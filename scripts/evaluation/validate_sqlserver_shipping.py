from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.cli.__main__ import required_env


def main(output: Path) -> None:
    connection = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,14333;DATABASE=EvalShipping;"
        f"UID={required_env('EVAL_SQL_ADMIN')};PWD={required_env('EVAL_SQL_PASSWORD')};Encrypt=yes;TrustServerCertificate=yes",
        timeout=15,
    )
    cursor = connection.cursor()
    cursor.execute("""
SELECT o.type_desc, s.name, o.name
FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
WHERE s.name='eval' AND o.type IN ('U','V','P','FN','IF','TF','TR')
ORDER BY o.type_desc,o.name
""")
    objects = [{"object_type": row[0], "schema": row[1], "object_name": row[2]} for row in cursor.fetchall()]
    cursor.execute("""
SELECT cs.name child_schema, ct.name child_table, cc.name child_column,
       ps.name parent_schema, pt.name parent_table, pc.name parent_column, fk.name constraint_name
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
JOIN sys.tables ct ON ct.object_id=fkc.parent_object_id
JOIN sys.schemas cs ON cs.schema_id=ct.schema_id
JOIN sys.columns cc ON cc.object_id=ct.object_id AND cc.column_id=fkc.parent_column_id
JOIN sys.tables pt ON pt.object_id=fkc.referenced_object_id
JOIN sys.schemas ps ON ps.schema_id=pt.schema_id
JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.referenced_column_id
WHERE cs.name='eval'
ORDER BY ct.name,cc.name
""")
    foreign_keys = [{"child_schema":r[0],"child_table":r[1],"child_column":r[2],"parent_schema":r[3],"parent_table":r[4],"parent_column":r[5],"constraint":r[6],"relationship_source":"DECLARED_FOREIGN_KEY","confidence":1.0,"accepted":True} for r in cursor.fetchall()]
    cursor.execute("""
SELECT s.name,t.name,c.name,ty.name
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.indexes i ON i.object_id=t.object_id AND i.is_primary_key=1
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id
JOIN sys.types ty ON ty.user_type_id=c.user_type_id
WHERE s.name='eval' ORDER BY t.name,ic.key_ordinal
""")
    primary_keys = [{"schema":r[0],"table":r[1],"column":r[2],"data_type":r[3]} for r in cursor.fetchall()]
    expected = {
        "tables": ["shipments","transport_work_orders","exceptions"],
        "views": ["vw_shipping_operations_1"],
        "procedures": ["usp_shipping_workflow_1"],
        "functions": ["fn_shipping_active_status"],
        "triggers": ["tr_bookings_audit"],
    }
    names = {(item["object_type"],item["object_name"]) for item in objects}
    type_map = {"tables":"USER_TABLE","views":"VIEW","procedures":"SQL_STORED_PROCEDURE","functions":"SQL_SCALAR_FUNCTION","triggers":"SQL_TRIGGER"}
    validations = [{"object_type":kind[:-1],"schema":"eval","object_name":name,"validation_status":"VALID" if (type_map[kind],name) in names else "MISSING"} for kind,values in expected.items() for name in values]
    shipping_fk = [item for item in foreign_keys if item["child_table"] == "transport_work_orders" and item["child_column"] == "ShipmentsId"]
    report = {
        "database_engine":"sql_server","database_name":"EvalShipping","schema":"eval",
        "objects":objects,"primary_keys":primary_keys,"foreign_keys":foreign_keys,"validations":validations,
        "shipping_relationship":shipping_fk,
        "passed":all(item["validation_status"]=="VALID" for item in validations) and len(shipping_fk)==1,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    connection.close()
    if not report["passed"]: raise SystemExit("EvalShipping schema validation failed")
    print(json.dumps({"passed":True,"objects":len(objects),"foreign_keys":len(foreign_keys),"shipping_relationship":shipping_fk},indent=2))


if __name__ == "__main__": main(Path(sys.argv[1]))
