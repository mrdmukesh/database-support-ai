import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LLMInvocationAuditPage } from "./LLMInvocationAuditPage";

const listInvocations = vi.fn();
const getInvocation = vi.fn();
const invocation = {
  llm_invocation_id: "CALL-1",
  investigation_id: "INV-20260725-151640-4928CAE6",
  logical_request_id: "LOGICAL-1",
  stage_name: "Root Cause Reasoning",
  agent_name: "reasoning_agent",
  provider: "openai",
  model_name: "gpt-4.1-mini",
  status: "completed",
  prompt_tokens: 5338,
  completion_tokens: 941,
  total_tokens: 6279,
  duration_ms: 12813,
  estimated_cost: 0,
  currency: "USD",
  retry_attempt: 1,
  started_at: "2026-07-25T15:17:27Z",
};
const invocationDetail = {
  ...invocation,
  system_prompt_sanitized: "Evidence-grounded system instructions",
  user_prompt_sanitized: JSON.stringify({ reasoning_mode: "evidence_summary_not_reproduced", evidence_refs: ["SQL-1"] }),
  context_payload_sanitized: JSON.stringify({ model: "gpt-4.1-mini", input: "[REDACTED_PII]" }),
  tool_definitions_sanitized: "[]",
  response_text_sanitized: "Verified evidence summary",
  error_message_sanitized: "",
  request_payload_hash: "hash",
  response_payload_hash: "response-hash",
  finish_reason: "completed",
  correlation_id: "INV-20260725-151640-4928CAE6",
  trace_id: null,
  prompt_template_name: "root_cause_reasoning",
  prompt_template_version: "v1",
  application_commit: "commit",
  redaction_notice: "Sensitive values are redacted.",
};

vi.mock("../../api/llm-audit-api", () => ({
  listLLMInvocations: (...args: unknown[]) => listInvocations(...args),
  getLLMInvocation: (...args: unknown[]) => getInvocation(...args),
}));

describe("LLMInvocationAuditPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listInvocations.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 25,
      zero_invocation_explanation: {
        code: "AI_SKIPPED_BY_EVIDENCE_GATE",
        reason: "The evidence gate determined that no LLM reasoning request was required.",
      },
    });
  });

  it("explains why a filtered investigation has zero provider invocations", async () => {
    render(<LLMInvocationAuditPage />);

    expect(await screen.findByText("AI_SKIPPED_BY_EVIDENCE_GATE")).toBeInTheDocument();
    expect(screen.getByLabelText("Why the LLM was not invoked")).toHaveTextContent(
      "The evidence gate determined that no LLM reasoning request was required.",
    );
    expect(screen.getByText("0 invocations")).toBeInTheDocument();
  });

  it("passes investigation, stage, model, status, prompt, failed-only, and date filters", async () => {
    render(<LLMInvocationAuditPage />);
    await screen.findByText("AI_SKIPPED_BY_EVIDENCE_GATE");

    fireEvent.change(screen.getByLabelText("Investigation ID"), { target: { value: "INV-APT-2101" } });
    fireEvent.change(screen.getByLabelText("Stage"), { target: { value: "reasoning_agent" } });
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "gpt-test" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "failed" } });
    fireEvent.change(screen.getByLabelText("Search sanitized prompts"), { target: { value: "appointment" } });
    fireEvent.change(screen.getByLabelText("From date and time"), { target: { value: "2026-07-24T10:00" } });
    fireEvent.change(screen.getByLabelText("To date and time"), { target: { value: "2026-07-25T18:00" } });
    fireEvent.click(screen.getByLabelText("Failed calls only"));
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => expect(listInvocations).toHaveBeenCalledTimes(2));
    expect(listInvocations).toHaveBeenLastCalledWith(expect.objectContaining({
      investigation_id: "INV-APT-2101",
      stage_name: "reasoning_agent",
      model: "gpt-test",
      status: "failed",
      search: "appointment",
      failed_only: true,
      started_after: expect.stringContaining("2026-07-24T"),
      started_before: expect.stringContaining("2026-07-25T"),
      page: 1,
      page_size: 25,
    }));
  });

  it("opens an obvious read-only prompt dialog and switches between prompt sections", async () => {
    listInvocations.mockResolvedValue({
      items: [invocation], total: 1, page: 1, page_size: 25, zero_invocation_explanation: null,
    });
    getInvocation.mockResolvedValue(invocationDetail);
    render(<LLMInvocationAuditPage />);

    const viewPrompt = await screen.findByRole("button", { name: "View prompt" });
    fireEvent.click(viewPrompt);
    const dialog = await screen.findByRole("dialog", { name: "Root Cause Reasoning" });
    expect(getInvocation).toHaveBeenCalledWith("CALL-1");
    expect(dialog).toHaveTextContent("Evidence-grounded system instructions");
    expect(dialog).toHaveTextContent("Sanitized · read only");

    fireEvent.click(screen.getByRole("button", { name: "User Prompt" }));
    expect(screen.getByLabelText("User Prompt")).toHaveTextContent("evidence_summary_not_reproduced");
    fireEvent.click(screen.getByRole("button", { name: "Request Context" }));
    expect(screen.getByLabelText("Request Context")).toHaveTextContent("gpt-4.1-mini");
    expect(screen.queryByRole("button", { name: /copy|retry|replay|execute/i })).not.toBeInTheDocument();
  });

  it("shows prompt loading failures without opening an empty dialog", async () => {
    listInvocations.mockResolvedValue({
      items: [invocation], total: 1, page: 1, page_size: 25, zero_invocation_explanation: null,
    });
    getInvocation.mockRejectedValue(new Error("Prompt details unavailable"));
    render(<LLMInvocationAuditPage />);
    fireEvent.click(await screen.findByRole("button", { name: "View prompt" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Prompt details unavailable");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
