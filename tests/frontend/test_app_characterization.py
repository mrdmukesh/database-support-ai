"""Characterization tests for the current framework-free frontend.

These tests intentionally protect app.html's existing DOM and JavaScript contracts
before extraction. They do not prescribe styling or a future component framework.
"""

from html.parser import HTMLParser
from pathlib import Path
import re


APP_PATH = Path(__file__).parents[2] / "app.html"
APP_HTML = APP_PATH.read_text(encoding="utf-8")


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.attributes_by_id: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
            self.attributes_by_id[element_id] = attributes


def _dom() -> _IdCollector:
    parser = _IdCollector()
    parser.feed(APP_HTML)
    return parser


def _function_source(name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", APP_HTML)
    assert match, f"Expected frontend function {name}"
    start = match.start()
    brace = match.end() - 1
    depth = 0
    for index in range(brace, len(APP_HTML)):
        if APP_HTML[index] == "{":
            depth += 1
        elif APP_HTML[index] == "}":
            depth -= 1
            if depth == 0:
                return APP_HTML[start : index + 1]
    raise AssertionError(f"Unclosed frontend function {name}")


def _event_handler_source(element_id: str, event_name: str) -> str:
    marker = f'document.getElementById("{element_id}").addEventListener("{event_name}"'
    start = APP_HTML.find(marker)
    assert start >= 0, f"Expected {event_name} handler for #{element_id}"
    arrow = APP_HTML.find("=>", start)
    brace = APP_HTML.find("{", arrow)
    assert arrow >= 0 and brace >= 0, f"Expected callback body for #{element_id}"
    depth = 0
    for index in range(brace, len(APP_HTML)):
        if APP_HTML[index] == "{":
            depth += 1
        elif APP_HTML[index] == "}":
            depth -= 1
            if depth == 0:
                return APP_HTML[start : index + 1]
    raise AssertionError(f"Unclosed {event_name} handler for #{element_id}")


def test_ai_chat_view_can_be_opened_from_navigation() -> None:
    dom = _dom()

    assert "chat" in dom.ids
    assert 'data-view-button="chat"' in APP_HTML
    assert 'setView(button.dataset.viewButton)' in APP_HTML
    assert 'views.forEach((view) => view.classList.toggle("active", view.id === name))' in _function_source("setView")


def test_investigation_uses_workspace_and_workspace_scoped_connection_management() -> None:
    dom = _dom()

    assert dom.attributes_by_id["chatWorkspace"]["name"] == "workspaceId"
    assert dom.attributes_by_id["connectionWorkspace"]["name"] == "workspaceId"
    assert "connectionRows" in dom.ids
    assert 'renderWorkspaceOptions("chatWorkspace", workspaces)' in _function_source("loadChatManager")
    assert 'api(`/databases/connections?organization_id=${encodeURIComponent(session.user.organization_id)}`)' in _function_source("loadConnectionManager")


def test_question_submission_sends_the_existing_investigation_contract() -> None:
    handler = _event_handler_source("chatForm", "submit")

    assert 'api("/chat/ask"' in handler
    assert 'workspace_id: form.get("workspaceId")' in handler
    assert 'question: form.get("question").trim()' in handler
    assert "organization_id: session.user.organization_id" in handler
    assert "user_id: session.user.id" in handler


def test_investigation_loading_state_is_displayed_and_submit_is_disabled() -> None:
    handler = _event_handler_source("chatForm", "submit")

    assert "submit.disabled = true" in handler
    assert 'setMessage("chatMessage", "Analyzing prompt and saving chat...")' in handler
    assert "finally" in handler
    assert "submit.disabled = false" in handler


def test_successful_investigation_renders_answer_badges_reports_and_verification() -> None:
    handler = _event_handler_source("chatForm", "submit")

    assert "response.assistant_message.content" in handler
    assert "renderChatBadges(response)" in handler
    assert "renderReportDownloads(response.report)" in handler
    assert "showFeedbackPanel(response.investigation_id)" in handler
    assert "await loadVerificationChecks(response.investigation_id)" in handler
    assert '"Investigation Complete. Reports generated."' in handler


def test_partial_success_without_report_keeps_answer_and_uses_saved_message() -> None:
    handler = _event_handler_source("chatForm", "submit")
    renderer = _function_source("renderInlineAnswer")

    assert "response.assistant_message.content" in handler
    assert 'response.report ? "Investigation Complete. Reports generated." : "Answer generated and saved to history."' in handler
    assert 'const answer = String(content || "").trim()' in renderer
    assert 'Open the report for full evidence-backed root-cause analysis.' in renderer
    assert 'Open the report for the evidence table and SQL results.' in renderer


def test_api_failures_are_rendered_as_frontend_error_messages() -> None:
    handler = _event_handler_source("chatForm", "submit")
    api_source = _function_source("api")

    assert 'setMessage("chatMessage", error.message, "error")' in handler
    assert "const detail = data?.detail" in api_source
    assert "throw new Error(formatApiErrorDetail(detail))" in api_source


def test_confidence_safety_and_finding_badges_are_rendered() -> None:
    renderer = _function_source("renderChatBadges")

    assert "Math.round(response.confidence * 100)" in renderer
    assert "response.requires_human_review" in renderer
    assert '"Human review required"' in renderer
    assert '"No safety findings"' in renderer
    assert "response.findings.map" in renderer


def test_report_download_actions_include_current_formats_and_trace_authorization() -> None:
    renderer = _function_source("renderReportDownloads")

    assert "report.html" in renderer
    assert "report.pdf" in renderer
    assert "report.docx" in renderer
    assert "report.xlsx" in renderer
    assert "report.ai_trace" in renderer
    assert '["super_admin", "organization_admin", "dba"].includes(role)' in renderer
    assert "downloadReport(button.dataset.downloadReport" in renderer


def test_saved_investigation_can_be_reopened_with_reports_and_checks() -> None:
    source = _function_source("openSavedInvestigation")

    assert "api(`/learning/investigations/${investigationId}`)" in source
    assert 'setView("chat")' in source
    assert "investigation.ai_answer" in source
    assert 'renderReportDownloads(investigation.report, "reportDownloads")' in source
    assert "await loadVerificationChecks(investigation.id)" in source


def test_expired_or_unauthorized_session_is_cleared_and_surfaces_api_error() -> None:
    source = _function_source("api")

    assert "response.status === 401" in source
    assert "localStorage.removeItem(sessionKey)" in source
    assert "updateSessionLabel()" in source
    assert "throw new Error(formatApiErrorDetail(detail))" in source


def test_characterization_suite_does_not_require_production_test_hooks() -> None:
    assert "data-testid" not in APP_HTML
    assert "__TEST__" not in APP_HTML
