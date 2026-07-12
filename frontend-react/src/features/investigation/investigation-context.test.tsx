import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { InvestigationSubmitResponse } from "../../models/investigation";
import { InvestigationProvider } from "./investigation-context";
import { useInvestigation } from "./use-investigation";

const response: InvestigationSubmitResponse = {
  conversation: {
    id: "conversation-1",
    organization_id: "organization-1",
    workspace_id: "workspace-1",
    user_id: "user-1",
    title: "Duplicate payment",
  },
  user_message: {
    id: "message-1",
    conversation_id: "conversation-1",
    role: "user",
    content: "Why was the payment duplicated?",
    confidence: null,
    source_count: 0,
    requires_human_review: false,
  },
  assistant_message: {
    id: "message-2",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "Evidence-grounded response",
    confidence: 0.8,
    source_count: 2,
    requires_human_review: false,
  },
  findings: ["A retry occurred."],
  confidence: 0.8,
  requires_human_review: false,
  sources: ["SQL-1"],
  report: null,
  investigation_id: "investigation-1",
  connection_id: "connection-1",
  connection_name: "Finance DB",
};

function wrapper({ children }: { children: ReactNode }) {
  return <InvestigationProvider>{children}</InvestigationProvider>;
}

describe("InvestigationProvider", () => {
  it("initializes with empty, idle state", () => {
    const { result } = renderHook(() => useInvestigation(), { wrapper });

    expect(result.current).toMatchObject({
      selectedWorkspaceId: null,
      selectedConnectionId: null,
      submittedQuestion: null,
      isLoading: false,
      currentResponse: null,
      currentError: null,
    });
  });

  it("tracks selections and submission transitions", () => {
    const { result } = renderHook(() => useInvestigation(), { wrapper });

    act(() => {
      result.current.selectWorkspace("workspace-1");
      result.current.selectConnection("connection-1");
      result.current.startSubmission("Why was the payment duplicated?");
    });

    expect(result.current).toMatchObject({
      selectedWorkspaceId: "workspace-1",
      selectedConnectionId: "connection-1",
      submittedQuestion: "Why was the payment duplicated?",
      isLoading: true,
      currentResponse: null,
      currentError: null,
    });
  });

  it("records successful submission output and derived identifiers", () => {
    const { result } = renderHook(() => useInvestigation(), { wrapper });
    act(() => result.current.startSubmission("Question"));
    act(() => result.current.completeSubmission(response));

    expect(result.current).toMatchObject({
      isLoading: false,
      currentInvestigationId: "investigation-1",
      currentConversationId: "conversation-1",
      currentResponse: response,
      currentError: null,
    });
  });

  it("records a failure without retaining a response", () => {
    const { result } = renderHook(() => useInvestigation(), { wrapper });
    act(() => result.current.startSubmission("Question"));
    act(() => result.current.failSubmission("Evidence collection failed."));

    expect(result.current).toMatchObject({
      isLoading: false,
      currentInvestigationId: null,
      currentResponse: null,
      currentError: "Evidence collection failed.",
    });
  });

  it("resets all investigation state", () => {
    const { result } = renderHook(() => useInvestigation(), { wrapper });
    act(() => {
      result.current.selectWorkspace("workspace-1");
      result.current.selectConnection("connection-1");
      result.current.startSubmission("Question");
    });
    act(() => result.current.completeSubmission(response));
    act(() => result.current.reset());

    expect(result.current).toMatchObject({
      selectedWorkspaceId: null,
      selectedConnectionId: null,
      submittedQuestion: null,
      isLoading: false,
      currentInvestigationId: null,
      currentConversationId: null,
      currentResponse: null,
      currentError: null,
    });
  });
});
