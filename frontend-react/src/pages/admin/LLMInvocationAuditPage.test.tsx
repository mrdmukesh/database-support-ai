import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LLMInvocationAuditPage } from "./LLMInvocationAuditPage";

const listInvocations = vi.fn();
const getInvocation = vi.fn();

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
});
