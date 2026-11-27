"""LocalMind showcase MVP: Tkinter UI over LightRAG + Ollama + Obsidian export."""
from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import quote

from .config import Config
from .ingest import canonical_roots
from .paths import AppPaths, default_paths
from .rag import MODES, Engine, check_ollama


def _vault_registered(vault: Path) -> bool:
    """True if Obsidian already lists this folder as a vault (macOS config)."""
    import json

    cfg = Path.home() / "Library/Application Support/obsidian/obsidian.json"
    try:
        vaults = json.loads(cfg.read_text()).get("vaults", {}).values()
        return any(Path(v.get("path", "")).resolve() == vault.resolve() for v in vaults)
    except (OSError, ValueError):
        return False


class App(tk.Tk):
    def __init__(self, paths: AppPaths | None = None):
        super().__init__()
        self.title("LocalMind")
        self.geometry("920x720")
        self.paths = paths or default_paths()
        self.paths.ensure_base_dirs()
        self.cfg = Config.load(self.paths.config)
        self.engine = Engine(self.cfg, self.paths)
        self.q: queue.Queue = queue.Queue()  # workers -> UI; workers never touch Tk
        self.busy = False
        self._build_ui()
        self.after(100, self._poll)
        self._run_bg(self._startup_check, "startup")
        self._refresh_state()

    # ----- layout -----
    def _build_ui(self):
        src = ttk.LabelFrame(self, text="Source directories", padding=6)
        src.pack(fill="x", padx=8, pady=4)
        self.roots_list = tk.Listbox(src, height=5)
        self.roots_list.pack(side="left", fill="x", expand=True)
        btns = ttk.Frame(src)
        btns.pack(side="left", padx=6)
        self.add_btn = ttk.Button(btns, text="Add directory", command=self.add_dir)
        self.rm_btn = ttk.Button(btns, text="Remove selected", command=self.remove_dir)
        self.add_btn.pack(fill="x"), self.rm_btn.pack(fill="x", pady=2)

        st = ttk.LabelFrame(self, text="Knowledge base", padding=6)
        st.pack(fill="x", padx=8, pady=4)
        row = ttk.Frame(st)
        row.pack(fill="x")
        self.build_btn = ttk.Button(row, text="Build knowledge base", command=self.build)
        self.obs_btn = ttk.Button(row, text="Open in Obsidian", command=self.open_obsidian)
        self.build_btn.pack(side="left"), self.obs_btn.pack(side="left", padx=6)
        self.bar = ttk.Progressbar(row, mode="determinate")
        self.bar.pack(side="left", fill="x", expand=True, padx=6)
        self.status = tk.StringVar(value="Starting...")
        ttk.Label(st, textvariable=self.status, wraplength=860).pack(anchor="w", pady=(4, 0))
        self.counts = tk.StringVar()
        ttk.Label(st, textvariable=self.counts).pack(anchor="w")

        chat = ttk.LabelFrame(self, text="Chat", padding=6)
        chat.pack(fill="both", expand=True, padx=8, pady=4)
        self.log = scrolledtext.ScrolledText(chat, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("q", foreground="#0a58ca", font=("TkDefaultFont", 11, "bold"))
        self.log.tag_configure("src", foreground="#555555")
        self.log.tag_configure("err", foreground="#b02a37")
        bar = ttk.Frame(chat)
        bar.pack(fill="x", pady=(6, 0))
        self.entry = ttk.Entry(bar)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.ask())
        self.mode = ttk.Combobox(bar, values=list(MODES), state="readonly", width=12)
        self.mode.set("GraphRAG")
        self.mode.pack(side="left", padx=6)
        self.ask_btn = ttk.Button(bar, text="Ask", command=self.ask)
        self.ask_btn.pack(side="left")

    # ----- helpers -----
    def _say(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.config(state="disabled")
        self.log.see("end")

    def _run_bg(self, fn, kind):
        def work():
            try:
                self.q.put((kind, "ok", fn()))
            except Exception as e:
                self.q.put((kind, "err", e))
        threading.Thread(target=work, daemon=True).start()

    def _refresh_state(self):
        self.roots_list.delete(0, "end")
        for r in self.cfg.roots:
            self.roots_list.insert("end", r)
        man = self.engine.manifest()
        ready = bool(man) and not self.cfg.blocked
        idle = "disabled" if self.busy else "normal"
        self.add_btn.config(state=idle), self.rm_btn.config(state=idle)
        self.build_btn.config(state=idle if self.cfg.roots else "disabled",
                              text="Refresh knowledge base" if man else "Build knowledge base")
        self.ask_btn.config(state="normal" if ready and not self.busy else "disabled")
        self.obs_btn.config(state="normal" if self.paths.vault.exists() and not self.busy else "disabled")
        if not self.busy:
            if self.cfg.blocked:
                self.status.set("A source was removed. Rebuild to query again.")
            elif self.cfg.stale:
                self.status.set("Index is STALE: sources changed since last build. Click Refresh.")
            elif man:
                self.status.set(f"Ready. Built {man['built_at']} with {man['llm_model']}.")
            else:
                self.status.set("No knowledge base yet. Add a directory, then Build.")
            if man:
                self.counts.set(f"Last build: {len(man['docs'])} indexed, {man['skipped']} skipped, "
                                f"{man['failed']} failed, {man['notes']} graph notes")

    def _save(self):
        self.cfg.save(self.paths.config)
        self._refresh_state()

    # ----- sources -----
    def add_dir(self):
        d = filedialog.askdirectory(title="Choose a directory to index")
        if not d:
            return  # cancelled: nothing changes
        roots = [str(p) for p in canonical_roots(self.cfg.roots + [d])]
        if roots != self.cfg.roots:
            self.cfg.roots, self.cfg.stale = roots, True
            self._save()

    def remove_dir(self):
        sel = self.roots_list.curselection()
        if not sel:
            return
        self.cfg.roots.pop(sel[0])
        self.cfg.stale = self.cfg.blocked = True  # removed data must not be queryable
        self._save()

    # ----- build -----
    def build(self):
        self.busy = True
        self.bar.config(value=0)
        self._refresh_state()
        self.status.set("Starting build...")
        self._run_bg(lambda: self.engine.rebuild(lambda stage, **kw: self.q.put(("progress", stage, kw))),
                     "build")

    def open_obsidian(self):
        vault = self.paths.vault
        msg = (f"Vault: {vault}\nIn Obsidian: 'Open folder as vault' and select it "
                "(one time only; the Open button works afterwards).")
        if _vault_registered(vault):
            webbrowser.open("obsidian://open?path=" + quote(str(vault)))
            self._say(f"Opening vault: {vault}", "src")
        else:
            messagebox.showinfo("Open in Obsidian", msg)
            self._say(msg, "src")

    # ----- chat -----
    def ask(self):
        qn = self.entry.get().strip()
        if not qn or self.busy:
            return
        self.entry.delete(0, "end")
        self._say(f"Q [{self.mode.get()}]: {qn}", "q")
        self.busy = True
        self._refresh_state()
        self.status.set("Thinking...")
        label = self.mode.get()
        self._run_bg(lambda: self.engine.ask(qn, label), "answer")

    # ----- worker results -----
    def _startup_check(self):
        return check_ollama(self.cfg)

    def _poll(self):
        try:
            while True:
                kind, state, payload = self.q.get_nowait()
                getattr(self, f"_on_{kind}")(state, payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_startup(self, state, problems):
        if state == "err":
            problems = [str(problems)]
        if problems:
            self._say("Setup problems:\n- " + "\n- ".join(problems), "err")
        self._refresh_state()

    def _on_progress(self, stage, kw):
        if "total" in kw and kw["total"]:
            self.bar.config(maximum=kw["total"], value=kw.get("processed", 0))
        if stage == "indexing":
            self.status.set(f"Indexing {kw['processed'] + 1}/{kw['total']}: {Path(kw['current']).name}")
        else:
            self.status.set({"scanning": "Scanning files...", "exporting": "Exporting Obsidian vault...",
                             "scanned": "Scan complete.", "done": "Finishing..."}[stage])
        if "discovered" in kw:
            self.counts.set(f"Discovered {kw['discovered']}, skipped {kw['skipped']}, failed {kw['failed']}")

    def _on_build(self, state, res):
        self.busy = False
        if state == "err":
            self._say(f"Build failed (previous index kept): {res}", "err")
        else:
            self.cfg.stale = self.cfg.blocked = False
            self.cfg.save(self.paths.config)
            self._say(f"Build complete. Vault: {self.paths.vault}")
            for p, why in res["skipped"] + res["failed"]:
                self._say(f"  skipped/failed {p}: {why}", "src")
        self._refresh_state()

    def _on_answer(self, state, ans):
        self.busy = False
        if state == "err":
            self._say(f"Error: {ans}\nCheck that Ollama is running and models are pulled.", "err")
        else:
            self._say(ans.text)
            for c in ans.citations:
                self._say(f"  [{c.path}]\n    {c.excerpt}", "src")
            for w in ans.warnings:
                self._say(f"  note: {w}", "err")
            self._say(f"  ({ans.mode}, {ans.model}, {ans.elapsed:.1f}s)\n", "src")
        self._refresh_state()


if __name__ == "__main__":
    App().mainloop()
