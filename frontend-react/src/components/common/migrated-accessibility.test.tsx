import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { InvestigationHistoryList } from "../investigation/InvestigationHistoryList";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { VerificationCheckCard } from "../verification/VerificationCheckCard";

describe("migrated page accessibility contracts", () => {
  it("provides accessible names for feedback controls and buttons", () => {
    render(<FeedbackPanel investigationId="INV-1" />);
    expect(screen.getByRole("textbox", { name: "Actual root cause" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Production issue resolved?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit for DBA/Lead Approval" })).toHaveAttribute("type", "submit");
  });
  it("uses explicit column headers and visible text status", () => {
    render(<MemoryRouter><InvestigationHistoryList investigations={[{ id:"I",organization_id:"O",workspace_id:"W",user_question:"Why?",detected_intent:"duplicate",ai_answer:"",confidence_score:0,report_path:"",status:"DEVELOPER_REVIEW",created_at:"2026" }]} /></MemoryRouter>);
    for (const header of screen.getAllByRole("columnheader")) expect(header).toHaveAttribute("scope", "col");
    expect(screen.getByText("DEVELOPER_REVIEW")).toBeVisible();
  });
  it("keeps verification SQL non-editable and action buttons explicitly named", () => {
    render(<VerificationCheckCard check={{ id:"C",investigation_id:"I",claim:"Check rows",purpose:"Purpose",claim_being_verified:"Claim",evidence_logic:"",expected_result_explanation:"",interpretation:"",conclusion_template:"",verification_sql:"SELECT 1",expected_result:"one",risk_level:"read",source:"SQL",status:"Pending",actual_result_summary:"",confidence_impact:"",notes:"",verified_by:"",verified_at:null }} onRun={()=>{}} onSkip={()=>{}} />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run this check" })).toHaveAttribute("type", "button");
    expect(screen.getByRole("button", { name: "Skip" })).toHaveAttribute("type", "button");
  });
});
