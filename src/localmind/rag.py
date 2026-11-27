"""LightRAG + Ollama adapters, staged rebuild, evidence-backed querying."""
from __future__ import annotations

import asyncio
import fcntl
import json
import shutil
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from .config import Config, is_loopback
from .export_graph import export_vault, replace_build
from .ingest import ScanResult, scan
from .paths import AppPaths, default_paths

MODES = {"GraphRAG": None, "Vector only": "naive"}  # GraphRAG resolves to cfg.graph_mode
LLM_OPTIONS = {"num_ctx": 8192, "temperature": 0.1, "think": False}


# ---------- environment checks ----------
def check_ollama(cfg: Config) -> list[str]:
    """Actionable problems; empty list = ready."""
    if not is_loopback(cfg.ollama_host):
        return [f"Ollama host {cfg.ollama_host} is not loopback; remote inference is disabled."]
    try:
        with urllib.request.urlopen(cfg.ollama_host + "/api/tags", timeout=3) as r:
            have = {m["name"] for m in json.load(r)["models"]}
    except Exception:
        return [f"Ollama not reachable at {cfg.ollama_host}. Start it with `ollama serve`."]
    out = []
    for m in (cfg.llm_model, cfg.embed_model):
        if m not in have and f"{m}:latest" not in have:
            out.append(f"Model '{m}' missing. Run: ollama pull {m}")
    return out


def probe_embed_dim(cfg: Config) -> int:
    """Actual dimension returned by the embedding model (spec M0)."""
    import ollama

    r = ollama.Client(host=cfg.ollama_host).embed(model=cfg.embed_model, input="dimension probe")
    return len(r["embeddings"][0])


# ---------- LightRAG factory ----------
async def open_rag(cfg: Config, working_dir: Path):
    from lightrag import LightRAG
    from lightrag.llm.ollama import ollama_embed, ollama_model_complete
    from lightrag.utils import EmbeddingFunc

    if not is_loopback(cfg.ollama_host):
        raise RuntimeError("Only loopback Ollama endpoints are allowed.")
    dim = await asyncio.to_thread(probe_embed_dim, cfg)
    working_dir.mkdir(parents=True, exist_ok=True)
    rag = LightRAG(
        working_dir=str(working_dir),
        llm_model_func=ollama_model_complete,
        llm_model_name=cfg.llm_model,
        llm_model_kwargs={"host": cfg.ollama_host, "options": dict(LLM_OPTIONS)},
        llm_model_max_async=1,  # one worker: fits a 16 GB laptop
        embedding_func=EmbeddingFunc(
            embedding_dim=dim, max_token_size=8192, model_name=cfg.embed_model,
            func=partial(ollama_embed.func, embed_model=cfg.embed_model, host=cfg.ollama_host)),
    )
    await rag.initialize_storages()
    return rag


# ---------- citations (pure, unit-tested) ----------
@dataclass
class Citation:
    path: str
    excerpt: str


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    mode: str = ""
    model: str = ""
    elapsed: float = 0.0
    warnings: list[str] = field(default_factory=list)


def build_citations(data: dict, doc_paths: dict[str, str], max_chars: int = 400) -> list[Citation]:
    """LightRAG reports basenames, so resolve the chunk id ("<doc_id>-chunk-N")
    to the original absolute path via the manifest. Model-written filenames
    are never trusted; chunks of unknown docs are dropped."""
    seen, out = set(), []
    for ch in (data or {}).get("chunks", []):
        key = ch.get("chunk_id") or ""
        path = doc_paths.get(key.rsplit("-chunk-", 1)[0])
        if not path or key in seen:
            continue
        seen.add(key)
        out.append(Citation(path, " ".join(ch.get("content", "").split())[:max_chars]))
    return out


