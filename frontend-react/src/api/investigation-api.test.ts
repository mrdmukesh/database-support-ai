import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ChatConversation,
  ChatMessage,
  InvestigationSubmitRequest,
  InvestigationSubmitResponse,
  InvestigationSummary,
  SavedInvestigation,
} from "../models/investigation";
import {
  loadConversationMessages,
  loadConversations,
  loadInvestigationHistory,
  loadInvestigationMetadata,
  loadSavedInvestigation,
  submitInvestigation,
} from "./investigation-api";

const scope = { organizationId: "ORG-1", workspaceId: "WS-1", userId: "USER-1" };
const legacyContent = "## Root Cause Analysis\n- Retry execution caused duplicate processing.\n\n## Confirmed Facts\n- SQL-1 returned two rows.";
const conversation: ChatConversation = {
  id: "CONV-1",
  organization_id: "ORG-1",
  workspace_id: "WS-1",
  user_id: "USER-1",
  title: "Duplicate payment",
};
const message: ChatMessage = {
  id: "MSG-1",
  conversation_id: "CONV-1",
  role: "assistant",
  content: legacyContent,
  confidence: null,
  source_count: 1,
  requires_human_review: true,
};
const report = {
  investigation_id: "INV-1",
  html: "/reports/INV-1/report.html",
  pdf: "/reports/INV-1/report.pdf",
};
const saved: SavedInvestigation = {
  id: "INV-1",
  organization_id: "ORG-1",
  workspace_id: "WS-1",
  user_question: "Why was payment duplicated?",
  detected_intent: "duplicate_data",
  ai_answer: legacyContent,
  confidence_score: 0,
  report_path: "reports/history/INV-1",
  status: "AI_ANSWERED",
  created_at: "2026-07-11T00:00:00Z",
  report,
};

function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("investigation API", () => {
  it("submits the exact current request and preserves optional response fields and content", async () => {
    const payload: InvestigationSubmitRequest = {
      organization_id: "ORG-1",
      workspace_id: "WS-1",
      user_id: "USER-1",
      question: "Why was payment duplicated?",
      conversation_id: null,
    };
    const fixture: InvestigationSubmitResponse = {
      conversation,
      user_message: { ...message, id: "MSG-0", role: "user", content: payload.question },
      assistant_message: message,
      findings: [],
      confidence: 0,
      requires_human_review: true,
      sources: ["SQL-1"],
      report: null,
      investigation_id: null,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(fixture, 201));
    vi.stubGlobal("fetch", fetchMock);

    const result = await submitInvestigation(payload);

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/chat/ask");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify(payload) });
    expect(result.assistant_message.content).toBe(legacyContent);
    expect(result.report).toBeNull();
    expect(result.investigation_id).toBeNull();
  });

  it("loads tenant, workspace, and user-scoped conversations", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response([conversation]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadConversations(scope)).resolves.toEqual([conversation]);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8001/chat/conversations?organization_id=ORG-1&workspace_id=WS-1&user_id=USER-1",
    );
  });

  it("loads conversation messages without parsing legacy assistant content", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response([message]));
    vi.stubGlobal("fetch", fetchMock);

    const messages = await loadConversationMessages("CONV/1", scope);

    expect(fetchMock.mock.calls[0][0]).toContain("/chat/conversations/CONV%2F1/messages?");
    expect(messages[0].content).toBe(legacyContent);
    expect(messages[0].confidence).toBeNull();
  });

  it("loads workspace investigation history with the current optional status filter", async () => {
    const summary: InvestigationSummary = { ...saved, confidence_score: null };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response([summary]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadInvestigationHistory("ORG-1", "WS-1", "AI_ANSWERED")).resolves.toEqual([summary]);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8001/learning/investigations?organization_id=ORG-1&workspace_id=WS-1&status_filter=AI_ANSWERED",
    );
  });

  it("loads the verified saved-investigation detail shape", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(saved));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadSavedInvestigation("INV-1")).resolves.toEqual(saved);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/learning/investigations/INV-1");
  });

  it("loads available metadata from the same saved-investigation route", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response(saved));
    vi.stubGlobal("fetch", fetchMock);

    const metadata = await loadInvestigationMetadata("INV-1");

    expect(metadata.detected_intent).toBe("duplicate_data");
    expect(metadata.report).toEqual(report);
    expect(metadata.ai_answer).toBe(legacyContent);
  });
});
