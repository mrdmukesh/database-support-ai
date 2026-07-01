from __future__ import annotations

import re
from dataclasses import dataclass

from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


@dataclass(frozen=True)
class ProblemPhrase:
    phrase: str
    issue_kind: str | None
    target_terms: list[str]
    parent_terms: list[str]
    secondary_cause_terms: list[str]


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "by",
    "caused",
    "created",
    "did",
    "does",
    "for",
    "from",
    "generated",
    "has",
    "have",
    "is",
    "issue",
    "like",
    "main",
    "missing",
    "multiple",
    "not",
    "no",
    "object",
    "of",
    "open",
    "or",
    "possible",
    "problem",
    "record",
    "records",
    "root",
    "slow",
    "the",
    "this",
    "two",
    "with",
    "without",
}


def parse_problem_phrase(question: str) -> ProblemPhrase:
    lowered = question.lower()
    main_text, secondary_text = _split_secondary_causes(lowered)
    normalized = re.sub(r"[^a-z0-9_\-\s]", " ", main_text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    patterns = [
        ("missing", r"\b(?:(?P<parent1>[a-z][a-z0-9_]*)(?:\s+[a-z][a-z0-9_]*){0,2}\s+)?(?:are\s+)?missing\s+(?P<target1>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\b"),
        ("missing", r"\b(?P<target7>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\s+(?:is\s+|are\s+)?missing\b"),
        ("missing", r"\bno\s+(?P<target2>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\s+(?:generated|created|exists?)\b"),
        ("missing", r"\b(?P<target3>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\s+(?:not\s+generated|not\s+created|does\s+not\s+exist)\b"),
        ("duplicate", r"\b(?:(?P<parent3>[a-z][a-z0-9_]*)(?:\s+[a-z][a-z0-9_]*){0,2}\s+(?:has|have|with|created)\s+)?(?:duplicate|duplicated|two|multiple)\s+(?:active\s+|open\s+|valid\s+)?(?P<target4>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\b"),
        ("performance", r"\b(?:slow|long running|timeout)\s+(?P<target5>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\b"),
        ("failed", r"\b(?:failed|failing)\s+(?P<target6>[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)\b"),
    ]
    for issue_kind, pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        target = next((value for key, value in match.groupdict().items() if key.startswith("target") and value), "")
        parent = next((value for key, value in match.groupdict().items() if key.startswith("parent") and value), "")
        target_terms = _terms(target)
        parent_terms = [term for term in _terms(parent) if term not in target_terms]
        if issue_kind == "missing" and not parent_terms:
            parent_terms = _parent_before_missing(normalized, target_terms)
        return ProblemPhrase(
            phrase=match.group(0).strip(),
            issue_kind=issue_kind,
            target_terms=target_terms,
            parent_terms=parent_terms,
            secondary_cause_terms=_terms(secondary_text),
        )
    return ProblemPhrase(
        phrase=normalized,
        issue_kind=None,
        target_terms=[],
        parent_terms=[],
        secondary_cause_terms=_terms(secondary_text),
    )


def resolve_table_from_terms(terms: list[str], metadata: MetadataSearchResult) -> TableMetadata | None:
    if not terms:
        return None
    scored: list[tuple[float, TableMetadata]] = []
    for table in metadata.tables:
        name = table.name.lower()
        name_tokens = set(_split_identifier(name))
        score = 0.0
        for term in terms:
            variants = _variants(term)
            if name in variants or any(variant == name for variant in variants):
                score += 8.0
            if any(variant in name_tokens for variant in variants):
                score += 5.0
            if any(variant in name for variant in variants):
                score += 3.0
            for column in table.columns:
                column_l = column.lower()
                if any(variant in column_l for variant in variants):
                    score += 0.5
        if score:
            scored.append((score + table.score * 0.1, table))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1].score, item[1].name), reverse=True)
    return scored[0][1]


def terms_match_table(terms: list[str], table: TableMetadata) -> bool:
    if not terms:
        return True
    name = table.name.lower()
    tokens = set(_split_identifier(name))
    for term in terms:
        variants = _variants(term)
        if any(variant in tokens or variant in name for variant in variants):
            return True
    return False


def _split_secondary_causes(text: str) -> tuple[str, str]:
    markers = (
        " caused by ",
        " whether caused by ",
        " possible causes ",
        " group by root cause ",
        " group them by ",
        " root cause ",
        " due to ",
        " because of ",
    )
    positions = [(text.find(marker), marker) for marker in markers if marker in text]
    if not positions:
        return text, ""
    index, marker = min(positions, key=lambda item: item[0])
    return text[:index], text[index + len(marker) :]


def _parent_before_missing(text: str, target_terms: list[str]) -> list[str]:
    before = text.split("missing", 1)[0]
    terms = _terms(before)
    return [term for term in terms[-3:] if term not in target_terms]


def _terms(text: str) -> list[str]:
    terms: list[str] = []
    for raw in re.findall(r"\b[a-z][a-z0-9_]*\b", text.lower()):
        for part in _split_identifier(raw):
            if len(part) >= 3 and part not in _STOPWORDS and part not in terms:
                terms.append(part)
    return terms


def _split_identifier(value: str) -> list[str]:
    return [part for part in re.split(r"[_\-\s]+", value.lower()) if part]


def _variants(term: str) -> set[str]:
    variants = {term}
    if term.endswith("ies") and len(term) > 3:
        variants.add(term[:-3] + "y")
    if term.endswith("es") and len(term) > 2:
        variants.add(term[:-2])
    if term.endswith("s") and len(term) > 1:
        variants.add(term[:-1])
    else:
        variants.add(term + "s")
    return variants
