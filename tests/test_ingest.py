import os
from pathlib import Path

from localmind.ingest import canonical_roots, scan


def make(tmp: Path):
    (tmp / "a").mkdir()
    (tmp / "a/note.md").write_text("hello atlas")
    (tmp / "a/code.py").write_text("print(1)")
    (tmp / "a/.env").write_text("SECRET=1")
    (tmp / "a/.env.local.md").write_text("x")
    (tmp / "a/id_rsa.txt").write_text("-----BEGIN-----")
    (tmp / "a/credentials.json").write_text("{}")
    (tmp / "a/blob.txt").write_bytes(b"ab\x00cd")
    (tmp / "a/empty.md").write_text("  ")
    (tmp / "a/node_modules").mkdir()
    (tmp / "a/node_modules/x.md").write_text("dep")
    (tmp / "a/.hidden").mkdir()
    (tmp / "a/.hidden/h.md").write_text("hid")
    (tmp / "a/bad.pdf").write_bytes(b"not a pdf")
    (tmp / "a/ignored.bin").write_bytes(b"\x01")
    (tmp / "out.md").write_text("outside root")


def test_scan_rules(tmp_path):
    make(tmp_path)
    os.symlink(tmp_path / "out.md", tmp_path / "a/link.md")
    r = scan([str(tmp_path / "a")])
    names = {Path(d.path).name for d in r.docs}
    assert names == {"note.md", "code.py"}
    reasons = dict((Path(p).name, why) for p, why in r.skipped)
    assert reasons["link.md"] == "symlink"
    assert reasons[".env.local.md"] == "hidden"
    assert reasons["id_rsa.txt"] == "credential file"
    assert reasons["credentials.json"] == "credential file"
    assert ".env" not in reasons and ".env" not in names
    assert reasons["blob.txt"] == "binary content"
    assert any(Path(p).name == "bad.pdf" for p, _ in r.failed)
    assert not any("node_modules" in d.path or ".hidden" in d.path for d in r.docs)


def test_exclude_and_nested_roots(tmp_path):
    make(tmp_path)
    (tmp_path / "a/vault").mkdir()
    (tmp_path / "a/vault/v.md").write_text("generated")
    r = scan([str(tmp_path / "a"), str(tmp_path / "a/vault")], exclude=[tmp_path / "a/vault"])
    assert all("vault" not in d.path for d in r.docs)
    assert len(canonical_roots([str(tmp_path / "a"), str(tmp_path / "a/vault")])) == 1


def test_stable_ids_and_size_limit(tmp_path):
    make(tmp_path)
    a = scan([str(tmp_path / "a")]).docs
    b = scan([str(tmp_path / "a")]).docs
    assert [d.doc_id for d in a] == [d.doc_id for d in b]
    (tmp_path / "a/big.md").write_text("x" * (2 * 1024 * 1024))
    r = scan([str(tmp_path / "a")], max_mb=1)
    assert any("limit" in why for _, why in r.skipped)


def test_explicitly_selected_excluded_roots_are_not_scanned(tmp_path):
    vault = tmp_path / "vault"
    sub = vault / "nested"
    sub.mkdir(parents=True)
    (sub / "note.md").write_text("Generated note")
    for root in (vault, sub):
        assert scan([str(root)], exclude=[vault]).docs == []
