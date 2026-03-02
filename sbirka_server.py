"""FastMCP server for Czech e-Sbírka legislation system."""

from fastmcp import FastMCP, Context
from pydantic import Field

from sbirka_client import SbirkaClient

mcp = FastMCP(
    "sbirka-mcp",
    instructions=(
        "Czech Republic legislation search and retrieval via the official "
        "e-Sbírka system (e-sbirka.cz). This server provides access to the "
        "complete Czech legal corpus including laws (zákony), constitutional acts, "
        "government regulations (nařízení), decrees (vyhlášky), international treaties, "
        "and Constitutional Court findings (nálezy Ústavního soudu).\n\n"
        "Typical workflow:\n"
        "1. Use search_czech_legislation to find documents by number, keyword, or article reference.\n"
        "2. Use the returned staleUrl with get_czech_law_text to retrieve the full text.\n"
        "3. Use get_czech_law_article to retrieve a specific section (§) or article (čl.) "
        "without downloading the entire law.\n\n"
        "The staleUrl is the permanent identifier for each document "
        "(e.g. '/sb/2009/40' for law 40/2009 Sb., '/sb/2009/40/2026-01-01' for a specific version). "
        "URLs without a date return the latest effective version."
    ),
)

client = SbirkaClient()


@mcp.tool()
async def search_czech_legislation(
    query: str = Field(
        description=(
            "Search query for Czech legislation. Accepts multiple formats:\n"
            "- Law number: '40/2009' (returns Criminal Code 40/2009 Sb.)\n"
            "- Law number with collection: '40/2009 Sb.' or '1/1993 Sb.' (Constitution)\n"
            "- Czech keyword: 'trestní zákoník', 'daň z příjmů', 'občanský zákoník'\n"
            "- Article reference: '40/2009 § 138' (specific section within a law)\n"
            "- Legal concept: 'trestní právo', 'ochrana spotřebitele'\n"
            "- English keyword: 'criminal code', 'tax' (limited support)\n"
            "The query is matched against document titles, article headings, "
            "and the CzechVoc/EuroVoc legal taxonomy."
        )
    ),
    start: int = Field(
        default=0,
        description=(
            "Pagination offset for full-text results (0-based). "
            "Use this to page through large result sets. "
            "For example, start=25 with count=25 returns results 26-50."
        ),
    ),
    count: int = Field(
        default=25,
        description=(
            "Number of full-text results to return per page (max 100). "
            "Default 25 is suitable for most queries. Use smaller values "
            "for quick lookups, larger for comprehensive searches."
        ),
    ),
) -> str:
    """Search Czech legislation in the e-Sbírka database.

    Combines autocomplete (exact matches by law number/title) with full-text search
    (keyword matching across the entire legal corpus). Returns matching documents with
    their citation codes, titles, validity status, and staleUrl identifiers needed
    for get_czech_law_text and get_czech_law_article.

    Results include three categories:
    - Matching Documents: exact law/regulation matches with permanent staleUrl
    - Matching Articles/Provisions: specific sections (§) or articles (čl.) with deep links
    - Full-Text Results: broader keyword matches with status and effective date info
    """
    parts: list[str] = []

    # 1. Autocomplete — quick exact matches
    try:
        ac = await client.autocomplete(query)

        docs = ac.get("seznamDokumentuSbirky", [])
        if docs:
            parts.append("## Matching Documents\n")
            for d in docs:
                code = d.get("kodDokumentuSbirky", "")
                name = d.get("nazev", "")
                url = d.get("staleUrl", "")
                parts.append(f"- **{code}** — {name}  \n  `staleUrl: {url}`")
            parts.append("")

        provisions = ac.get("seznamNalezenychUstanoveni", [])
        if provisions:
            parts.append("## Matching Articles/Provisions\n")
            for p in provisions:
                ident = p.get("identifikaceUstanoveni", "")
                name = p.get("nazev", "")
                url = p.get("staleUrl", "")
                parts.append(f"- **{ident}** — {name}  \n  `staleUrl: {url}`")
            parts.append("")

        concepts = ac.get("seznamKonceptu", [])
        if concepts:
            parts.append("## Related Legal Concepts\n")
            for c in concepts:
                label = c.get("preferovanyTerminTextNazvu", "")
                parts.append(f"- {label}")
            parts.append("")
    except Exception:
        pass  # autocomplete failure is non-critical

    # 2. Full-text search
    try:
        ft = await client.fulltext_search(query, start=start, count=count)
        total = ft.get("pocetCelkem", 0)
        results = ft.get("seznam", [])

        if results:
            parts.append(f"## Full-Text Results ({total} total)\n")
            for r in results:
                code = r.get("kodDokumentuSbirky", "")
                name = r.get("nazev", "")
                url = r.get("staleUrl", "")
                status = r.get("stavDokumentuSbirky", "")
                effective = r.get("datumUcinnostiZneniOd", "")
                status_label = {
                    "AKTUALNE_PLATNY": "Currently valid",
                    "PLATNY": "Valid",
                    "ZRUSENY": "Repealed",
                    "CASOVE_NEAKTIVNI": "Inactive",
                }.get(status, status)
                parts.append(
                    f"- **{code}** — {name}  \n"
                    f"  Status: {status_label} | Effective: {effective}  \n"
                    f"  `staleUrl: {url}`"
                )

            if total > start + count:
                parts.append(
                    f"\n*Showing {start + 1}–{start + len(results)} of {total}. "
                    f"Use start={start + count} for next page.*"
                )
    except Exception as e:
        parts.append(f"Full-text search error: {e}")

    if not parts:
        return f"No results found for '{query}'."

    return "\n".join(parts)


