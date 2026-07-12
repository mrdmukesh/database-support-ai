import { useEffect, useState } from "react";
import { listFeedback, reviewFeedback } from "../../api/feedback-api";
import { loadInvestigationHistory } from "../../api/investigation-api";
import { listKnowledge, loadLearningDashboard } from "../../api/learning-api";
import { listWorkspaces } from "../../api/workspace-api";
import { useAuth } from "../../hooks/use-auth";
import type { InvestigationFeedback } from "../../models/feedback";
import type { InvestigationSummary } from "../../models/investigation";
import type { KnowledgeArticle, LearningDashboard } from "../../models/learning";
import type { Workspace } from "../../models/workspace";

export function LearningPage() {
  const { organizationId }=useAuth(); const [workspaces,setWorkspaces]=useState<Workspace[]>([]); const [workspaceId,setWorkspaceId]=useState("");
  const [dashboard,setDashboard]=useState<LearningDashboard|null>(null), [investigations,setInvestigations]=useState<InvestigationSummary[]>([]), [feedback,setFeedback]=useState<InvestigationFeedback[]>([]), [knowledge,setKnowledge]=useState<KnowledgeArticle[]>([]); const [loading,setLoading]=useState(true), [error,setError]=useState<string|null>(null);
  useEffect(() => { if (!organizationId) return; const controller=new AbortController(); void listWorkspaces(organizationId,controller.signal).then((rows)=>{setWorkspaces(rows);setWorkspaceId((current)=>current||rows[0]?.id||"");}).catch((cause)=>setError(cause instanceof Error?cause.message:"Learning workflow failed.")); return()=>controller.abort(); },[organizationId]);
  async function load(signal?:AbortSignal) { if(!organizationId||!workspaceId){setLoading(false);return;} setLoading(true);setError(null);try{const [d,i,f,k]=await Promise.all([loadLearningDashboard(organizationId,workspaceId,signal),loadInvestigationHistory(organizationId,workspaceId,undefined,signal),listFeedback(organizationId,workspaceId,"PENDING_APPROVAL",signal),listKnowledge(organizationId,workspaceId,signal)]);setDashboard(d);setInvestigations(i.filter((x)=>["OPEN","AI_ANSWERED","DEVELOPER_REVIEW"].includes(x.status)));setFeedback(f);setKnowledge(k);}catch(cause){if((cause as {name?:string})?.name!=="AbortError")setError(cause instanceof Error?cause.message:"Learning workflow failed.");}finally{if(!signal?.aborted)setLoading(false);}}
  useEffect(()=>{const controller=new AbortController();void load(controller.signal);return()=>controller.abort();},[organizationId,workspaceId]);
  async function review(id:string,approved:boolean){setError(null);try{await reviewFeedback(id,{approved,title:null,review_notes:approved?"Approved from learning dashboard.":"Rejected from learning dashboard.",confidence_after_approval:0.95});await load();}catch(cause){setError(cause instanceof Error?cause.message:"Feedback review failed.");}}
  return <section className="management-page" aria-labelledby="learning-title"><h2 id="learning-title">Human-approved learning loop</h2><p>Feedback becomes reusable knowledge only after explicit approval. It is not automatic model training.</p>
    <label>Workspace<select aria-label="Workspace" value={workspaceId} onChange={(e)=>setWorkspaceId(e.target.value)}><option value="">Select a workspace</option>{workspaces.map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
    {error?<div role="alert">{error}</div>:null}{loading?<p role="status">Loading learning workflow...</p>:<>
      {dashboard?<dl><dt>Open investigations</dt><dd>{dashboard.open_investigations}</dd><dt>Pending feedback</dt><dd>{dashboard.pending_feedback}</dd><dt>Pending approval</dt><dd>{dashboard.pending_approval}</dd><dt>Approved knowledge</dt><dd>{dashboard.approved_knowledge}</dd></dl>:null}
      <section><h3>Investigations available for review</h3>{investigations.length?<ul>{investigations.map((x)=><li key={x.id}>{x.user_question} — {x.status}</li>)}</ul>:<p>No open investigations.</p>}</section>
      <section><h3>Feedback review</h3>{feedback.length?<ul>{feedback.map((x)=><li key={x.id}>{x.rating}: {x.actual_root_cause||"Not provided"} <button onClick={()=>void review(x.id,true)}>Approve</button><button onClick={()=>void review(x.id,false)}>Reject</button></li>)}</ul>:<p>No feedback awaiting approval.</p>}</section>
      <section><h3>Approved knowledge</h3>{knowledge.length?<ul>{knowledge.map((x)=><li key={x.id}>{x.title}: {x.actual_root_cause||"Not recorded"}</li>)}</ul>:<p>No approved knowledge yet.</p>}</section>
    </>}</section>;
}
