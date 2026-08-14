from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.domain.schemas import SearchCitation


@dataclass(slots=True)
class KnowledgeDocument:
    title: str
    source: str
    content: str
    tags: tuple[str, ...]


class LocalKnowledgeBase:
    """Small auditable lexical retriever used for the offline competition demo.

    The retrieval interface is deliberately provider-neutral so it can be replaced
    by a vector store, knowledge graph, or enterprise document system.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.documents: list[KnowledgeDocument] = []
        self.reload()

    def reload(self) -> None:
        self.documents.clear()
        if not self.root.exists():
            return
        for path in sorted(self.root.glob("**/*.md")):
            raw = path.read_text(encoding="utf-8")
            title = raw.splitlines()[0].lstrip("# ").strip() if raw else path.stem
            tags_match = re.search(r"^tags:\s*(.+)$", raw, flags=re.MULTILINE)
            tags = tuple(t.strip() for t in tags_match.group(1).split(",")) if tags_match else ()
            self.documents.append(
                KnowledgeDocument(title=title, source=str(path), content=raw, tags=tags)
            )

    def search(self, query: str, limit: int = 5) -> list[SearchCitation]:
        tokens = {token.lower() for token in re.findall(r"[\w\-]+", query) if len(token) > 2}
        scored: list[tuple[float, KnowledgeDocument]] = []
        for doc in self.documents:
            haystack = f"{doc.title} {' '.join(doc.tags)} {doc.content}".lower()
            overlap = sum(1 for token in tokens if token in haystack)
            tag_bonus = sum(0.75 for token in tokens if token in {tag.lower() for tag in doc.tags})
            if overlap:
                scored.append((overlap + tag_bonus, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[SearchCitation] = []
        for _, doc in scored[:limit]:
            snippet = " ".join(doc.content.replace("#", "").split())[:320]
            results.append(
                SearchCitation(
                    title=doc.title,
                    url=f"file://{doc.source}",
                    snippet=snippet,
                    source="local-knowledge",
                )
            )
        return results
