from localmind.config import Config
from localmind.rag import build_citations, check_ollama


def test_citations_only_from_manifest_and_deduped():
    data = {"chunks": [
        {"file_path": "a.md", "chunk_id": "doc-1-chunk-000", "content": "x  y\n z"},
        {"file_path": "a.md", "chunk_id": "doc-1-chunk-000", "content": "dup"},
        {"file_path": "evil.md", "chunk_id": "doc-9-chunk-000", "content": "not indexed"},
    ]}
    c = build_citations(data, {"doc-1": "/a.md"})
    assert [(x.path, x.excerpt) for x in c] == [("/a.md", "x y z")]
    assert build_citations({}, {"doc-1": "/a.md"}) == []


def test_remote_host_rejected_and_unreachable_message(monkeypatch):
    assert "not loopback" in check_ollama(Config(ollama_host="http://example.com:11434"))[0]
    def unavailable(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr("localmind.rag.urllib.request.urlopen", unavailable)
    assert "ollama serve" in check_ollama(Config(ollama_host="http://127.0.0.1:1"))[0]


def test_removed_sources_block_engine_queries():
    import asyncio
    from types import SimpleNamespace

    import pytest
    from localmind.rag import Engine

    engine = SimpleNamespace(cfg=Config(blocked=True), manifest=lambda: {})
    with pytest.raises(RuntimeError, match="source was removed"):
        asyncio.run(Engine._ask(engine, "What was indexed?", "GraphRAG"))
