# api-client

**Your API requests live in Git, not a cloud account.**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
api-client
```

Cross-platform desktop client for building and sending HTTP requests. Projects are plain JSON folders on disk — diffable, shareable, version-controlled.

| | |
|---|---|
| On-disk requests | One JSON file per request under `requests/` |
| HTTP methods | GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS |
| Request body | none, JSON, or raw text |
| Headers | Key/value table editor |
| Collections | Nested folders; add, rename, delete |
| Stack | Python 3.11+, PySide6, httpx |

MVP today: create and open projects, organize requests in folders, send calls, read responses. The `environments/` directory is reserved for variables — not wired into the UI yet.

## Quick start

Requires Python 3.11 or newer.

```bash
cd api-client
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
api-client
```

On Windows, activate with `.venv\Scripts\activate`. You can also launch without the console script:

```bash
python -m apiclient
```

## Project layout

Each project is a directory you pick in the app:

```
my-api-project/
├── project.json
├── collection.json
├── environments/
└── requests/
    └── users/
        └── list-users.json
```

A request file looks like this:

```json
{
  "name": "List users",
  "method": "GET",
  "url": "https://api.example.com/users",
  "headers": {"Accept": "application/json"},
  "body": {"mode": "none", "content": ""}
}
```

`collection.json` holds the folder tree; individual requests stay in separate files so diffs stay small.

## Development

| Task | Command |
|------|---------|
| Run | `api-client` or `python -m apiclient` |
| Tests | `pytest` |
| Lint | `ruff check src tests` |

## Packaging

Build on the target OS — PyInstaller does not cross-compile.

```bash
pip install -e ".[dev]"
pyinstaller packaging/apiclient.spec
```

Output: `dist/api-client/`. Runtime dependencies use `pyside6-essentials` to keep the bundle lean.
