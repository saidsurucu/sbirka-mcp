# Sbírka MCP: MCP Server for the Czech e-Sbírka Legislation System

This project provides a [FastMCP](https://gofastmcp.com/) server for accessing the Czech Republic's official legislation database [e-Sbírka](https://www.e-sbirka.cz/) (e-sbirka.cz). It enables searching, retrieving full texts, and extracting specific articles from Czech laws through the Model Context Protocol (MCP), making it usable as a tool by LLM applications (e.g. Claude Desktop, [5ire](https://5ire.app)) and other MCP-compatible clients.

🎯 **Key Features**

* Standard MCP interface for programmatic access to the Czech e-Sbírka legislation system.
* 3 specialized tools covering the complete legislation access workflow:
    * **Search** — Find laws by number, keyword, article reference, or legal concept
    * **Full Text** — Retrieve complete law texts as formatted Markdown with cross-reference links
    * **Article Lookup** — Extract specific sections (§) or articles (čl.) without downloading entire laws
* Comprehensive legal corpus coverage:
    * **Zákony (Laws)** — Acts of Parliament
    * **Ústavní zákony (Constitutional Acts)** — Constitutional laws including the Constitution
    * **Nařízení (Government Regulations)** — Government regulatory instruments
    * **Vyhlášky (Decrees)** — Ministerial and agency decrees
    * **Nálezy Ústavního soudu (Constitutional Court Findings)** — Court decisions
    * **Mezinárodní smlouvy (International Treaties)** — Treaties and conventions
* Advanced features:
    * XHTML-to-Markdown conversion with proper heading hierarchy (Parts, Titles, Sections)
    * Cross-reference resolution — links to other laws converted to clickable URLs
    * In-memory caching (1-hour TTL) for fast repeated access
    * Pagination support for large documents (e.g. Civil Code with 3000+ sections)
    * Multiple article notation formats: § 138, čl. 95, bare numbers
    * Historical legislation back to 1848 (Říšský zákoník)
* Easy integration with Claude Desktop, 5ire, and other MCP clients

---

🌐 **Easiest Way: Free Remote MCP (for Claude Desktop)**

No installation required — ready to use directly:

1. Open Claude Desktop
2. **Settings > Connectors > Add custom connector**
3. In the dialog:
   * **Name:** `Sbírka MCP`
   * **URL:** `https://sbirka-mcp.fastmcp.app/mcp`
4. Click **Save**

That's it! You can now search Czech legislation through Claude.

> **Note:** This free server is provided for the community. For heavy usage, consider running your own instance.

---

🚀 **Easy Setup for Non-Claude MCP Clients (e.g. 5ire)**

This section is for using Sbírka MCP with MCP clients other than Claude Desktop, such as 5ire.

* **Python:** Python 3.10 or higher must be installed. Make sure to check "**Add Python to PATH**" during installation. [Download here](https://www.python.org/downloads/).
* **Git (Windows):** Install [git](https://git-scm.com/downloads/win) — download the "Git for Windows/x64 Setup" option.
* **`uv` Installation:**
    * **Windows (PowerShell):** Open CMD and run: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    * **Mac/Linux (Terminal):** Open Terminal and run: `curl -LsSf https://astral.sh/uv/install.sh | sh`
* Install [5ire](https://5ire.app) for your operating system.
* Open 5ire. Go to **Workspace -> Providers** and enter your LLM API key.
* Go to **Tools** menu. Click **+Local** or **New**.
    * **Tool Key:** `sbirkamcp`
    * **Name:** `Sbírka MCP`
    * **Command:**
        ```
        uvx --from git+https://github.com/saidsurucu/sbirka-mcp sbirka-mcp
        ```
    * Click **Save**.
* Under **Tools**, you should now see **Sbírka MCP**. Click the toggle to enable it (green light).
* You can now search Czech legislation!

---

⚙️ **Claude Desktop Manual Setup**

1.  **Prerequisites:** Ensure Python and `uv` are installed. See the "Easy Setup" section above for details.
2.  Claude Desktop **Settings -> Developer -> Edit Config**.
3.  Add the following under `mcpServers` in the `claude_desktop_config.json` file:

    ```json
    {
      "mcpServers": {
        "Sbírka MCP": {
          "command": "uvx",
          "args": [
            "--from",
            "git+https://github.com/saidsurucu/sbirka-mcp",
            "sbirka-mcp"
          ]
        }
      }
    }
    ```
4.  Restart Claude Desktop.

---

🛠️ **Available Tools (MCP Tools)**

This FastMCP server provides **3 tools** for LLM models:

### 1. `search_czech_legislation`

Search the Czech legal corpus by law number, keyword, article reference, or legal concept.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query. Accepts law numbers (`40/2009`), Czech keywords (`trestní zákoník`), article references (`40/2009 § 138`), or legal concepts (`trestní právo`) |
| `start` | int | No | 0 | Pagination offset (0-based) for full-text results |
| `count` | int | No | 25 | Number of results per page (max 100) |

**Returns:** Markdown-formatted list of matching documents, articles, and legal concepts with their `staleUrl` identifiers.

**Examples:**
```
search_czech_legislation("40/2009")           → Criminal Code (Trestní zákoník)
search_czech_legislation("daň z příjmů")      → Income Tax Act and related laws
search_czech_legislation("40/2009 § 138")      → Section 138 of the Criminal Code
search_czech_legislation("občanský zákoník")   → Civil Code (89/2012 Sb.)
```

### 2. `get_czech_law_text`

Retrieve the full text of a Czech law as formatted Markdown with metadata and cross-reference links.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `stale_url` | string | Yes | — | Document identifier from search results (e.g. `/sb/2009/40` or `/sb/2009/40/2026-01-01`) |
| `max_pages` | int | No | 30 | Maximum fragment pages to fetch. Large laws may need higher values. Set to 1-2 for quick previews |

**Returns:** Full document text as Markdown with heading hierarchy (Parts → Titles → Sections → Articles), metadata header, and cross-references as clickable links.

**Examples:**
```
get_czech_law_text("/sb/2009/40")              → Full Criminal Code text
get_czech_law_text("/sb/1993/1")               → Constitution of the Czech Republic
get_czech_law_text("/sb/2012/89", max_pages=1) → Civil Code preview (first page only)
```

### 3. `get_czech_law_article`

Retrieve a specific section (§) or article (čl.) from a Czech law with all subsections.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `stale_url` | string | Yes | — | Document identifier from search results |
| `article` | string | Yes | — | Article identifier: `§ 138`, `§138`, `čl. 95`, `cl. 95`, or bare number `138` |

**Returns:** The specific article with its heading, all numbered subsections (odstavce), lettered points, and cross-references as Markdown.

**Examples:**
```
get_czech_law_article("/sb/2009/40", "§ 138")  → Damage thresholds in Criminal Code
get_czech_law_article("/sb/1993/1", "čl. 95")  → Judicial independence (Constitution)
get_czech_law_article("/sb/2012/89", "1")       → Section 1 of the Civil Code
```

### Typical Workflow

1. **Search** for a law: `search_czech_legislation("trestní zákoník")`
2. Get the `staleUrl` from results: `/sb/2009/40`
3. **Read full text**: `get_czech_law_text("/sb/2009/40")` — or —
4. **Read specific article**: `get_czech_law_article("/sb/2009/40", "§ 138")`

### Understanding `staleUrl`

The `staleUrl` is the permanent identifier for each document in e-Sbírka:

| Format | Meaning | Example |
|--------|---------|---------|
| `/sb/{year}/{number}` | Latest version of a law | `/sb/2009/40` (Criminal Code, latest) |
| `/sb/{year}/{number}/{date}` | Specific version by effective date | `/sb/2009/40/2026-01-01` |
| `/sm/{year}/{number}` | International treaty | `/sm/2009/40` |

* `sb` = Sbírka zákonů (Collection of Laws)
* `sm` = Sbírka mezinárodních smluv (International Treaties)
* URLs without a date automatically resolve to the latest effective version

---

📜 **License**

This project is licensed under the MIT License. See the `LICENSE` file for details.
