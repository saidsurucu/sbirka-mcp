"""API client for Czech e-Sbírka legislation system."""

import re
import time
from html import unescape
from urllib.parse import quote

import httpx

BASE_URL = "https://www.e-sbirka.cz/sbr-cache"


class SimpleCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._data: dict[str, tuple] = {}
        self._ttl = ttl_seconds

    def get(self, key: str):
        if key in self._data:
            value, ts = self._data[key]
            if time.time() - ts < self._ttl:
                return value
            del self._data[key]
        return None

    def set(self, key: str, value):
        self._data[key] = (value, time.time())


class SbirkaClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "User-Agent": "sbirka-mcp/1.0",
            },
            verify=True,
        )
        self._cache = SimpleCache()

    async def close(self):
        await self._client.aclose()

    # ── API Methods ────────────────────────────────────────────────

    async def autocomplete(self, text: str, max_count: int = 15) -> dict:
        key = f"ac:{text}:{max_count}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        resp = await self._client.get(
            "/jednoducha-vyhledavani/nabidka",
            params={"text": text, "maxPocet": max_count},
        )
        resp.raise_for_status()
        data = resp.json()
        self._cache.set(key, data)
        return data

    async def fulltext_search(
        self,
        query: str,
        start: int = 0,
        count: int = 25,
        filters: dict | None = None,
    ) -> dict:
        key = f"fs:{query}:{start}:{count}:{filters}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        body: dict = {
            "fulltext": query,
            "start": start,
            "pocet": count,
            "razeni": ["+relevance"],
        }
        if filters:
            body["fazetovyFiltr"] = filters
        resp = await self._client.post(
            "/jednoducha-vyhledavani",
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        self._cache.set(key, data)
        return data

    async def get_metadata(self, stale_url: str) -> dict:
        key = f"meta:{stale_url}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        encoded = quote(stale_url, safe="")
        resp = await self._client.get(f"/dokumenty-sbirky/{encoded}")
        resp.raise_for_status()
        data = resp.json()
        self._cache.set(key, data)
        return data

    async def get_fragments(self, stale_url: str, page: int = 0) -> dict:
        key = f"frag:{stale_url}:{page}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        encoded = quote(stale_url, safe="")
        resp = await self._client.get(
            f"/dokumenty-sbirky/{encoded}/fragmenty",
            params={"cisloStranky": page},
        )
        resp.raise_for_status()
        data = resp.json()
        self._cache.set(key, data)
        return data

    async def get_all_fragments(
        self, stale_url: str, max_pages: int = 30
    ) -> list[dict]:
        first = await self.get_fragments(stale_url, 0)
        all_fragments = list(first.get("seznam", []))
        total_pages = first.get("pocetStranek", 1)
        pages_to_fetch = min(total_pages, max_pages)

        for page in range(1, pages_to_fetch):
            data = await self.get_fragments(stale_url, page)
            all_fragments.extend(data.get("seznam", []))

        return all_fragments

    # ── XHTML → Markdown ──────────────────────────────────────────

    @staticmethod
    def _resolve_cross_references(xhtml: str, odkazy: list) -> str:
        if not odkazy:
            return xhtml
        for o in odkazy:
            odkaz_id = str(o.get("odkazId", ""))
            cil = o.get("cil") or {}
            target = cil.get("staleUrl", "")
            if not odkaz_id or not target:
                continue
            full_url = f"https://www.e-sbirka.cz{target}"
            pattern = rf'<a[^>]*data-odkaz-id="{re.escape(odkaz_id)}"[^>]*>(.*?)</a>'
            xhtml = re.sub(pattern, rf"[\1]({full_url})", xhtml)
        return xhtml

    @staticmethod
    def _xhtml_to_markdown(xhtml: str, odkazy: list | None = None) -> str:
        if not xhtml:
            return ""
        text = SbirkaClient._resolve_cross_references(xhtml, odkazy or [])
        # Convert known HTML elements
        text = re.sub(r"<em>(.*?)</em>", r"*\1*", text)
        text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)
        text = re.sub(r"<var>(.*?)</var>", r"\1", text)
        text = re.sub(
            r"<czechvoc-termin[^>]*>(.*?)</czechvoc-termin>", r"\1", text
        )
        text = re.sub(r"<sup>(.*?)</sup>", r"^\1^", text)
        text = re.sub(r"<br\s*/?>", "\n", text)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        # Clean whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Fragment → Markdown ───────────────────────────────────────

    DEPTH_TO_HEADING = {
        0: "#",
        1: "##",
        2: "###",
        3: "####",
        4: "#####",
        5: "######",
    }

    # Fragment types that serve as structural headings
    HEADING_TYPES = {
        "Virtual_Document",
        "Virtual_Prefix",
        "Virtual_Norma",
        "Virtual_Postfix",
        "Cast",
        "Hlava",
        "Dil",
        "Oddil",
        "Paragraf",
        "Clanek",
        "Nadpis_nad",
        "Nadpis_pod",
        "Prefix_Number",
        "Prefix_Type",
        "Prefix_Author",
        "Block_Citace",
        "Block_Nalez_rozhodnuti",
        "Block_Nalez_oduvodneni",
        "Block_Predpis_Obecny",
    }

    def _fragment_to_markdown(self, fragment: dict) -> str:
        xhtml = fragment.get("xhtml", "")
        if not xhtml:
            return ""

        odkazy = fragment.get("odkazyZFragmentu", [])
        body = self._xhtml_to_markdown(xhtml, odkazy)
        if not body:
            return ""

        depth = fragment.get("hloubka", 0)
        ftype = fragment.get("kodTypuFragmentu", "")

        if ftype in self.HEADING_TYPES:
            prefix = self.DEPTH_TO_HEADING.get(depth, "")
            if prefix:
                citation = fragment.get("uplnaCitace", "")
                if citation and citation != body:
                    return f"{prefix} {body}\n"
                return f"{prefix} {body}\n"

        return f"{body}\n"

    def fragments_to_markdown(self, fragments: list[dict]) -> str:
        parts = []
        for f in fragments:
            md = self._fragment_to_markdown(f)
            if md:
                parts.append(md)
        return "\n".join(parts)

    # ── Article Search ────────────────────────────────────────────

    @staticmethod
    def _normalize_article_id(article: str) -> tuple[str, str]:
        """Return (type, number) from input like '§ 138' or 'čl. 95'."""
        article = article.strip()
        # § 138 / §138
        m = re.match(r"§\s*(\d+\w*)", article)
        if m:
            return ("par", m.group(1))
        # čl. 95 / cl. 95 / Čl. 95
        m = re.match(r"[čČcC]l\.?\s*(\d+\w*)", article, re.IGNORECASE)
        if m:
            return ("cl", m.group(1))
        # Bare number
        m = re.match(r"(\d+\w*)", article)
        if m:
            return ("par", m.group(1))
        return ("par", article)

    def find_article_in_fragments(
        self, fragments: list[dict], article: str
    ) -> str:
        art_type, art_num = self._normalize_article_id(article)

        # Build anchor pattern: #par_138 or #cl_95
        anchor = f"#{art_type}_{art_num}"

        # Find the target fragment and collect its children
        collecting = False
        target_depth = -1
        result_parts: list[str] = []

        for f in fragments:
            stale = f.get("staleUrl", "")
            depth = f.get("hloubka", 0)

            if anchor in stale:
                collecting = True
                target_depth = depth
                md = self._fragment_to_markdown(f)
                if md:
                    result_parts.append(md)
                continue

            if collecting:
                if depth <= target_depth:
                    break
                md = self._fragment_to_markdown(f)
                if md:
                    result_parts.append(md)

        if result_parts:
            return "\n".join(result_parts)

        # Fallback: search by text content
        search_patterns = [
            f"§ {art_num}",
            f"§{art_num}",
            f"čl. {art_num}",
            f"Čl. {art_num}",
        ]
        for f in fragments:
            xhtml = f.get("xhtml", "")
            if any(p in xhtml for p in search_patterns):
                ftype = f.get("kodTypuFragmentu", "")
                if ftype in ("Paragraf", "Clanek"):
                    collecting = True
                    target_depth = f.get("hloubka", 0)
                    md = self._fragment_to_markdown(f)
                    if md:
                        result_parts.append(md)
                    idx = fragments.index(f)
                    for child in fragments[idx + 1 :]:
                        if child.get("hloubka", 0) <= target_depth:
                            break
                        md = self._fragment_to_markdown(child)
                        if md:
                            result_parts.append(md)
                    break

        if result_parts:
            return "\n".join(result_parts)

        return f"Article {article} not found in document fragments."
