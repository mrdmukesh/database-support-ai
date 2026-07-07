from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import KnowledgeArticleModel


def _tokens(value: str) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for tokens within approved_knowledge_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in approved_knowledge_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return {token for token in re.findall(r"[a-z0-9_/-]{3,}", value.lower()) if token}


def search_approved_knowledge(
    db: Session,
    *,
    organization_id: str,
    workspace_id: str,
    question: str,
    limit: int = 3,
) -> list[KnowledgeArticleModel]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles search approved knowledge within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
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
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles knowledge article reference within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
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
