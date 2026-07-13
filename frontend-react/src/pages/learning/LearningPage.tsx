import { useEffect, useState } from "react";
import { listFeedback, reviewFeedback } from "../../api/feedback-api";
import { loadInvestigationHistory } from "../../api/investigation-api";
import { listKnowledge, loadLearningDashboard } from "../../api/learning-api";
import { listWorkspaces } from "../../api/workspace-api";
import { FeedbackReviewWorkspace } from "../../components/learning/FeedbackReviewWorkspace";
import { useAuth } from "../../hooks/use-auth";
import type { FeedbackReviewRequest, InvestigationFeedback } from "../../models/feedback";
import type { InvestigationSummary } from "../../models/investigation";
import type { KnowledgeArticle, LearningDashboard } from "../../models/learning";
import type { Workspace } from "../../models/workspace";

export function LearningPage() {
  const { organizationId } = useAuth();
  const [workspaces,setWorkspaces]=useState<Workspace[]>([]), [workspaceId,setWorkspaceId]=useState("");
  const [dashboard,setDashboard]=useState<LearningDashboard|null>(null), [investigations,setInvestigations]=useState<InvestigationSummary[]>([]), [feedback,setFeedback]=useState<InvestigationFeedback[]>([]), [knowledge,setKnowledge]=useState<KnowledgeArticle[]>([]);
  const [loading,setLoading]=useState(true), [error,setError]=useState<string|null>(null), [success,setSuccess]=useState<string|null>(null), [reviewing,setReviewing]=useState<string|null>(null);

  useEffect(() => { if (!organizationId) return; const controller=new AbortController(); void listWorkspaces(organizationId,controller.signal).then((rows)=>{setWorkspaces(rows);setWorkspaceId((current)=>current||rows[0]?.id||"");}).catch((cause)=>setError(cause instanceof Error?cause.message:"Learning workflow failed.")); return()=>controller.abort(); },[organizationId]);
  async function load(signal?:AbortSignal) { if(!organizationId||!workspaceId)return; setLoading(true);setError(null);try{const [d,i,f,k]=await Promise.all([loadLearningDashboard(organizationId,workspaceId,signal),loadInvestigationHistory(organizationId,workspaceId,undefined,signal),listFeedback(organizationId,workspaceId,undefined,signal),listKnowledge(organizationId,workspaceId,signal)]);setDashboard(d);setInvestigations(i);setFeedback(f);setKnowledge(k);}catch(cause){if((cause as {name?:string})?.name!=="AbortError")setError(cause instanceof Error?cause.message:"Learning workflow failed.");}finally{if(!signal?.aborted)setLoading(false);}}
  useEffect(()=>{const controller=new AbortController();void load(controller.signal);return()=>controller.abort();},[organizationId,workspaceId]);
  async function review(id:string,payload:FeedbackReviewRequest){setError(null);setSuccess(null);setReviewing(id);try{await reviewFeedback(id,payload);setSuccess(payload.approved?"Feedback approved as workspace knowledge.":"Feedback rejected and excluded from knowledge.");await load();}catch(cause){setError(cause instanceof Error?cause.message:"Feedback review failed.");throw cause;}finally{setReviewing(null);}}

  return <section className="management-page learning-page" aria-labelledby="learning-title">
    <header className="ui-page-header"><div><p className="eyebrow">Governed learning</p><h2 id="learning-title">Feedback Review</h2><p>Compare investigation evidence with human corrections before creating reusable workspace knowledge. This workflow does not train model weights.</p></div><label className="ui-form-field workspace-picker">Workspace<select className="ui-control" aria-label="Workspace" value={workspaceId} onChange={(e)=>setWorkspaceId(e.target.value)}><option value="">Select a workspace</option>{workspaces.map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label></header>
    {error?<div className="ui-alert" role="alert"><strong>Review workspace unavailable</strong><span>{error}</span></div>:null}{success?<div className="ui-alert" data-tone="success" role="status">{success}</div>:null}
    {loading?<div className="ui-card ui-skeleton" role="status" aria-label="Loading feedback review"><span/><span/><span/><span/><span/></div>:<>
      {dashboard?<section className="learning-metrics" aria-label="Learning workflow summary"><article><span>Open investigations</span><strong>{dashboard.open_investigations}</strong></article><article><span>Pending feedback</span><strong>{dashboard.pending_feedback}</strong></article><article><span>Pending approval</span><strong>{dashboard.pending_approval}</strong></article><article><span>Approved knowledge</span><strong>{dashboard.approved_knowledge}</strong></article></section>:null}
      <section aria-labelledby="review-queue-title"><div className="section-heading"><div><h3 id="review-queue-title">Review queue</h3><p>Pending decisions appear first; completed records remain visible for audit context.</p></div></div>{feedback.length?<div className="feedback-review-list">{[...feedback].sort((a,b)=>Number(b.status==="PENDING_APPROVAL")-Number(a.status==="PENDING_APPROVAL")).map((item)=><FeedbackReviewWorkspace key={item.id} feedback={item} investigation={investigations.find((x)=>x.id===item.investigation_id)} workspace={workspaces.find((x)=>x.id===item.workspace_id)} busy={reviewing===item.id} onReview={review}/>)}</div>:<div className="ui-empty"><strong>No feedback to review</strong><p>Submitted feedback for this workspace will appear here.</p></div>}</section>
      <section className="ui-card approved-knowledge" aria-labelledby="approved-knowledge-title"><div className="ui-card-header"><h3 id="approved-knowledge-title">Approved knowledge</h3><p>Active reviewed records available to workspace-scoped retrieval.</p></div>{knowledge.length?<ul>{knowledge.map((x)=><li key={x.id}><strong>{x.title}</strong><span>{x.actual_root_cause||"Root cause not recorded"}</span></li>)}</ul>:<div className="ui-empty"><strong>No approved knowledge yet</strong></div>}</section>
    </>}
  </section>;
}
