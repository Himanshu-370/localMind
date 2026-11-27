# LocalMind (showcase MVP)

Local GraphRAG: pick folders, build a knowledge graph with a local model, browse it in
Obsidian, and ask cited questions from a desktop window. No cloud or paid API is required.
Product scope is in [SPEC.md](SPEC.md#16-minimal-showcase-mvp--local-graphrag-with-obsidian);
installation and onboarding are in [INSTALL_SPEC.md](INSTALL_SPEC.md).

## Install

LocalMind requires [Ollama](https://ollama.com) and a Python runtime with Tkinter. Once
the package is published, the supported installation will be:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/localMind/main/install.sh | sh
localmind doctor
localmind
```

`OWNER` is intentionally a placeholder until the public repository is created. To inspect
the installer instead of piping it directly to a shell:

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/OWNER/localMind/main/install.sh
less install.sh
sh install.sh
rm install.sh
```

The installer does not use `sudo`, clone the repository, install Ollama, or download models.
Pull the required models explicitly:

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

The first indexing run may fetch a tokenizer file. Fully offline first-run behavior remains
an implementation task; subsequent use works locally after dependencies, models, and caches
are present.

## Run

```bash
localmind
```

Useful diagnostics:

```bash
localmind --version
localmind paths
localmind doctor
```

Configuration, the index, and the generated vault are stored in platform-specific user
directories rather than beside the installed package. `localmind paths` prints their exact
locations.

## Use

1. **Add directory** (try `demo_data/projects` and `demo_data/operations`).
2. **Build knowledge base** (minutes on a laptop; originals are never modified).
3. **Open in Obsidian**, or open the vault reported by `localmind paths`.
4. Ask a question; choose `GraphRAG` or `Vector only` (same retrieval budget).

Removing a directory disables chat until you rebuild. A failed rebuild keeps the previous
index and vault. Skipped/failed files are listed in the chat panel.

Refresh preserves personal notes and Obsidian settings. If a generated note would
overwrite a personal or edited note, move or rename that note and retry. Vaults built
with v0.1.0 lack a note inventory, so refresh preserves their existing notes unless a
new note has identical content. To start with a fresh graph, move the old vault to a
different folder before refreshing.

## Development

From a source checkout:

```bash
uv sync --dev
uv run pytest
uv run mypy
uv build
```

Run the comparison after building an index:

```bash
uv run python -m localmind.compare
```

The existing checkout-local `config.json`, `storage/`, and `vault/` are not migrated
automatically. Packaged LocalMind starts with its own user-data directory.

Upgrade or remove the installed command with:

```bash
uv tool upgrade localmind-graphrag
uv tool uninstall localmind-graphrag
```

Uninstalling the command intentionally preserves user data. Run `localmind paths` before
uninstalling if you may want to remove those directories manually.

## Limits
- Supports `.md .txt .rst`, code/config text, and text-layer PDFs. Skips hidden, symlinked,
  binary, oversized and credential-like files (best effort, not a guarantee).
- Entity quality depends on the 4B model; edges can be missing or odd between runs.
- Edits to generated vault notes are not ingested. Vault and storage are never scanned.
- Models are downloaded separately; check their licenses before redistributing.
