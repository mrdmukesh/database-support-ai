from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.cli.__main__ import all_scenarios, required_env
from evaluation.preflight import DATABASES
from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle


def main(output: Path) -> None:
    scenario = next(item for item in all_scenarios() if item.scenario_id == "shipping-pilot-001")
    lifecycle = SqlCmdDatabaseLifecycle(
        server=required_env("EVAL_SQL_SERVER"), username=required_env("EVAL_SQL_ADMIN"), password=required_env("EVAL_SQL_PASSWORD"),
        databases=DATABASES, allowed_hosts={"127.0.0.1","localhost"}, allowed_databases=set(DATABASES.values()),
    )
    lifecycle.reset(scenario)
    try:
        lifecycle.inject(scenario); verification=lifecycle.verify(scenario)
        db=pyodbc.connect("DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,14333;DATABASE=EvalShipping;"+f"UID={required_env('EVAL_SQL_ADMIN')};PWD={required_env('EVAL_SQL_PASSWORD')};Encrypt=yes;TrustServerCertificate=yes",timeout=15)
        cur=db.cursor()
        checks={
            "shipment":"SELECT BusinessKey,Status,CorrelationId,Details FROM eval.shipments WHERE BusinessKey='SHP-5001'",
            "work_order":"SELECT BusinessKey,Status,CorrelationId,Details FROM eval.transport_work_orders WHERE BusinessKey='EMPTY-SHP-5001'",
            "exception":"SELECT BusinessKey,Status,CorrelationId,Details FROM eval.exceptions WHERE CorrelationId='EVAL-SHIPPING-001'",
        }
        records={}
        for name,sql in checks.items():
            cur.execute(sql); columns=[item[0] for item in cur.description]; records[name]=[dict(zip(columns,row,strict=True)) for row in cur.fetchall()]
        cur.execute("""SELECT fk.name,cs.name,ct.name,cc.name,ps.name,pt.name,pc.name FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id JOIN sys.tables ct ON ct.object_id=fkc.parent_object_id JOIN sys.schemas cs ON cs.schema_id=ct.schema_id JOIN sys.columns cc ON cc.object_id=ct.object_id AND cc.column_id=fkc.parent_column_id JOIN sys.tables pt ON pt.object_id=fkc.referenced_object_id JOIN sys.schemas ps ON ps.schema_id=pt.schema_id JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.referenced_column_id WHERE cs.name='eval' AND ct.name='transport_work_orders' AND cc.name='ShipmentsId'""")
        relationships=[{"constraint":r[0],"child":f"{r[1]}.{r[2]}","child_key":r[3],"parent":f"{r[4]}.{r[5]}","parent_key":r[6],"source":"DECLARED_FOREIGN_KEY"} for r in cur.fetchall()]
        db.close()
        valid=bool(records["shipment"] and records["shipment"][0]["Status"]=="Delivered" and not records["work_order"] and records["exception"] and relationships)
        result={"scenario_id":scenario.scenario_id,"verified_at":datetime.now(timezone.utc).isoformat(),"database_engine":"sql_server","database_name":"EvalShipping","fixture_validity":"VALID" if valid else "VERIFICATION_FAILED","verification":verification,"records":records,"relationships":relationships}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,default=str),encoding="utf-8")
        if not valid: raise SystemExit("Native SQL Server fixture invalid")
    finally:
        lifecycle.cleanup(scenario)


if __name__ == "__main__": main(Path(sys.argv[1]))
