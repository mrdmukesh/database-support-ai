import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceSection } from "./EvidenceSection";
import { ExecutiveSummarySection } from "./ExecutiveSummarySection";
import { InvestigationBadges } from "./InvestigationBadges";
import { InvestigationHeader } from "./InvestigationHeader";
import { RecommendationSection } from "./RecommendationSection";
import { RootCauseSection } from "./RootCauseSection";

describe("current investigation result components", () => {
  it("renders complete current data through narrow props", () => {
    render(<>
      <InvestigationHeader investigationId="INV-1" question="Why duplicate?" intent="duplicate_data" status="AI_ANSWERED" createdAt="2026-07-12" />
      <InvestigationBadges confidence={0.8} sourceCount={2} requiresHumanReview findings={["verification_required"]} />
      <ExecutiveSummarySection summary="Evidence-backed summary" />
      <RootCauseSection rootCauses={["Retry execution"]} />
      <EvidenceSection evidence={["SQL-1 returned two rows"]} />
      <RecommendationSection recommendations={["Verify idempotency"]} />
    </>);
    expect(screen.getByRole("heading", { name: "Investigation INV-1" })).toBeInTheDocument();
    expect(screen.getByText("Confidence 80%")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
    expect(screen.getByText("Human review required")).toBeInTheDocument();
    expect(screen.getByText("Retry execution")).toBeInTheDocument();
    expect(screen.getByText("SQL-1 returned two rows")).toBeInTheDocument();
    expect(screen.getByText("Verify idempotency")).toBeInTheDocument();
  });

  it("preserves partial results and legitimate zero values", () => {
    render(<><InvestigationBadges confidence={0} sourceCount={0} requiresHumanReview={false} />
      <ExecutiveSummarySection summary="Partial answer" /><EvidenceSection evidence={[]} /></>);
    expect(screen.getByText("Confidence 0%")).toBeInTheDocument();
    expect(screen.getByText("0 sources")).toBeInTheDocument();
    expect(screen.getByText("No safety findings")).toBeInTheDocument();
    expect(screen.getByText("Partial answer")).toBeInTheDocument();
    expect(screen.getByText("Evidence unavailable")).toBeInTheDocument();
  });

  it("shows existing missing-data fallbacks without inventing content", () => {
    render(<><InvestigationHeader investigationId={null} question="" />
      <InvestigationBadges confidence={null} /><ExecutiveSummarySection summary={null} />
      <RootCauseSection rootCauses={null} /><RecommendationSection recommendations={undefined} /></>);
    expect(screen.getByRole("heading", { name: "Investigation ID unavailable" })).toBeInTheDocument();
    expect(screen.getByText("Question unavailable")).toBeInTheDocument();
    expect(screen.getByText("Confidence Confidence unavailable")).toBeInTheDocument();
    expect(screen.getByText("Summary unavailable for this investigation.")).toBeInTheDocument();
    expect(screen.getByText("Open the report for full evidence-backed root-cause analysis.")).toBeInTheDocument();
  });

  it("keeps malformed values safe and omits unusable list entries", () => {
    render(<><ExecutiveSummarySection summary={'<script>alert("x")</script>'} />
      <RootCauseSection rootCauses={[null, "  valid cause  ", 42]} />
      <EvidenceSection evidence={["", {}, " valid evidence "]} />
      <RecommendationSection recommendations={[undefined, " valid step "]} /></>);
    expect(screen.getByText('<script>alert("x")</script>')).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("valid cause")).toBeInTheDocument();
    expect(screen.getByText("valid evidence")).toBeInTheDocument();
    expect(screen.getByText("valid step")).toBeInTheDocument();
    expect(screen.queryByText("42")).not.toBeInTheDocument();
  });
});
