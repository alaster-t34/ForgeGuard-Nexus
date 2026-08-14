from __future__ import annotations

import asyncio
from collections.abc import Iterable
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.domain.schemas import SearchCitation, SearchResult
from app.services.knowledge import LocalKnowledgeBase


class SearchPolicyError(RuntimeError):
    pass


class SearchBroker:
    """Policy-controlled federated research and web search gateway.

    The broker offers broad read access while keeping network scope, timeouts,
    result counts, citations, and query purpose auditable. It never exposes shell
    execution, private-network access, cookies, or arbitrary credentials to agents.
    """

    ALLOWED_SCHEMES = {"http", "https"}
    ACADEMIC_HOSTS = {"api.openalex.org", "api.crossref.org"}
    VALID_SCOPES = {"internal", "academic", "web", "all"}

    def __init__(self, settings: Settings, knowledge: LocalKnowledgeBase) -> None:
        self.settings = settings
        self.knowledge = knowledge

    async def search(
        self,
        query: str,
        *,
        purpose: str,
        max_results: int | None = None,
        scope: str = "all",
    ) -> SearchResult:
        query = query.strip()
        scope = scope.strip().lower()
        if not query:
            raise SearchPolicyError("Search query cannot be empty")
        if len(query) > 500:
            raise SearchPolicyError("Search query exceeds policy limit")
        if scope not in self.VALID_SCOPES:
            raise SearchPolicyError(f"Unsupported search scope: {scope}")
        limit = min(max_results or self.settings.search_max_results, 12)

        citations: list[SearchCitation] = []
        providers: list[str] = []
        if scope in {"internal", "all"}:
            citations.extend(self.knowledge.search(query, limit=limit))
            providers.append("controlled-knowledge")

        if self.settings.allow_external_search and scope in {"academic", "all"}:
            academic = await self._gather_safe(
                self._search_openalex(query, limit=limit),
                self._search_crossref(query, limit=limit),
            )
            citations.extend(item for group in academic for item in group)
            providers.extend(["openalex", "crossref"])

        if (
            self.settings.allow_external_search
            and scope in {"web", "all"}
            and self.settings.search_provider == "searxng"
            and self.settings.searxng_base_url
        ):
            citations.extend(await self._search_searxng(query, limit=limit))
            providers.append("searxng")

        citations = self._deduplicate(citations)[:limit]
        if not providers:
            providers.append("offline-policy")
        return SearchResult(
            query=query,
            citations=citations,
            provider="+".join(providers),
            policy_notes=[
                "Read-only retrieval with citation retention",
                "No shell, cookie, secret, or private-network access",
                f"Scope: {scope}",
                f"Purpose recorded: {purpose}",
                f"External search: {'enabled' if self.settings.allow_external_search else 'disabled'}",
            ],
        )

    async def _gather_safe(self, *calls) -> list[list[SearchCitation]]:
        results = await asyncio.gather(*calls, return_exceptions=True)
        output: list[list[SearchCitation]] = []
        for result in results:
            output.append([] if isinstance(result, Exception) else result)
        return output

    async def _search_openalex(self, query: str, limit: int) -> list[SearchCitation]:
        url = "https://api.openalex.org/works"
        self._assert_allowed_academic_url(url)
        async with httpx.AsyncClient(timeout=self.settings.search_timeout_seconds) as client:
            response = await client.get(
                url,
                params={"search": query, "per-page": min(limit, 10), "select": "id,display_name,publication_year,doi,primary_location"},
                headers={"User-Agent": "ForgeGuard-Nexus/0.1 (research search)"},
            )
            response.raise_for_status()
            payload = response.json()
        citations: list[SearchCitation] = []
        for item in payload.get("results", []):
            location = item.get("primary_location") or {}
            target = item.get("doi") or location.get("landing_page_url") or item.get("id")
            if not target:
                continue
            citations.append(
                SearchCitation(
                    title=item.get("display_name", "Untitled research work"),
                    url=target,
                    snippet=f"Publication year: {item.get('publication_year') or 'unknown'}",
                    source="OpenAlex",
                    published_at=str(item.get("publication_year")) if item.get("publication_year") else None,
                )
            )
        return citations

    async def _search_crossref(self, query: str, limit: int) -> list[SearchCitation]:
        url = "https://api.crossref.org/works"
        self._assert_allowed_academic_url(url)
        async with httpx.AsyncClient(timeout=self.settings.search_timeout_seconds) as client:
            response = await client.get(
                url,
                params={"query": query, "rows": min(limit, 10), "select": "DOI,title,published,URL,abstract"},
                headers={"User-Agent": "ForgeGuard-Nexus/0.1 (mailto:replace-with-project-contact)"},
            )
            response.raise_for_status()
            payload = response.json()
        citations: list[SearchCitation] = []
        for item in payload.get("message", {}).get("items", []):
            title = (item.get("title") or ["Untitled research work"])[0]
            date_parts = ((item.get("published") or {}).get("date-parts") or [[]])[0]
            published = "-".join(str(value) for value in date_parts) if date_parts else None
            abstract = " ".join(str(item.get("abstract", "")).replace("<jats:p>", "").replace("</jats:p>", "").split())
            citations.append(
                SearchCitation(
                    title=title,
                    url=item.get("URL") or f"https://doi.org/{item.get('DOI')}",
                    snippet=abstract[:420] or f"DOI: {item.get('DOI', 'not provided')}",
                    source="Crossref",
                    published_at=published,
                )
            )
        return citations

    async def _search_searxng(self, query: str, limit: int) -> list[SearchCitation]:
        assert self.settings.searxng_base_url
        parsed = urlparse(self.settings.searxng_base_url)
        if parsed.scheme not in self.ALLOWED_SCHEMES or not parsed.hostname:
            raise SearchPolicyError("Invalid SearXNG endpoint")
        async with httpx.AsyncClient(timeout=self.settings.search_timeout_seconds) as client:
            response = await client.get(
                self.settings.searxng_base_url.rstrip("/") + "/search",
                params={"q": query, "format": "json", "safesearch": 1},
                headers={"User-Agent": "ForgeGuard-Nexus/0.1"},
            )
            response.raise_for_status()
            payload = response.json()
        return [
            SearchCitation(
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                snippet=item.get("content", "")[:500],
                source=item.get("engine", "SearXNG"),
                published_at=item.get("publishedDate"),
            )
            for item in payload.get("results", [])[:limit]
            if item.get("url")
        ]

    def _assert_allowed_academic_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.ACADEMIC_HOSTS:
            raise SearchPolicyError(f"Academic provider is not allowlisted: {url}")

    @staticmethod
    def _deduplicate(items: Iterable[SearchCitation]) -> list[SearchCitation]:
        output: list[SearchCitation] = []
        seen: set[str] = set()
        for item in items:
            key = item.url.rstrip("/").lower() or item.title.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
        return output
