from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchContext, MetadataSearchResult, search_metadata
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument, retrieve_documents
from legacydb_copilot.services.llm_invocation_audit_service import InvocationContext
from legacydb_copilot.services.metadata_catalog_service import active_snapshot, schema_metadata_from_catalog


@dataclass(frozen=True)
class DiscoveredContext:
    metadata: MetadataSearchResult
    documents: list[RetrievedDocument]


def discover_context(
    connector,
    db: Session,
    organization_id: str,
    workspace_id: str,
    question: str,
    entities: EntityExtractionResult,
    metadata_context: MetadataSearchContext | None = None,
    schema_metadata=None,
    audit_context: InvocationContext | None = None,
) -> DiscoveredContext:
    """
    Owner: Mukesh Dabi
    Purpose:
        Discovers database metadata and workspace knowledge relevant to the current question.

    Input:
        Active database connector, app database session, workspace identifiers, user question, and extracted entities.

    Output:
        DiscoveredContext containing ranked metadata and retrieved documents/knowledge chunks.

    Called by:
        Main /chat/ask investigation orchestration before object ranking and safe SQL planning.

    Flow:
        Entity Extraction -> Metadata Discovery + Knowledge Retrieval -> Investigation Planner.

    Safety:
        Metadata and knowledge retrieval are read-only. Customer database rows are not embedded or sent to the
        knowledge retriever; live evidence collection happens later through validated SQL.
    """

    if schema_metadata is None and metadata_context is not None:
        snapshot = active_snapshot(db, organization_id=organization_id, workspace_id=workspace_id, connection_id=metadata_context.connection_id)
        if snapshot is not None:
            schema_metadata = schema_metadata_from_catalog(db, snapshot)
    metadata = search_metadata(connector, question, entities, context=metadata_context, schema_metadata=schema_metadata)
    documents = retrieve_documents(
        db, organization_id, workspace_id, question, audit_context=audit_context
    )
    return DiscoveredContext(metadata=metadata, documents=documents)
