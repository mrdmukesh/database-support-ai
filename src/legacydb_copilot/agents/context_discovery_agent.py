from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, search_metadata
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument, retrieve_documents


@dataclass(frozen=True)
class DiscoveredContext:
    metadata: MetadataSearchResult
    documents: list[RetrievedDocument]


def discover_context(connector, db: Session, organization_id: str, workspace_id: str, question: str, entities: EntityExtractionResult) -> DiscoveredContext:
    metadata = search_metadata(connector, question, entities)
    documents = retrieve_documents(db, organization_id, workspace_id, question)
    return DiscoveredContext(metadata=metadata, documents=documents)