@mcp.tool()
async def get_czech_law_text(
    stale_url: str = Field(
        description=(
            "Permanent document identifier (staleUrl) obtained from search_czech_legislation results. "
            "Format: '/sb/{year}/{number}' for the latest version, or "
            "'/sb/{year}/{number}/{date}' for a specific version.\n"
            "Examples:\n"
            "- '/sb/2009/40' — Criminal Code (latest version)\n"
            "- '/sb/2009/40/2026-01-01' — Criminal Code as effective on 2026-01-01\n"
            "- '/sb/1993/1' — Constitution of the Czech Republic\n"
            "- '/sb/2012/89' — Civil Code (občanský zákoník)\n"
            "- '/sm/2009/40' — international treaty (Sbírka mezinárodních smluv)\n"
            "Note: URLs without a date automatically resolve to the latest effective version."
        )
    ),
    max_pages: int = Field(
        default=30,
        description=(
            "Maximum number of fragment pages to fetch. Each page contains up to 1000 fragments. "
            "Large laws like the Criminal Code (5 pages) or Civil Code (10+ pages) may require "
            "higher values. Default 30 covers virtually all documents. "
            "Set lower (e.g. 1-2) for quick previews of very large laws."
        ),
    ),
) -> str:
    """Retrieve the full text of a Czech law, regulation, or legal document as formatted Markdown.

    Fetches document metadata (citation, status, effective date, ELI identifier) and the complete
    text content with proper heading hierarchy (Parts, Titles, Sections, Articles). Cross-references
    to other laws are converted to clickable links. Use the staleUrl from search_czech_legislation results.

    For very large documents (e.g. Civil Code with 3000+ sections), consider using
    get_czech_law_article instead to retrieve only the specific section you need.
    """
    parts: list[str] = []

    # Metadata
    try:
        meta = await client.get_metadata(stale_url)
        citation = meta.get("uplnaCitace") or meta.get("zkracenaCitace", "")
        code = meta.get("kodDokumentuSbirky", "")
        status = meta.get("stavDokumentuSbirky", "")
        effective = meta.get("datumUcinnostiZneniOd", "")
        eli = meta.get("eli", "")

        parts.append(f"# {code} — {citation}\n")
        status_label = {
            "AKTUALNE_PLATNY": "Currently valid",
            "PLATNY": "Valid",
            "ZRUSENY": "Repealed",
            "CASOVE_NEAKTIVNI": "Inactive",
        }.get(status, status)
        parts.append(
            f"**Status:** {status_label} | **Effective:** {effective} | "
            f"**ELI:** {eli}\n"
        )
        parts.append("---\n")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Document not found: {stale_url}"
        return f"Error fetching metadata: {e}"

    # Fragments
    try:
        fragments = await client.get_all_fragments(stale_url, max_pages)
        if fragments:
            md = client.fragments_to_markdown(fragments)
            parts.append(md)
        else:
            parts.append("*No content fragments available for this document.*")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            parts.append("*Content fragments not available.*")
        else:
            parts.append(f"Error fetching content: {e}")

    return "\n".join(parts)


