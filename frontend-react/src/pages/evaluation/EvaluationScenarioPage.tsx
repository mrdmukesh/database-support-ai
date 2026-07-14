import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEvaluationScenario } from "../../api/evaluation-api";
import type { AIJudgeInvocation, EvaluationScenarioDetail } from "../../models/evaluation";

const render = (value:unknown) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
const number = (value:unknown) => typeof value === "number" ? value.toFixed(1) : "—";
const list = (value:unknown) => Array.isArray(value) ? value.map(String) : [];

function JudgeInvocation({invocation}:{invocation:AIJudgeInvocation}) {
  const result=invocation.result;
  const criteria=["root_cause_score","evidence_score","object_discovery_score","fix_score","citation_score","safety_score","completeness_score"];
  const findings:[string,string[]][]=[["Unsupported claims",list(result.unsupported_claims)],["Missing evidence",list(result.missing_evidence)],["Incorrect objects",list(result.incorrect_objects)],["Incorrect entities",list(result.incorrect_entities)]];
  return <article className="evaluation-judge-invocation">
    <header><div><span>Judge {invocation.judge_index}</span><h4>{invocation.model}</h4><small>{invocation.provider} · {invocation.status}</small></div><strong>{invocation.weighted_score.toFixed(1)}</strong></header>
    <div className="evaluation-judge-scores">{criteria.map(key=><div key={key}><span>{key.replaceAll("_"," ")}</span><strong>{number(result[key])}</strong></div>)}</div>
    <p className="evaluation-judge-explanation">{String(result.explanation||"No explanation was returned.")}</p>
    {findings.map(([title,items])=><div className="evaluation-judge-findings" key={title}><h5>{title}</h5>{items.length?<ul>{items.map((item,index)=><li key={`${item}-${index}`}>{item}</li>)}</ul>:<p>None reported</p>}</div>)}
    {invocation.error&&<p className="form-message error">{invocation.error}</p>}
    <footer>{invocation.input_tokens+invocation.output_tokens} tokens · {(invocation.duration_ms/1000).toFixed(2)}s · ${invocation.estimated_cost_usd.toFixed(6)} · {invocation.retry_count} retries</footer>
  </article>;
}

function AIJudgeReport({row}:{row:EvaluationScenarioDetail}) {
  if(!row.judge_report) return <section className="evaluation-judge-report"><h3>AI Judge Report</h3><div className="evaluation-inline-empty"><h3>AI judge has not run</h3><p>Run AI judging for this evaluation result, then refresh this page to see its rubric scores and findings.</p></div></section>;
  return <section className="evaluation-judge-report"><div className="evaluation-judge-heading"><div><h3>AI Judge Report</h3><p>Judge version {row.judge_report.judge_version} · prompt {row.judge_report.prompt_version}</p></div><div><strong>{row.ai_judge_score?.toFixed(1)??"—"}</strong><small>Difference from deterministic: {row.judge_report.deterministic_difference.toFixed(1)}</small></div></div><div className="evaluation-judge-list">{row.judge_report.invocations.map(item=><JudgeInvocation invocation={item} key={item.judge_index}/>)}</div><details className="evaluation-detail-section"><summary>Raw normalized judge result</summary><pre>{render(row.judge_result)}</pre></details></section>;
}

export function EvaluationScenarioPage(){
  const {resultId=""}=useParams(); const [row,setRow]=useState<EvaluationScenarioDetail|null>(null); const [error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();getEvaluationScenario(resultId,controller.signal).then(setRow).catch(cause=>setError(cause instanceof Error?cause.message:"Unable to load scenario."));return()=>controller.abort();},[resultId]);
  if(error)return <div className="form-message error" role="alert">{error}</div>; if(!row)return <p>Loading scenario result…</p>;
  return <section className="evaluation-page"><Link className="evaluation-back" to="/app/evaluation">← Evaluation dashboard</Link><header className="evaluation-detail-heading"><div><p className="eyebrow">{row.domain} · {row.category} · {row.difficulty}</p><h2>{row.scenario_id}</h2><p>{row.question}</p></div><div><span>{row.execution_status}</span><strong>{row.deterministic_score?.toFixed(1)??"Not scored"}</strong><small>Deterministic score</small></div></header><div className="evaluation-detail-grid"><section><h3>Investigation result</h3><dl><dt>Investigation ID</dt><dd>{row.investigation_id||"Not created"}</dd><dt>Application status</dt><dd>{row.investigation_status||"Unavailable"}</dd><dt>AI judge score</dt><dd>{row.ai_judge_score?.toFixed(1)??"Not judged"}</dd></dl><h4>Answer</h4><p className="evaluation-answer">{row.answer||"No application answer was persisted."}</p></section><section><h3>Human review</h3><p>{row.human_review_required?"Required":"Not required"}</p>{row.human_review_reasons.length>0&&<ul>{row.human_review_reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>}<h3>Timing and usage</h3><pre>{render({timings:row.timings,usage_cost:row.usage_cost})}</pre></section></div><AIJudgeReport row={row}/>{[["Evidence",row.evidence],["Citations",row.citations],["Discovered objects",row.discovered_database_objects],["Recommendations",row.recommendations],["Deterministic validation",row.deterministic_details]].map(([title,value])=><details className="evaluation-detail-section" key={String(title)}><summary>{String(title)}</summary><pre>{render(value)}</pre></details>)}</section>;
}
