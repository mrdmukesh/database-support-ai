from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HelpResponse:
    answer: str
    steps: list[str]
    related_pages: list[str]
    warnings: list[str]
    links: list[str]


@dataclass(frozen=True)
class HelpDocument:
    slug: str
    title: str
    content: str


_INVESTIGATION_TERMS = {
    "root cause",
    "duplicate",
    "missing",
    "failed",
    "slow",
    "why did",
    "investigate",
    "apt-",
    "ord-",
}


def answer_help_question(question: str, current_page: str | None = None) -> HelpResponse:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles answer help question within the Database Support AI application flow.
    
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
    normalized = question.strip()
    if _should_redirect_to_ai_chat(normalized):
        return HelpResponse(
            answer=(
                "This sounds like a database investigation or root-cause question. "
                "Use AI Chat so the app can collect live metadata, safe SQL evidence, "
                "verification checks, and a report."
            ),
            steps=[
                "Open AI Chat.",
                "Select the correct workspace.",
                "Enter the production issue and business key.",
                "Click Ask AI.",
                "Review evidence and run suggested verification checks.",
            ],
            related_pages=["AI Chat", "Suggested Verification Checks", "Reports"],
            warnings=[
                "Help Assistant does not query customer databases.",
                "Help Assistant does not run SQL.",
            ],
            links=["AI Chat"],
        )

    docs = _load_help_documents()
    matches = _rank_documents(normalized, docs, current_page=current_page)
    selected = matches[:3] or docs[:1]
    primary = selected[0]
    return HelpResponse(
        answer=_summary(primary),
        steps=_section_lines(primary.content, "Steps"),
        related_pages=[doc.title for doc in selected],
        warnings=_dedupe([line for doc in selected for line in _section_lines(doc.content, "Warnings")]),
        links=[doc.title for doc in selected],
    )


def _should_redirect_to_ai_chat(question: str) -> bool:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for should redirect to ai chat within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    lowered = question.lower()
    if lowered.startswith(("how do i", "how to", "where do i", "what is the page")):
        return False
    return any(term in lowered for term in _INVESTIGATION_TERMS)


def _load_help_documents() -> list[HelpDocument]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for load help documents within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Document indexing must remain workspace-scoped and must not index unapproved live database rows.
    """
    root = _help_root()
    docs: list[HelpDocument] = []
    for path in sorted(root.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title = _title(content) or path.stem.replace("_", " ").title()
        docs.append(HelpDocument(slug=path.stem, title=title, content=content))
    return docs


def _help_root() -> Path:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for help root within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    candidates = [
        Path.cwd() / "docs" / "help",
        Path(__file__).resolve().parents[3] / "docs" / "help",
        Path("/app/docs/help"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _rank_documents(question: str, docs: list[HelpDocument], current_page: str | None = None) -> list[HelpDocument]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for rank documents within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Document indexing must remain workspace-scoped and must not index unapproved live database rows.
    """
    query_terms = _terms(question)
    page_terms = _terms(current_page or "")
    scored = []
    for doc in docs:
        haystack = f"{doc.title} {doc.slug} {doc.content}".lower()
        score = sum(3 for term in query_terms if term in haystack)
        score += sum(1 for term in page_terms if term in haystack)
        if doc.slug.replace("_", " ") in question.lower():
            score += 5
        scored.append((score, doc.title, doc))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [doc for score, _, doc in scored if score > 0]


def _terms(value: str) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for terms within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return {
        term
        for term in re.split(r"[^a-zA-Z0-9_-]+", value.lower())
        if len(term) >= 3 and term not in {"the", "and", "this", "that", "with", "from"}
    }


def _title(content: str) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for title within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _summary(doc: HelpDocument) -> str:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for summary within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    lines = [
        line.strip()
        for line in doc.content.splitlines()
        if line.strip() and not line.startswith("#") and not re.match(r"^\d+\.", line.strip())
    ]
    return lines[0] if lines else f"Use the {doc.title} page for this workflow."


def _section_lines(content: str, heading: str) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for section lines within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    lines = content.splitlines()
    capture = False
    values: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.rstrip(":").lower() == heading.lower():
            capture = True
            continue
        if capture and stripped.endswith(":") and not re.match(r"^\d+\.", stripped):
            break
        if capture and re.match(r"^\d+\.", stripped):
            values.append(re.sub(r"^\d+\.\s*", "", stripped))
        elif capture and stripped.startswith("-"):
            values.append(stripped.lstrip("-").strip())
    return values


def _dedupe(values: list[str]) -> list[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for dedupe within help_assistant_service.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in help_assistant_service.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    return list(dict.fromkeys(item for item in values if item))
