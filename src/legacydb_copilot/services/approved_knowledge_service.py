from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import KnowledgeArticleModel


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_/-]{3,}", value.lower()) if token}


def search_approved_knowledge(
    db: Session,
    *,
    organization_id: str,
    workspace_id: str,
    question: str,
    limit: int = 3,
) -> list[KnowledgeArticleModel]:
    question_tokens = _tokens(question)
    if not question_tokens:
        return []
    articles = (
        db.query(KnowledgeArticleModel)
        .filter(
            KnowledgeArticleModel.organization_id == organization_id,
            KnowledgeArticleModel.workspace_id == workspace_id,
            KnowledgeArticleModel.is_active.is_(True),
        )
        .order_by(KnowledgeArticleModel.updated_at.desc())
        .limit(50)
        .all()
    )
    scored: list[tuple[int, KnowledgeArticleModel]] = []
    for article in articles:
        haystack = " ".join(
            [
                article.title,
                article.module_name,
                article.issue_type,
                article.symptoms,
                article.detected_entities,
                article.actual_root_cause,
                article.fix_summary,
            ]
        )
        score = len(question_tokens & _tokens(haystack))
        if score:
            scored.append((score, article))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [article for _, article in scored[:limit]]


def knowledge_article_reference(article: KnowledgeArticleModel) -> str:
    confidence = (
        f"{round(float(article.confidence_after_approval) * 100)}%"
        if article.confidence_after_approval is not None
        else "approved"
    )
    entities = ""
    try:
        parsed = json.loads(article.detected_entities or "[]")
        if parsed:
            entities = f"\nEntities: {parsed}"
    except json.JSONDecodeError:
        entities = ""
    return (
        "Similar approved issue found\n"
        f"Reference article: {article.title} ({article.id})\n"
        f"Previous root cause: {article.actual_root_cause or 'Not recorded'}\n"
        f"Previous fix: {article.fix_summary or 'Not recorded'}\n"
        f"Confidence: {confidence}"
        f"{entities}"
    )
