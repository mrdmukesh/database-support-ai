from __future__ import annotations

import re
from typing import Any

INTERNAL_TOKEN = re.compile(r"(?i)^(?:entity-\d+-(?:exact|candidate)-\d+|sql-\d+|evidence-\d+|rank(?:ing)?-\d+)$")
BUSINESS_TYPES = {"business_identifier", "exact_id_or_code", "business_key", "resolved_business_entity"}
DIAGNOSTIC_TYPES = {"entity_resolution", "entity_resolution_diagnostic"}


def canonicalize_entities(identified_entities: Any, evidence: Any = None) -> dict[str, Any]:
    """Separate business identity from resolver diagnostics and select canonical values."""
    business: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    defects: list[str] = []
    for item in identified_entities if isinstance(identified_entities, list) else []:
        if isinstance(item, str):
            if INTERNAL_TOKEN.fullmatch(item.strip()):
                defects.append(f"Internal token leaked into business entity field: {item}")
            elif item.strip():
                business.append({"original_entity_text": item, "normalized_entity_text": item})
            continue
        if not isinstance(item, dict):
            continue
        kind = str(item.get("entity_type") or "").casefold()
        if kind in DIAGNOSTIC_TYPES:
            diagnostics.append(item)
            continue
        if kind not in BUSINESS_TYPES:
            continue
        value = str(item.get("resolved_entity_value") or item.get("value") or item.get("normalized_entity_text") or item.get("original_entity_text") or "").strip()
        if value and INTERNAL_TOKEN.fullmatch(value):
            defects.append(f"Internal token leaked into business entity field: {value}")
            continue
        business.append({
            "original_entity_text": str(item.get("original_entity_text") or value),
            "normalized_entity_text": str(item.get("normalized_entity_text") or value),
            "resolved_entity_value": item.get("resolved_entity_value"),
            "resolved_entity_type": item.get("resolved_entity_type") or kind,
            "resolved_table": item.get("resolved_table"),
            "resolved_column": item.get("resolved_column"),
            "resolution_confidence": item.get("resolution_confidence"),
            "resolution_method": item.get("resolution_method"),
            "supporting_evidence_ids": item.get("supporting_evidence_ids") or [],
        })

    for resolution in diagnostics:
        original = str(resolution.get("original_entity_text") or resolution.get("extracted_value") or "").strip()
        resolved = str(resolution.get("resolved_entity_value") or resolution.get("matched_value") or "").strip()
        target = next((x for x in business if original and x["normalized_entity_text"].casefold() == original.casefold()), None)
        if target is None and original:
            target = {"original_entity_text": original, "normalized_entity_text": original}
            business.append(target)
        if target is not None and resolved and not INTERNAL_TOKEN.fullmatch(resolved):
            target.update({
                "resolved_entity_value": resolved,
                "resolved_entity_type": resolution.get("resolved_entity_type") or "business_identifier",
                "resolved_table": resolution.get("resolved_table"),
                "resolved_column": resolution.get("resolved_column"),
                "resolution_confidence": resolution.get("resolution_confidence", resolution.get("confidence")),
                "resolution_method": resolution.get("resolution_method") or resolution.get("match_type"),
                "supporting_evidence_ids": resolution.get("supporting_evidence_ids") or ([resolution.get("evidence_id")] if resolution.get("evidence_id") else []),
            })

    canonical: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in business:
        value = str(item.get("resolved_entity_value") or item.get("normalized_entity_text") or item.get("original_entity_text") or "").strip()
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            canonical.append({"canonical_investigated_entity": value, **item})
    evidence_text = str(evidence or "").casefold()
    linked = [x["canonical_investigated_entity"] for x in canonical if x["canonical_investigated_entity"].casefold() in evidence_text]
    return {
        "canonical_entities": canonical,
        "canonical_investigated_entity": canonical[0]["canonical_investigated_entity"] if canonical else "",
        "evidence_linked_entities": linked,
        "diagnostics": diagnostics,
        "evaluator_input_defects": defects,
    }
