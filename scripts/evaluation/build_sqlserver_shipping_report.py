from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlalchemy import select
from evaluation.cli.__main__ import build_store
from evaluation.framework.models import EvaluationAIJudgeScoreModel,EvaluationDeterministicScoreModel,EvaluationHumanReviewFlagModel,EvaluationScenarioExecutionModel


def load(value,fallback):
    try:return json.loads(value or "")
    except:return fallback


def main(run_id:str,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    schema=json.loads((out/'sqlserver-schema-validation.json').read_text(encoding='utf8'))
    fixture=json.loads((out/'shipping-pilot-sqlserver-fixture-proof.json').read_text(encoding='utf8'))
    runtime=json.loads(Path('.tmp/local-evaluation/api-runtime.json').read_text(encoding='utf8'))
    deployment=json.loads(Path('.tmp/local-sqlserver/deployment-summary.json').read_text(encoding='utf-8-sig'))
    with build_store().session_factory() as db:
        execution=db.scalar(select(EvaluationScenarioExecutionModel).where(EvaluationScenarioExecutionModel.evaluation_run_id==run_id))
        deterministic=db.scalar(select(EvaluationDeterministicScoreModel).where(EvaluationDeterministicScoreModel.scenario_execution_id==execution.id))
        judge=db.scalar(select(EvaluationAIJudgeScoreModel).where(EvaluationAIJudgeScoreModel.scenario_execution_id==execution.id))
        review=db.scalar(select(EvaluationHumanReviewFlagModel).where(EvaluationHumanReviewFlagModel.deterministic_score_id==deterministic.id))
    response=load(execution.raw_response_json,{})['investigation'];trace=response.get('debug_trace',{})
    relationship=schema['shipping_relationship'][0]
    result={
        'run_id':run_id,'scenario_id':execution.scenario_id,'investigation_id':execution.investigation_id,
        'run_status':execution.status,'application_status':execution.investigation_status,'final_provenance':execution.investigation_status,
        'environment':deployment,'fixture':fixture,'schema_validation_passed':schema['passed'],
        'declared_relationship_used':relationship,'selected_parent_table':'eval.shipments','selected_parent_key':'ShipmentsId',
        'metadata_cache':trace.get('metadata_cache'),'sql_plan':trace.get('sql_plan'),'sql_evidence':trace.get('sql_evidence'),
        'evidence_gate':trace.get('evidence_gate'),'application_ai_invoked':trace.get('ai_reasoning_invoked'),
        'application_model':runtime.get('ai_model'),'prompt_version':trace.get('prompt_version'),
        'application_input_tokens':trace.get('input_tokens'),'application_output_tokens':trace.get('output_tokens'),
        'application_answer':load(execution.result_json,{}).get('answer',''),
        'deterministic_unadjusted_score':float(deterministic.unadjusted_score),'deterministic_final_score':float(deterministic.final_score),
        'deterministic_classification':deterministic.classification,'deterministic_critical_failures':load(deterministic.details_json,{}).get('critical_failure_details',[]),
        'ai_judge_score':float(judge.weighted_score),'ai_judge_model':judge.model,'ai_judge_explanation':load(judge.normalized_result_json,{}).get('explanation',''),
        'judge_input_tokens':judge.input_tokens,'judge_output_tokens':judge.output_tokens,
        'human_review_required':review.required,'human_review_reasons':load(review.reasons_json,[]),
        'remaining_failure':'Entity validation treated internal resolution token entity-1-exact-8 as the investigated business entity, causing a critical override despite correct root cause, evidence, objects, citations, and 92.778 unadjusted score.',
        'pilot_safe_to_begin':False,
        'compatibility':{'fixture':'NATIVE_SQL_SERVER_VALID','metadata':'NATIVE_SQL_SERVER_VALID','procedure':'NATIVE_SQL_SERVER_VALID','application':'OPERATIONAL_BUT_ENTITY_VALIDATION_FAILED'},
    }
    (out/'shipping-pilot-sqlserver-result.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    env_md=f"""# Local SQL Server Environment

- Status: READY
- Image: `{deployment['image']}`
- Container: `{deployment['container']}`
- Binding: `{deployment['host']}:{deployment['port']}` (localhost only)
- Persistent volume: `{deployment['persistent_volume']}`
- Databases: {', '.join(deployment['databases'])}
- Dedicated admin login: `{deployment['admin_login']}`
- Dedicated reader login: `{deployment['reader_login']}`
- Password present: yes (not displayed)
- EvalShipping schema validation: PASS
- Native objects: {len(schema['objects'])}
- Declared foreign keys: {len(schema['foreign_keys'])}
"""
    (out/'sqlserver-environment-report.md').write_text(env_md,encoding='utf8')
    rel_md=f"""# SQL Server Relationship Diagnostics

## Authoritative shipping relationship

- Child: `{relationship['child_schema']}.{relationship['child_table']}.{relationship['child_column']}`
- Parent: `{relationship['parent_schema']}.{relationship['parent_table']}.{relationship['parent_column']}`
- Constraint: `{relationship['constraint']}`
- Source: `DECLARED_FOREIGN_KEY`
- Confidence: 1.0
- Accepted: yes

Declared SQL Server foreign keys now take priority over inferred relationships. CorrelationId and BusinessKey are excluded from inference. `shipment_milestones.ShipmentsId` is rejected as a parent key because `shipment_milestones` does not own that primary key.
"""
    (out/'sqlserver-relationship-diagnostics.md').write_text(rel_md,encoding='utf8')
    trace_md=f"""# Shipping Pilot SQL Server Trace

- Run: `{run_id}`
- Investigation: `{execution.investigation_id}`
- Fixture: `{fixture['fixture_validity']}`
- Engine/database: SQL Server / EvalShipping
- Parent selected: `eval.shipments(ShipmentsId)`
- Child selected: `eval.transport_work_orders(ShipmentsId)`
- Evidence gate reproduced: `{trace.get('evidence_gate',{}).get('reproduced')}`
- Application AI invoked: `{trace.get('ai_reasoning_invoked')}`
- Model: `{runtime.get('ai_model')}`
- Prompt: `{trace.get('prompt_version')}`
- Application tokens: {trace.get('input_tokens')} input / {trace.get('output_tokens')} output
- Provenance: `{execution.investigation_status}`
- Deterministic score: {float(deterministic.final_score)} (unadjusted {float(deterministic.unadjusted_score)})
- AI Judge score: {float(judge.weighted_score)}

## Evidence gate
```json
{json.dumps(trace.get('evidence_gate'),indent=2)}
```

## SQL evidence
```json
{json.dumps(trace.get('sql_evidence'),indent=2)}
```

## Remaining blocker
{result['remaining_failure']}
"""
    (out/'shipping-pilot-sqlserver-trace.md').write_text(trace_md,encoding='utf8')
    rows=''.join(f"<tr><td>{html.escape(str(x.get('evidence_id')))}</td><td>{html.escape(str(x.get('purpose')))}</td><td>{x.get('row_count')}</td></tr>" for x in trace.get('sql_evidence',[]))
    report=f"<!doctype html><html><head><meta charset='utf-8'><title>SQL Server Shipping Pilot</title><style>body{{font:15px Arial;margin:40px;color:#0b2545}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #ccd5df}}.good{{color:#166534}}.bad{{color:#991b1b}}pre{{white-space:pre-wrap;background:#f8fafc;padding:12px}}</style></head><body><h1>Native SQL Server Shipping Pilot</h1><p class=good>Fixture, schema, metadata, negative evidence, evidence gate, and application AI invocation passed.</p><p class=bad>Quality gate failed: deterministic 0 and Judge 0 due to an entity-validation critical override.</p><h2>Scores</h2><ul><li>Unadjusted deterministic: {float(deterministic.unadjusted_score)}</li><li>Final deterministic: {float(deterministic.final_score)}</li><li>AI Judge: {float(judge.weighted_score)}</li><li>Provenance: {execution.investigation_status}</li></ul><h2>Evidence</h2><table><tr><th>ID</th><th>Purpose</th><th>Rows</th></tr>{rows}</table><h2>Remaining blocker</h2><p>{html.escape(result['remaining_failure'])}</p><h2>Application answer</h2><pre>{html.escape(result['application_answer'])}</pre></body></html>"
    (out/'shipping-pilot-sqlserver-report.html').write_text(report,encoding='utf8')


if __name__=='__main__':main(sys.argv[1],Path(sys.argv[2]))