# ---------- engine: one asyncio loop in a worker thread ----------
class Engine:
    def __init__(self, cfg: Config, paths: AppPaths | None = None):
        self.cfg = cfg
        self.paths = paths or default_paths()
        self.paths.ensure_base_dirs()
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self._rag = None
        self._manifest: dict = {}

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    # -- manifest --
    def manifest(self) -> dict:
        try:
            return json.loads((self.paths.storage / "manifest.json").read_text())
        except (OSError, ValueError):
            return {}

    def has_index(self) -> bool:
        return bool(self.manifest())

    # -- build: staging -> publish only on success --
    def rebuild(self, progress=lambda stage, **kw: None) -> dict:
        with (self.paths.data_dir / ".refresh.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("A knowledge base refresh is already running.") from exc
            return self.run(self._rebuild(progress))

    async def _rebuild(self, progress) -> dict:
        cfg = self.cfg
        storage, vault = self.paths.storage, self.paths.vault
        stage, stage_vault = storage.with_name("storage.staging"), vault.with_name("vault.staging")
        for staged_dir in (stage, stage_vault):
            shutil.rmtree(staged_dir, ignore_errors=True)
        progress("scanning")
        res: ScanResult = await asyncio.to_thread(
            scan, cfg.roots, [*self.paths.excluded_dirs, stage, stage_vault], cfg.max_file_mb)
        progress("scanned", discovered=res.discovered, skipped=len(res.skipped), failed=len(res.failed),
                 processed=0, total=len(res.docs))
        if not res.docs:
            raise RuntimeError("No supported documents found in the selected directories.")
        rag = await open_rag(cfg, stage)
        done, failed = 0, list(res.failed)
        try:
            for doc in res.docs:
                progress("indexing", current=doc.path, processed=done, total=len(res.docs))
                try:
                    await rag.ainsert(doc.text, ids=[doc.doc_id], file_paths=[doc.path])
                    st = await rag.doc_status.get_by_id(doc.doc_id)
                    if st and str(st.get("status", "")).lower().endswith("failed"):
                        raise RuntimeError(st.get("error_msg") or "extraction failed")
                    done += 1
                except Exception as e:
                    failed.append((doc.path, f"{type(e).__name__}: {e}"))
            if done == 0:
                raise RuntimeError("Every document failed to index; first error: " + failed[0][1])
            progress("exporting")
            g = rag.chunk_entity_relation_graph
            nodes, edges = await g.get_all_nodes(), await g.get_all_edges()
        finally:
            await rag.finalize_storages()
        docs = {d.doc_id: d.path for d in res.docs if d.path not in {p for p, _ in failed}}
        if vault.is_symlink() or (vault.exists() and not vault.is_dir()):
            raise ValueError(f"Refusing to replace {vault}. Expected a LocalMind vault folder.")
        if vault.exists():
            await asyncio.to_thread(shutil.copytree, vault, stage_vault, symlinks=True)
        stats = await asyncio.to_thread(export_vault, nodes, edges, stage_vault, docs)
        manifest = {"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "roots": cfg.roots,
                    "docs": docs,
                    "discovered": res.discovered, "skipped": len(res.skipped), "failed": len(failed),
                    "llm_model": cfg.llm_model, "embed_model": cfg.embed_model, **stats}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2))
        await self.close()
        replace_build(stage, storage, stage_vault, vault)
        progress("done", processed=done, total=len(res.docs), failed=len(failed))
        return {"manifest": manifest, "skipped": res.skipped, "failed": failed}

    # -- query --
    async def close(self):
        if self._rag is not None:
            await self._rag.finalize_storages()
            self._rag = None

    def ask(self, question: str, mode_label: str) -> Answer:
        return self.run(self._ask(question, mode_label))

    async def _ask(self, question: str, mode_label: str) -> Answer:
        if self.cfg.blocked:
            raise RuntimeError("A source was removed. Rebuild to query again.")

        from lightrag import QueryParam

        man = self.manifest()
        if not man:
            raise RuntimeError("No knowledge base yet. Click 'Build knowledge base'.")
        if self._rag is None:
            self._rag = await open_rag(self.cfg, self.paths.storage)
        rag = self._rag
        assert rag is not None
        mode = MODES[mode_label] or self.cfg.graph_mode
        t0 = time.time()
        r = await rag.aquery_llm(question, QueryParam(mode=mode, stream=False, enable_rerank=False,
                                              top_k=10, chunk_top_k=5))  # same budget both modes)
        cites = build_citations(r.get("data") or {}, man["docs"])
        text = (r.get("llm_response") or {}).get("content") or ""
        warnings = []
        if r.get("status") == "failure" or not cites:
            warnings.append("No supporting evidence retrieved; answer withheld.")
            text = "Insufficient evidence in the indexed documents to answer this."
            cites = []
        return Answer(text, cites, mode_label, self.cfg.llm_model, time.time() - t0, warnings)
