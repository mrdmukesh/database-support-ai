import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import * as api from "../../api/evaluation-api";
import { EvaluationDashboardPage } from "./EvaluationDashboardPage";

vi.mock("../../api/evaluation-api");
vi.mock("./EvaluationJobControl", () => ({ EvaluationJobControl: () => null }));

it("loads the completed run targeted by Open reports", async () => {
  const run = (id: string) => ({ id, name: id, status: "completed", created_at: "2026-01-01", application_commit: "abc", application_version: "1", scenario_count: 1, completed_count: 1 });
  vi.mocked(api.listEvaluationRuns).mockResolvedValue([run("R1"), run("R2")]);
  vi.mocked(api.getEvaluationSummary).mockImplementation(async id => ({ run_id: id, scenario_count: 1, completed_count: 1, passed_count: 1, failed_count: 0, human_review_count: 0, critical_failure_count: 0, deterministic_average: 80, ai_judge_average: 80, total_duration_seconds: 1, total_tokens: 1, total_cost_usd: 0, domains: { payroll: 1 }, statuses: { completed: 1 } }));
  vi.mocked(api.listEvaluationScenarios).mockResolvedValue([]);
  vi.mocked(api.listHumanReviews).mockResolvedValue([]);

  render(<MemoryRouter initialEntries={["/app/evaluation?runId=R2#scenario-results"]}><EvaluationDashboardPage /></MemoryRouter>);

  await waitFor(() => expect(api.getEvaluationSummary).toHaveBeenCalledWith("R2", expect.any(AbortSignal)));
  expect(screen.getByLabelText("Evaluation run")).toHaveValue("R2");
  expect(screen.getByRole("navigation", { name: "Evaluation views" })).toHaveAttribute("id", "scenario-results");
});
