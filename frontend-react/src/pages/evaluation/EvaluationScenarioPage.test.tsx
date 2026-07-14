import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/evaluation-api";
import { EvaluationScenarioPage } from "./EvaluationScenarioPage";

vi.mock("../../api/evaluation-api");

describe("EvaluationScenarioPage",()=>{
  beforeEach(()=>vi.clearAllMocks());
  it("shows a structured AI judge report",async()=>{
    vi.mocked(api.getEvaluationScenario).mockResolvedValue({result_id:"X1",scenario_id:"payroll-1",scenario_version:1,domain:"payroll",attempt:1,execution_status:"completed",investigation_id:"I1",deterministic_score:80,classification:"pass",critical_failure:false,ai_judge_score:84,score_difference:4,human_review_required:false,human_review_reasons:[],duration_seconds:12,total_tokens:170,cost_usd:.02,question:"Why?",category:"root_cause",difficulty:"medium",investigation_status:"AI_ANSWERED",answer:"Answer",identified_entities:[],discovered_database_objects:[],evidence:[],citations:[],recommendations:[],errors:[],timings:{},usage_cost:{},deterministic_details:{},judge_result:{explanation:"Evidence supports the answer."},judge_report:{judge_version:1,prompt_version:"v1",deterministic_difference:4,invocations:[{judge_index:1,provider:"openai",model:"judge-model",status:"completed",weighted_score:84,result:{root_cause_score:90,evidence_score:85,object_discovery_score:80,fix_score:75,citation_score:70,safety_score:95,completeness_score:85,unsupported_claims:[],missing_evidence:["lock evidence"],incorrect_objects:[],incorrect_entities:[],explanation:"Evidence supports the answer."},input_tokens:100,output_tokens:50,duration_ms:1250,estimated_cost_usd:.002,retry_count:0,error:""}]}});
    render(<MemoryRouter initialEntries={["/app/evaluation/scenarios/X1"]}><Routes><Route path="/app/evaluation/scenarios/:resultId" element={<EvaluationScenarioPage/>}/></Routes></MemoryRouter>);
    expect(await screen.findByText("AI Judge Report")).toBeInTheDocument();
    expect(screen.getByText("judge-model")).toBeInTheDocument();
    expect(screen.getByText("Evidence supports the answer.")).toBeInTheDocument();
    expect(screen.getByText("lock evidence")).toBeInTheDocument();
    expect(screen.getByRole("progressbar",{name:"Root Cause: 90 out of 100"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Download PDF"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Download JSON"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Copy Report"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Compare Previous"})).toBeInTheDocument();
  });
});
