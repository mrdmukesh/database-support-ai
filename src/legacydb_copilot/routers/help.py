from __future__ import annotations

from fastapi import APIRouter, Depends

from legacydb_copilot.dependencies import get_current_user
from legacydb_copilot.schemas import HelpAskRequest, HelpAskResponse
from legacydb_copilot.services.help_assistant_service import answer_help_question

router = APIRouter(prefix="/help", tags=["help"])


@router.post("/ask", response_model=HelpAskResponse)
def ask_help(payload: HelpAskRequest, _current_user=Depends(get_current_user)) -> dict[str, object]:
    response = answer_help_question(payload.question, payload.current_page)
    return {
        "answer": response.answer,
        "steps": response.steps,
        "related_pages": response.related_pages,
        "warnings": response.warnings,
        "links": response.links,
    }
