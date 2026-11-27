# LocalMind installation and onboarding specification

## 1. Goal

Make the showcase MVP in [SPEC.md section 16](SPEC.md#16-minimal-showcase-mvp--local-graphrag-with-obsidian) usable without cloning the repository, creating a virtual environment, or running commands as an administrator.

The supported happy path is:

```sh
curl -fsSL https://raw.githubusercontent.com/OWNER/localMind/main/install.sh | sh
localmind
```

`OWNER` is a release-time placeholder and must be replaced with the repository owner before this command is published.

This work changes distribution and onboarding, not the GraphRAG design. The existing Tkinter folder picker, staged build, local Ollama inference, cited answers, and optional Obsidian projection remain the MVP.

## 2. MVP scope

### In scope

- A POSIX `install.sh` for supported macOS and Linux systems.
- Installation as an isolated Python command with `uv tool`.
- A `localmind` console entry point that launches the existing Tkinter app.
- Application configuration and generated data stored outside the installed package.
- First-run checks for Ollama, required models, writable directories, and Tkinter.
- Explicit user consent before LocalMind starts any model download.
- Clear update, diagnostics, and uninstall instructions.

### Explicitly deferred

- `.app`, `.dmg`, `.pkg`, AppImage, Flatpak, Snap, MSI, and other app bundles or native installers.
- A web UI, local web server, custom graph UI, or mobile UI.
- Automatically installing, upgrading, starting, or configuring Ollama.
- Bundling Ollama, models, Python, Obsidian, or user documents.
- Windows installer scripting. The Python path layout must be Windows-correct so a later installer can use it.
- Background updates, file watching, cloud services, and telemetry.

## 3. Distribution contract

### 3.1 Python package

Package LocalMind as an installable Python project with:

- Python 3.11 or newer declared in package metadata.
- Runtime dependencies separated from development/test dependencies.
- A console script named `localmind`.
- Package resources addressed through package APIs, never by assuming a writable source checkout.
- A version available through `localmind --version`.

Running `localmind` with no subcommand launches the Tkinter UI. The minimum supporting CLI is:

```text
localmind                 Launch the UI
localmind doctor          Print readiness checks and actionable fixes
localmind paths           Print config, data, cache, and vault paths
localmind --version       Print the installed version
```

The PyPI distribution and `uv tool` name are `localmind-graphrag`; the import
package and installed console command remain `localmind`. The shorter PyPI name
is already owned by an unrelated project.

### 3.2 Published artifact

Publish tested source distributions and wheels to PyPI. `install.sh` installs the released package:

```sh
uv tool install localmind-graphrag
```

The raw script on `main` is only a small bootstrapper; application code comes from a versioned package artifact, not an archive of the moving `main` branch. A release must not update the public installer instructions until its package is available.

### 3.3 Installer behavior

`install.sh` must:

1. Use portable POSIX `sh`, `set -eu`, and HTTPS URLs.
2. Detect supported macOS/Linux and fail clearly on unsupported systems.
3. Never require or invoke `sudo`.
4. Never clone the repository and never write into the current directory.
5. If `uv` is present, use it. If it is absent, state that the official Astral `uv` installer will be downloaded into the user's account, then run that installer without elevation. The install command itself is the user's authorization for these package-manager downloads.
6. Run `uv tool install localmind-graphrag` (or report that it is already installed) and preserve useful `uv` errors.
7. Ensure the `uv` tool bin directory is on `PATH` using `uv tool update-shell`, or print the exact one-time PATH command when the shell cannot be updated safely.
8. Print only the next useful actions: reopen the shell if needed, run `localmind doctor`, then run `localmind`.

The script must not install Ollama, pull models, launch the app, alter system Python, edit privileged locations, or collect analytics. Re-running it must be safe and idempotent.

For users who do not want to pipe a network response into a shell, documentation must offer an inspect-first equivalent:

```sh
curl -fsSLo install.sh https://raw.githubusercontent.com/OWNER/localMind/main/install.sh
less install.sh
sh install.sh
rm install.sh
```

Release documentation should show a checksum for `install.sh`. A future phase may pin artifact hashes or verify release signatures.

## 4. User-owned paths

Installed package directories are read-only. No configuration, indexes, staging directories, generated vault, logs, or downloaded runtime assets may be written beside Python modules.

Use `platformdirs` rather than hand-built home-directory logic:

| Purpose | macOS | Linux | Windows (future installer) |
|---|---|---|---|
| Config | `~/Library/Application Support/LocalMind/config.json` | `${XDG_CONFIG_HOME:-~/.config}/localmind/config.json` | `%APPDATA%\LocalMind\config.json` |
| Persistent data | `~/Library/Application Support/LocalMind/` | `${XDG_DATA_HOME:-~/.local/share}/localmind/` | `%LOCALAPPDATA%\LocalMind\` |
| Cache | `~/Library/Caches/LocalMind/` | `${XDG_CACHE_HOME:-~/.cache}/localmind/` | `%LOCALAPPDATA%\LocalMind\Cache\` |

Persistent data contains:

```text
storage/          active graph/vector index and manifest
storage.staging/  transactional rebuild only
vault/            LocalMind-owned generated Obsidian vault
vault.staging/    transactional export only
```

Configuration contains selected source paths and settings. Cache contains reproducible downloads/caches and may be deleted without losing configuration or the last built knowledge base. Logs, if introduced, must contain no document text by default.

Requirements:

- Create directories lazily with user-only permissions where the OS supports them.
- Respect XDG overrides on Linux.
- `localmind paths` reports resolved paths, and error messages name the failing path.
- Preserve the current staging-and-replace behavior: a failed build keeps the previous index and vault.
- Never scan LocalMind's own config, data, cache, storage, or vault, even if a user selects an ancestor directory.
- Never modify selected source files.
- Package upgrades and reinstalls preserve all user-owned paths.
- A one-time migration from checkout-local data is deferred; do not silently search for or move old data.

## 5. First-run readiness

Readiness is a guided state in the existing UI, not a separate account/setup wizard. Folder selection remains available when inference is not ready.

On every launch, and on demand through **Check again** / `localmind doctor`, check:

1. User directories are writable.
2. Tkinter can create the UI.
3. The configured Ollama endpoint is loopback (`127.0.0.1`, `localhost`, or `::1`).
4. Ollama is installed/reachable.
5. `qwen3:4b` and `nomic-embed-text` are available.
6. The last index, if present, is readable and compatible with the installed LocalMind version.

### Ollama absent or unreachable

Show a plain-language explanation that Ollama runs the models locally, a link to the official Ollama installation instructions, and platform-appropriate advice to start it. Provide **Check again**. LocalMind must not download or install Ollama, run an unreviewed vendor installer, or silently change the configured service.

### Models missing

List each missing model, its purpose, model identifier, estimated download size when known, and a link or reminder to review its license. Then offer:

- **Download models** — after a confirmation such as “This will run `ollama pull` for the listed models and download approximately … to Ollama's data directory. Continue?”
- **Not now** — closes the prompt without side effects.
- Copyable manual commands:

  ```sh
  ollama pull qwen3:4b
  ollama pull nomic-embed-text
  ```

Consent defaults to **Not now** and is required before each newly requested set of downloads. Stream pull progress and allow the user to retry after failure. Do not interpret launching LocalMind, adding a folder, or clicking Build as consent. LocalMind must not delete or upgrade Ollama models.

While readiness is incomplete, users may add/remove folders and inspect paths, but **Build** and **Ask** are disabled with an actionable reason. Opening a previously generated vault may remain available.

No runtime component may contact a remote inference endpoint. Any other possible first-use network fetch (for example, a tokenizer cache) must be eliminated by packaging it or disclosed and explicitly confirmed before download. Once dependencies and models are present, build and ask must work offline.

## 6. Core onboarding journey

Keep the primary UI and language task-oriented:

1. **Choose folders** — launch `localmind`; click **Add directory** one or more times. Show canonical absolute paths and explain that originals are read-only. Cancellation changes nothing.
2. **Build** — once readiness passes, click **Build knowledge base**. Show discovered, processed, skipped, and failed counts without freezing the UI. Explain that processing can take minutes and remains local. A failed rebuild retains the prior usable index and vault.
3. **Ask** — after a successful build, focus the question box and offer one short example. **GraphRAG** remains the default; **Vector only** remains available for comparison. Every answer shows verified source paths and excerpts, or says evidence is insufficient.
4. **Browse (optional)** — **Open in Obsidian** opens only LocalMind's generated vault when registered; otherwise show its exact path and “Open folder as vault” instructions. Obsidian is optional for building and asking and is never installed automatically.

If folders change, mark the index stale. Removing a folder blocks questions until a successful rebuild so removed content cannot remain queryable.

## 7. Upgrades

The documented upgrade command is:

```sh
uv tool upgrade localmind-graphrag
```

An upgrade must not rebuild an index automatically, pull models, or change selected folders. On launch after an upgrade:

- Read older configuration defensively, retaining known values.
- Detect incompatible storage through a manifest schema/app version.
- If a rebuild is required, explain why and require the user to start it.
- Keep prior data until the replacement build succeeds.

Rollback tooling and automatic update checks are deferred. Users may inspect the installed version with `localmind --version`.

## 8. Uninstall

Remove the executable and isolated environment with:

```sh
uv tool uninstall localmind-graphrag
```

This intentionally preserves configuration, indexes, and the generated vault. Documentation must then show `localmind paths` *before uninstalling* and explain how to delete those exact directories manually if the user wants a full purge.

Do not provide a broad wildcard or recursive home-directory deletion command. Never remove source folders, source files, Ollama, Ollama models, Obsidian, `uv`, or shared caches as part of LocalMind uninstall. A dedicated, path-validated `localmind uninstall --purge` command is deferred.

## 9. Safety and privacy requirements

- No `sudo`, privileged writes, system Python mutation, shell profile replacement, or repository clone.
- Installer and app errors must be actionable and must not hide failed downloads or commands.
- All inference is restricted to loopback; there is no cloud fallback.
- No telemetry, analytics, crash upload, or automatic update request in the MVP.
- Network operations initiated by LocalMind are visible and require consent when they download models or runtime assets.
- Continue best-effort exclusion of hidden, symlinked, binary, oversized, generated, and credential-like files. State clearly that this is not a guarantee.
- Resolve selected roots canonically, do not follow symlinks, and do not read outside approved roots.
- Generated output belongs only in LocalMind's data directory and must never overwrite a personal Obsidian vault.
- Quote shell variables, use temporary files safely, validate paths before deletion/replacement, and preserve the last successful build.
- Public release artifacts, scripts, fixtures, and logs must contain no credentials, private documents, or machine-specific paths.

## 10. Acceptance criteria

- [ ] On a clean supported macOS and Linux user account, the published curl command installs `localmind` without cloning, creating a project venv, or using `sudo`.
- [ ] Re-running `install.sh` is safe and gives a useful already-installed or upgrade instruction.
- [ ] `command -v localmind`, `localmind --version`, `localmind paths`, and `localmind doctor` work in a fresh shell.
- [ ] The installed command launches the same responsive Tkinter workflow required by SPEC.md section 16.
- [ ] No mutable file is created in site-packages, the tool environment, the current directory, or the source repository.
- [ ] Config, storage, staging data, cache, and vault resolve to the documented platform directories.
- [ ] Missing Ollama produces official manual installation/start guidance; LocalMind does not install it.
- [ ] Missing models are named and are not pulled until the user explicitly confirms; declining leaves the app usable for folder selection.
- [ ] After consent, model pulls show progress, errors, and a retry path.
- [ ] A user can choose folders, build, ask a cited question, and optionally open the generated vault without using a terminal after launch.
- [ ] Original files are unchanged, LocalMind-owned directories are excluded from scans, and removed sources require a successful rebuild before querying.
- [ ] After installation and approved model downloads, folder/build/ask works with the network disconnected and no remote fallback.
- [ ] `uv tool upgrade localmind-graphrag` preserves user data and either opens the existing index or clearly requests a user-started rebuild.
- [ ] `uv tool uninstall localmind-graphrag` removes the command but preserves user data and never removes Ollama, models, Obsidian, or source documents.
- [ ] Installer tests cover unsupported OS handling, missing/present `uv`, PATH guidance, idempotence, and failed package installation.
- [ ] Package tests and type checks pass from both a wheel installation and an isolated `uv tool` installation.

## 11. Phased implementation

### Phase 1 — Package and paths

- Add modern package metadata, the `localmind` entry point, version reporting, and runtime/dev dependency separation.
- Move config, storage, staging, and vault resolution to `platformdirs`.
- Add `paths` and `doctor`; update exclusions for all resolved LocalMind directories.
- Add path, permissions, read-only-package, and upgrade-preservation tests.

Exit: a locally built wheel installed with `uv tool install` launches the app and completes folder/build/ask without writing into the package or current directory.

### Phase 2 — Readiness and consent

- Replace the current chat-log-only startup warnings with a clear readiness area and **Check again** action.
- Implement missing-Ollama guidance and explicit model-pull confirmation/progress.
- Disable only model-dependent actions, not folder management.
- Remove or consent-gate any tokenizer/runtime fetch and verify offline operation.

Exit: clean-machine, declined-download, failed-download, and offline paths meet the acceptance criteria.

### Phase 3 — Release and installer

- Publish a test wheel/source distribution, install both in clean environments, then publish the release to PyPI.
- Add the small audited `install.sh`, installer tests, checksum, inspect-first instructions, upgrade instructions, and uninstall instructions.
- Replace `OWNER`, test the exact public raw URL on clean macOS and Linux accounts, and only then make the curl command prominent.

Exit: the documented one-line command installs the released package without clone or elevation, and a new user can reach the first folder selection with clear Ollama guidance.

### Phase 4 — Hardening

- Test supported OS/Python combinations, shell PATH edge cases, interrupted builds, incompatible manifests, and data preservation through upgrade/uninstall.
- Add release CI that builds artifacts, runs tests and type checks, scans for secrets, and smoke-tests an isolated `uv tool` install.
- Record the supported platforms and known limitations.

Exit: all acceptance criteria pass in release CI or are documented as manually verified platform checks.

App bundles, a web UI, automatic Ollama installation, automatic updates, Windows installer scripting, and destructive purge automation remain deferred after Phase 4.
