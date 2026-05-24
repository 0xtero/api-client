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
| Request body | none, JSON, text, form-urlencoded, multipart, file |
| Headers | Key/value table with enable/disable per row |
| Parameters | Path (`:id`) and query param tables |
| Authentication | Bearer, Basic, API key (header or query) |
| Request settings | Redirects, timeout, max redirects, URL encoding |
| cURL | Copy as cURL and import from cURL |
| Responses | Status class, headers, formatted body, elapsed time |
| Collections | Nested folders; add, rename, delete |
| Stack | Python 3.11+, PySide6, httpx |

Projects are folders of JSON on disk. Create requests, send them, inspect responses. The `environments/` directory is reserved for variables — not wired into the UI yet.

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
  "url": "https://api.example.com/users/:userId",
  "path_params": [{"name": "userId", "value": "42", "enabled": true}],
  "query_params": [{"name": "include", "value": "orders", "enabled": true}],
  "headers": [{"name": "Accept", "value": "application/json", "enabled": true}],
  "body": {"mode": "none", "content": "", "form_fields": [], "multipart_fields": []},
  "auth": {"type": "none"},
  "settings": {"follow_redirects": true, "max_redirects": 5, "timeout_ms": 30000, "encode_url": true}
}
```

Legacy request files with `"headers": {"Accept": "..."}` still load; they are saved in the list format above.

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
