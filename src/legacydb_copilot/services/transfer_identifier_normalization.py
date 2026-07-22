from __future__ import annotations

import re
from dataclasses import dataclass

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult, ExtractedEntity


_TRANSFER_ENTITY_TYPES = {"business_identifier", "exact_id_or_code", "business_key"}
_CANONICAL_TRF_PATTERN = re.compile(r"^TRF-(\d+)$", re.IGNORECASE)
_MSG_WRAPPED_TRF_PATTERN = re.compile(r"^MSG-(TRF-\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class TransferNormalizationTrace:
    raw_extracted_entity: str | None
    normalized_entity: str | None
    entity_type: str | None
    normalization_rule_used: str | None


def normalize_transfer_identifier(value: str) -> tuple[str | None, str | None]:
    wrapped_match = _MSG_WRAPPED_TRF_PATTERN.fullmatch(value.strip())
    if wrapped_match:
        return wrapped_match.group(1).upper(), "msg_wrapped_transfer_key"
    canonical_match = _CANONICAL_TRF_PATTERN.fullmatch(value.strip())
    if canonical_match:
        return f"TRF-{canonical_match.group(1)}", "canonical_transfer_key"
    return None, None


def normalize_transfer_entities(
    entities: EntityExtractionResult,
) -> tuple[EntityExtractionResult, TransferNormalizationTrace]:
    normalized_entities: list[ExtractedEntity] = []
    trace = TransferNormalizationTrace(None, None, None, None)
    for entity in entities.entities:
        if entity.entity_type not in _TRANSFER_ENTITY_TYPES:
            normalized_entities.append(entity)
            continue
        normalized_value, rule = normalize_transfer_identifier(entity.value)
        if normalized_value is None:
            normalized_entities.append(entity)
            continue
        normalized_entities.append(ExtractedEntity(entity.entity_type, normalized_value))
        if trace.raw_extracted_entity is None:
            trace = TransferNormalizationTrace(
                raw_extracted_entity=entity.value,
                normalized_entity=normalized_value,
                entity_type=entity.entity_type,
                normalization_rule_used=rule,
            )
    deduped: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    for entity in normalized_entities:
        key = (entity.entity_type, entity.value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    return (
        EntityExtractionResult(
            entities=deduped,
            suspected_issue=entities.suspected_issue,
            likely_module=entities.likely_module,
            application_name=entities.application_name,
            business_keywords=entities.business_keywords,
        ),
        trace,
    )


def typed_transfer_identifier(entities: EntityExtractionResult) -> str | None:
    for entity in entities.entities:
        if entity.entity_type not in _TRANSFER_ENTITY_TYPES:
            continue
        normalized_value, _ = normalize_transfer_identifier(entity.value)
        if normalized_value:
            return normalized_value
    return None