@mcp.tool()
async def get_czech_law_article(
    stale_url: str = Field(
        description=(
            "Permanent document identifier (staleUrl) for the law containing the article. "
            "Obtained from search_czech_legislation results.\n"
            "Examples:\n"
            "- '/sb/2009/40' — Criminal Code\n"
            "- '/sb/2009/40/2026-01-01' — Criminal Code, specific version\n"
            "- '/sb/1993/1' — Constitution"
        )
    ),
    article: str = Field(
        description=(
            "The specific article or section identifier to retrieve. "
            "Supports multiple Czech legal notation formats:\n"
            "- Section (paragraf): '§ 138', '§138', or just '138'\n"
            "- Article (článek): 'čl. 95', 'Čl. 95', 'cl. 95'\n"
            "Czech laws use § (paragraf) for sections in regular laws, "
            "and čl. (článek) for articles in constitutional acts and amendments.\n"
            "Examples:\n"
            "- '§ 138' — Section 138 of a law (e.g. Criminal Code damage thresholds)\n"
            "- '§ 1' — Section 1 (typically the opening provision)\n"
            "- 'čl. 95' — Article 95 (e.g. Constitution, judicial independence)\n"
            "- '13' — Bare number, interpreted as § 13"
        )
    ),
) -> str:
    """Retrieve a specific section (§) or article (čl.) from a Czech law with all its subsections.

    This is more efficient than get_czech_law_text for large laws when you only need one provision.
    The tool first attempts to locate the article via autocomplete for an exact match, then falls
    back to scanning document fragments. Returns the article heading, all numbered subsections
    (odstavce), lettered points, and any cross-references as Markdown links.
    """
    # Try autocomplete first for direct article URL
    try:
        query = stale_url.split("/")
        # Extract law number pattern like "40/2009"
        if len(query) >= 4:
            law_num = f"{query[3]}/{query[2]}"
            ac = await client.autocomplete(f"{law_num} {article}")
            provisions = ac.get("seznamNalezenychUstanoveni", [])
            if provisions:
                # Found direct match — use its versioned staleUrl
                prov = provisions[0]
                prov_url = prov.get("staleUrl", "")
                if prov_url and "#" in prov_url:
                    # Extract base URL (without anchor) for fetching fragments
                    base_url = prov_url.split("#")[0]
                    stale_url = base_url
    except Exception:
        pass

    # Fetch fragments and search for article
    try:
        fragments = await client.get_all_fragments(stale_url)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Document not found: {stale_url}"
        return f"Error fetching document: {e}"

    if not fragments:
        return f"No content available for {stale_url}."

    result = client.find_article_in_fragments(fragments, article)

    # Add metadata header
    try:
        meta = await client.get_metadata(stale_url)
        code = meta.get("kodDokumentuSbirky", "")
        citation = meta.get("zkracenaCitace", "")
        header = f"**{code}** — {citation}\n\n---\n\n"
        return header + result
    except Exception:
        return result


if __name__ == "__main__":
    mcp.run()
