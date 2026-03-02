# Sbírka MCP

MCP server for Czech e-Sbírka legislation system (e-sbirka.cz).

## Architecture

```
FastMCP Server (sbirka_server.py) — 3 tools, stdio transport
    ↓
SbirkaClient (sbirka_client.py) — httpx async + in-memory cache (1h TTL)
    ↓
e-Sbírka API (https://www.e-sbirka.cz/sbr-cache/)
```

## Key Files

- `sbirka_client.py` — API client: autocomplete, fulltext search, metadata, fragments, XHTML→Markdown conversion, article finder
- `sbirka_server.py` — FastMCP server with 3 tools: `search_czech_legislation`, `get_czech_law_text`, `get_czech_law_article`
- `pyproject.toml` — Project config (fastmcp, httpx, beautifulsoup4, lxml)
- `fastmcp.json` — MCP server config for `uv run`

## Design Decisions

- **No Pydantic models** — Tools return plain `str` (Markdown). Client works with raw `dict` from API responses.
- **Field() from pydantic** — Used for tool parameter descriptions only.
- **Cache** — Simple dict-based with TTL, no external dependency.
- **XHTML→Markdown** — Regex-based conversion. Cross-references resolved via `odkazyZFragmentu` array.
- **Fragment heading hierarchy** — Based on `hloubka` (depth) field: 0→`#`, 1→`##`, 2→`###`, 3→`####`, 4→`#####`, 5→`######`.

## API Base URL

`https://www.e-sbirka.cz/sbr-cache/`

No authentication required. Public API, JSON responses.

## staleUrl Format

- `/sb/{year}/{number}` — latest version
- `/sb/{year}/{number}/{date}` — specific version
- Must be URL-encoded when used in path params: `quote(staleUrl, safe='')`

## Running

```bash
uv run fastmcp run sbirka_server.py     # stdio
uv run fastmcp dev sbirka_server.py     # dev inspector
uv run python -c "from sbirka_server import mcp; ..."  # in-memory test
```

## Testing

In-memory test with FastMCP Client:
```python
from fastmcp import Client
from sbirka_server import mcp

async with Client(mcp) as c:
    r = await c.call_tool("search_czech_legislation", {"query": "40/2009"})
    print(r.content[0].text)
```
