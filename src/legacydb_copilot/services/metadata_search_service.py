from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult


@dataclass(frozen=True)
class TableMetadata:
    name: str
    columns: list[str]
    score: int
    primary_key: list[str] | None = None
    foreign_keys: list[dict[str, Any]] | None = None
    indexes: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class MetadataSearchResult:
    tables: list[TableMetadata]
    views: list[str]
    procedures: list[str]
    version: str
    engine_type: str | None = None


def _tokens(question: str, entities: EntityExtractionResult) -> set[str]:
    raw = question.lower().replace("_", " ").replace("-", " ").split()
    tokens = {token.strip(".,:;()[]{}") for token in raw if len(token.strip(".,:;()[]{}")) >= 3}
    for entity in entities.entities:
        tokens.update(entity.value.lower().replace("-", " ").split())
    if entities.likely_module:
        tokens.add(entities.likely_module.lower())
    if entities.suspected_issue:
        tokens.update(entities.suspected_issue.lower().split())
    return tokens


def search_metadata(connector, question: str, entities: EntityExtractionResult) -> MetadataSearchResult:
    metadata = connector.get_schema_metadata()
    tokens = _tokens(question, entities)
    tables: list[TableMetadata] = []
    for table_name in metadata.tables:
        try:
            schema = connector.get_table_schema(table_name)
            columns = [column["name"] for column in schema["columns"]]
            primary_key = schema.get("primary_key", [])
            foreign_keys = schema.get("foreign_keys", [])
            indexes = schema.get("indexes", [])
        except Exception:
            columns = []
            primary_key = []
            foreign_keys = []
            indexes = []
        haystack = {table_name.lower(), *[column.lower() for column in columns]}
        score = sum(1 for token in tokens if any(token in item for item in haystack))
        if score or len(tables) < 8:
            tables.append(
                TableMetadata(
                    name=table_name,
                    columns=columns,
                    score=score,
                    primary_key=primary_key,
                    foreign_keys=foreign_keys,
                    indexes=indexes,
                )
            )
    tables.sort(key=lambda item: (item.score, item.name), reverse=True)
    procedures = [proc for proc in metadata.procedures if any(token in proc.lower() for token in tokens)]
    if not procedures:
        procedures = metadata.procedures[:10]
    views = [view for view in metadata.views if any(token in view.lower() for token in tokens)]
    if not views:
        views = metadata.views[:10]
    return MetadataSearchResult(tables=tables[:8], views=views[:10], procedures=procedures[:10], version=metadata.version, engine_type=metadata.engine_type)


def rows_as_text(rows: list[dict[str, Any]], limit: int = 5) -> str:
    if not rows:
        return "No rows returned."
    return "\n".join("; ".join(f"{k}={v}" for k, v in row.items()) for row in rows[:limit])
