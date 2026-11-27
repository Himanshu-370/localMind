import pytest

from localmind.export_graph import MARKER, assign_filenames, broken_links, export_vault, replace_dir

NODES = [
    {"id": "Project Atlas", "entity_type": "project", "description": "Atlas.", "source_id": "d1-chunk-000"},
    {"id": "Kafka", "entity_type": "tech", "description": "Broker<SEP>Stream", "source_id": "d1-chunk-000<SEP>d2-chunk-001"},
    {"id": "AWS/MSK", "entity_type": "tech", "description": "Managed", "source_id": "d2-chunk-000"},
    {"id": "aws:msk", "entity_type": "tech", "description": "dup name", "source_id": "d3-chunk-000"},
]
EDGES = [
    {"source": "Project Atlas", "target": "Kafka", "description": "uses", "keywords": "uses", "source_id": "d1-chunk-000"},
    {"source": "Kafka", "target": "AWS/MSK", "description": "hosted on", "keywords": "hosting", "source_id": "d2-chunk-000"},
    {"source": "Kafka", "target": "Ghost", "description": "dangling", "keywords": "", "source_id": ""},
]


DOCS = {"d1": "/p/a.md", "d2": "/p/b.md", "d3": "/p/c.md"}


def test_filenames_deterministic_and_collision_free():
    a = assign_filenames([n["id"] for n in NODES])
    assert a == assign_filenames(list(reversed([n["id"] for n in NODES])))
    assert len({v.lower() for v in a.values()}) == len(NODES)
    assert all("/" not in v and ":" not in v for v in a.values())


def test_export_links_sources_and_no_broken(tmp_path):
    v = tmp_path / "v"
    stats = export_vault(NODES, EDGES, v, DOCS)
    assert stats == {"notes": 4, "edges": 2}
    assert broken_links(v) == []
    kafka = (v / "Kafka.md").read_text()
    assert "[[Project Atlas]]" in kafka and "`/p/a.md`" in kafka and "hosted on" in kafka
    assert "Ghost" not in kafka


def test_refuses_foreign_dir_and_clears_only_owned(tmp_path):
    v = tmp_path / "personal"
    v.mkdir()
    (v / "mine.md").write_text("keep")
    with pytest.raises(ValueError):
        export_vault(NODES, EDGES, v)
    assert (v / "mine.md").exists()
    g = tmp_path / "gen"
    export_vault(NODES, EDGES, g)
    (g / "stale.md").write_text("x")
    export_vault(NODES[:1], [], g)
    assert (g / "stale.md").read_text() == "x" and (g / MARKER).exists()


def test_replace_dir_keeps_old_on_failure(tmp_path):
    final = tmp_path / "vault"
    final.mkdir()
    (final / "old.md").write_text("old")
    staged = tmp_path / "stage"
    staged.mkdir()
    (staged / "new.md").write_text("new")
    replace_dir(staged, final)
    assert (final / "new.md").exists() and not (tmp_path / "vault.old").exists()
    with pytest.raises(Exception):
        replace_dir(tmp_path / "missing", final)
    assert (final / "new.md").exists()


def test_regeneration_preserves_user_notes_and_settings(tmp_path):
    vault = tmp_path / "vault"
    export_vault(NODES, EDGES, vault, DOCS)
    (vault / "Personal.md").write_text("keep")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "appearance.json").write_text("{}")
    export_vault(NODES[:1], [], vault, DOCS)
    assert (vault / "Personal.md").read_text() == "keep"
    assert (vault / ".obsidian" / "appearance.json").read_text() == "{}"
    assert not (vault / "Kafka.md").exists()


def test_publish_rolls_back_both_artifacts_on_vault_failure(tmp_path, monkeypatch):
    from pathlib import Path

    from localmind.export_graph import replace_build

    storage, vault = tmp_path / "storage", tmp_path / "vault"
    stage, stage_vault = tmp_path / "storage.staging", tmp_path / "vault.staging"
    for folder in (storage, vault, stage, stage_vault):
        folder.mkdir()
        (folder / "content").write_text(folder.name)
    rename = Path.rename

    def fail_vault_publish(source, target):
        if source == stage_vault and target == vault:
            raise OSError("vault publish failed")
        return rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_vault_publish)
    with pytest.raises(OSError, match="vault publish failed"):
        replace_build(stage, storage, stage_vault, vault)
    assert (storage / "content").read_text() == "storage"
    assert (vault / "content").read_text() == "vault"


def test_conflicting_legacy_note_survives_refresh(tmp_path):
    from localmind.export_graph import LEGACY_MARKER

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / MARKER).write_text(LEGACY_MARKER)
    (vault / "Kafka.md").write_text("personal or edited note")
    with pytest.raises(ValueError, match="Move or rename"):
        export_vault(NODES, EDGES, vault, DOCS)
    assert (vault / "Kafka.md").read_text() == "personal or edited note"
    assert (vault / MARKER).read_text() == LEGACY_MARKER
    assert not (vault / "Project Atlas.md").exists()


def test_edited_generated_note_survives_refresh(tmp_path):
    vault = tmp_path / "vault"
    export_vault(NODES, EDGES, vault, DOCS)
    (vault / "Kafka.md").write_text("my edits")
    with pytest.raises(ValueError, match="Move or rename"):
        export_vault(NODES, EDGES, vault, DOCS)
    export_vault(NODES[:1], [], vault, DOCS)
    assert (vault / "Kafka.md").read_text() == "my edits"
