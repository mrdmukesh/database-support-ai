from __future__ import annotations

import html
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "study_materials"


SLIDES = [
    ("Database Support AI", ["Generic relational database investigation platform", "Evidence-first troubleshooting for support engineers, DBAs, and developers", "Works from metadata, relationships, safe SQL, procedure analysis, documents, reports, and approved knowledge"]),
    ("Problem It Solves", ["Legacy systems fail in production but root cause is scattered across tables, procedures, logs, jobs, and documents", "The app collects read-only evidence and creates a structured investigation answer", "It avoids hardcoded business rules and adapts to ERP, Clinic, School, CRM, Warehouse, and other schemas"]),
    ("High-Level Architecture", ["Static HTML UI talks to FastAPI backend", "Internal app database stores users, workspaces, connections, investigations, feedback, reports, and knowledge", "Target customer database is separate and accessed through database adapters", "Report generator outputs HTML, PDF, Word, and Excel"]),
    ("Main User Flow", ["Login and choose workspace", "Create or test target database connection", "Upload runbooks, data dictionaries, known issues, and test docs", "Ask an investigation question", "Download report and submit feedback after fix"]),
    ("Investigation Pipeline", ["1. Detect intent and extract entities", "2. Parse main problem phrase to identify target object and parent object", "3. Discover metadata, relationships, procedures, views, documents, and approved knowledge", "4. Generate safe evidence SQL", "5. Execute read-only SQL and collect evidence", "6. Evidence gate validates issue reproduction", "7. Rank root causes and generate report"]),
    ("Generic Target Discovery", ["Target object comes from the main problem phrase, not possible causes", "Example: 'appointments missing claims caused by lab issues' means target=claims, parent=appointments", "Secondary cause terms support analysis but cannot override the target", "Metadata resolves nouns to real tables and relationships"]),
    ("Evidence Gate", ["Before root cause analysis, the engine checks key existence, condition existence, affected rows, and parent-child relationship", "If evidence is missing, the app reports that the issue could not be reproduced", "No fix is recommended until connected database evidence confirms the issue"]),
    ("Database Adapter Layer", ["BaseDatabaseAdapter exposes generic methods such as list_tables, list_columns, list_indexes, list_foreign_keys, list_procedures, explain_query, execute_read_only_query", "MySQL, SQL Server, PostgreSQL, SQLite, and Oracle placeholder adapters isolate dialect differences", "The investigation engine calls adapter methods instead of embedding engine-specific SQL everywhere"]),
    ("Safety Model", ["Read-only SQL validation blocks INSERT, UPDATE, DELETE, MERGE, ALTER, DROP, TRUNCATE, CREATE, EXEC, CALL, GRANT, and REVOKE", "LLM, when enabled, does not run SQL directly", "Every conclusion should cite evidence; low evidence means lower confidence"]),
    ("Report Generation", ["Investigation creates structured report object", "HTML report for viewing", "PDF for sharing", "Word document for editing", "Excel workbook for evidence and SQL", "History saved by timestamp and investigation ID"]),
    ("Human-Approved Learning Loop", ["The model does not train itself automatically", "Developer feedback is stored after investigation", "DBA/Lead/Admin reviews feedback", "Approved feedback becomes a knowledge article", "Only approved human-verified knowledge is used in future answers"]),
    ("How To Explain The App", ["It is not a chatbot that guesses", "It is an evidence collection and reasoning platform", "Python deterministic engine handles safety, metadata, SQL, and evidence", "Optional LLM explains evidence and writes professional RCA text", "Reports make findings usable by SQL developers and DBAs"]),
]


TECH_DOC = """# Database Support AI - Technical Study Document

## 1. Purpose

Database Support AI is a generic relational database investigation platform. It helps support engineers, DBAs, and developers investigate production questions such as missing records, duplicate records, slow queries, failed jobs, process-flow breaks, impact analysis, and health assessment.

The key design principle is evidence-first reasoning. The application should not guess root causes from the wording of a question. It discovers metadata, relationships, stored procedures, logs, documents, approved knowledge, and read-only SQL evidence before producing a conclusion.

## 2. Architecture Summary

The application has four main layers:

1. Static browser UI
2. FastAPI backend
3. Internal application database
4. Target/customer database adapters

The internal application database stores application data such as users, sessions, organizations, workspaces, database connection records, document metadata, investigations, feedback, reports, and approved knowledge articles. This is separate from the customer database being investigated.

The target/customer database is accessed only through database connection records and adapter classes. The investigation engine should treat the customer database as read-only during evidence collection.

## 3. Major Backend Modules

### API and Routers

- `legacydb_copilot.api` creates the FastAPI app.
- `routers.auth` handles login and sessions.
- `routers.workspaces` manages workspaces.
- `routers.databases` manages target database connections and tests.
- `routers.documents` handles document uploads.
- `routers.chat` runs investigations.
- `routers.learning` handles feedback, approval, and knowledge.
- `routers.reports` serves generated reports.

### Internal Data Model

Important internal tables include:

- organizations
- users
- workspaces
- database_connections
- documents and document_versions
- investigations
- investigation_feedback
- knowledge_articles
- chat_conversations and chat_messages
- audit_logs

### Target Database Adapter Layer

The adapter layer separates database-specific behavior from the investigation engine.

Generic adapter methods include:

- `list_tables()`
- `list_columns()`
- `list_indexes()`
- `list_foreign_keys()`
- `list_views()`
- `list_procedures()`
- `get_procedure_definition()`
- `explain_query()`
- `execute_read_only_query()`

Current adapter classes:

- `BaseDatabaseAdapter`
- `MySQLAdapter`
- `SQLServerAdapter`
- `PostgreSQLAdapter`
- `SQLiteAdapter`
- `OracleAdapter` placeholder

Dialect-specific syntax such as MySQL `LIMIT`, SQL Server `TOP`, SQLite `EXPLAIN QUERY PLAN`, and catalog queries belongs in adapters.

## 4. Investigation Flow

When the user asks a question, the `/chat/ask` route runs the investigation pipeline:

1. Load the active workspace and target database connection.
2. Detect the question intent.
3. Extract entities such as business keys, statuses, and procedure names.
4. Parse the main problem phrase.
5. Discover database metadata.
6. Rank relevant objects.
7. Analyze stored procedures.
8. Generate read-only evidence SQL.
9. Execute safe evidence queries.
10. Expand related ID evidence.
11. Correlate evidence.
12. Build evidence focus.
13. Run the evidence gate.
14. Generate hypotheses and reason over evidence.
15. Optionally use LLM reasoning over collected evidence only.
16. Calculate explainable confidence.
17. Compose and generate reports.
18. Store investigation history.

## 5. Generic Target Object Discovery

The target object must come from the main problem phrase, not from possible causes.

Examples:

- `appointments are missing claims` means target object is claims and parent object is appointments.
- `orders are missing invoices` means target object is invoices and parent object is orders.
- `ticket has duplicate comments` means target object is comments and parent object is tickets.
- `student has duplicate payments` means target object is payments and parent object is students.

Secondary cause terms such as lab order, batch, shipment, payment, workflow, routing, retry, or import can support root-cause analysis but cannot override the target object.

## 6. Evidence Gate

Before root cause analysis, the app validates:

- supplied business key exists
- reported condition exists
- affected rows exist
- parent-child relationship exists

If these checks fail, the app must stop root cause analysis and report:

`Reported issue could not be reproduced from connected database evidence.`

The app should not recommend a fix when the issue is not reproduced.

## 7. SQL Safety

The safe SQL layer only allows read-only investigation statements. It blocks:

- INSERT
- UPDATE
- DELETE
- MERGE
- ALTER
- DROP
- TRUNCATE
- CREATE
- EXEC / CALL
- GRANT / REVOKE

The app may run SELECT, supported metadata queries, and explain-plan queries through the adapter layer.

## 8. Root Cause Reasoning

Root-cause ranking is evidence-driven. Strong evidence includes:

- confirmed affected rows
- parent-child relationship proof
- procedure that writes the affected object
- error log referencing the affected key/object/procedure
- job history evidence
- document or approved knowledge support

The app separates:

- confirmed facts
- inferred findings
- hypotheses
- missing evidence
- most likely root cause

## 9. Optional LLM Layer

The deterministic Python engine handles safety, metadata, SQL generation, evidence collection, evidence gate, and report object creation.

The LLM, when enabled, may help with:

- understanding user intent
- generating hypotheses
- explaining stored procedure logic
- reasoning over collected evidence
- writing root cause analysis
- generating test cases
- generating proof-of-fix steps

The LLM must not execute SQL. It only reasons over evidence collected by the app.

## 10. Report Generation

When an investigation completes, the app generates a structured report and saves outputs in report history.

Supported output types:

- HTML
- PDF
- Word
- Excel

The report includes executive summary, scope, methodology, evidence collected, root-cause analysis, technical analysis, recommended SQL, recommended fix, test cases, proof of fix, rollback plan, risks, lessons learned, references, and appendix.

## 11. Human-Approved Learning Loop

The app does not train itself automatically.

After an investigation:

1. Developer submits feedback.
2. Feedback goes to pending approval.
3. DBA/Lead/Admin reviews.
4. If approved, a knowledge article is created.
5. Approved knowledge is used in future answers.

Only approved human-verified fixes should influence future responses.

## 12. How To Present This App

Use this explanation:

Database Support AI is an evidence-first production support platform. It connects to a customer database through safe read-only adapters, discovers metadata and relationships, collects proof using generated SQL, analyzes stored procedures and documents, then creates a professional RCA report. It is generic because business meaning comes from the connected database, uploaded documents, approved knowledge, and evidence rather than hardcoded table names.

## 13. Current Strengths

- Generic target object parsing
- Metadata-driven parent-child SQL
- Evidence gate before RCA
- Database adapter layer
- Read-only SQL safety
- Professional report generation
- Feedback and approval-based learning loop
- Optional LLM reasoning over evidence

## 14. Future Enhancements

- Add richer Oracle support
- Add real vector indexing for document chunks
- Add job scheduler for open investigation reminders
- Add deeper performance evidence per database engine
- Add visual process-flow graph in reports
- Add RBAC screens for approval workflows
"""


MERMAID = """flowchart LR
    UI[Browser UI\\nHTML/JavaScript] --> API[FastAPI Backend]
    API --> Auth[Auth / RBAC]
    API --> InternalDB[(Internal App DB\\nusers, workspaces, sessions, reports, knowledge)]
    API --> Chat[/chat/ask Investigation Route]
    Chat --> Intent[Intent + Entity Extraction]
    Intent --> Problem[Main Problem Phrase Parser\\ntarget, parent, cause terms]
    Problem --> Metadata[Metadata Discovery]
    Metadata --> Adapter[Database Adapter Layer]
    Adapter --> TargetDB[(Target Customer Database)]
    Metadata --> Planner[Safe SQL Planner]
    Planner --> Safety[Read-only SQL Safety]
    Safety --> Evidence[Evidence Execution]
    Evidence --> Gate[Evidence Gate]
    Gate --> Reasoning[Deterministic Reasoning]
    Reasoning --> LLM[Optional LLM\\nevidence-only reasoning]
    Reasoning --> Report[Report Composer]
    LLM --> Report
    Report --> Outputs[HTML / PDF / Word / Excel]
    Outputs --> History[(Report History)]
    Reasoning --> Feedback[Developer Feedback]
    Feedback --> Approval[DBA/Admin Approval]
    Approval --> Knowledge[(Approved Knowledge)]
    Knowledge --> Chat
"""


SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="900" viewBox="0 0 1500 900">
<defs>
  <style>
    .box { fill:#f8fafc; stroke:#334155; stroke-width:2; rx:10; }
    .core { fill:#e0f2fe; stroke:#0369a1; stroke-width:2; rx:10; }
    .data { fill:#ecfdf5; stroke:#047857; stroke-width:2; rx:10; }
    .warn { fill:#fff7ed; stroke:#c2410c; stroke-width:2; rx:10; }
    .title { font-family:Arial; font-size:30px; font-weight:bold; fill:#0f172a; }
    .text { font-family:Arial; font-size:17px; fill:#0f172a; }
    .small { font-family:Arial; font-size:14px; fill:#334155; }
    .arrow { stroke:#475569; stroke-width:2.2; marker-end:url(#arrow); fill:none; }
  </style>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L0,6 L9,3 z" fill="#475569"/>
  </marker>
</defs>
<text x="50" y="55" class="title">Database Support AI - Architecture and Investigation Flow</text>

<rect x="50" y="110" width="210" height="90" class="box"/>
<text x="75" y="145" class="text">Browser UI</text>
<text x="75" y="172" class="small">Static HTML / JavaScript</text>

<rect x="330" y="110" width="230" height="90" class="core"/>
<text x="360" y="145" class="text">FastAPI Backend</text>
<text x="360" y="172" class="small">Routers + Services</text>

<rect x="650" y="95" width="260" height="120" class="data"/>
<text x="675" y="130" class="text">Internal App DB</text>
<text x="675" y="157" class="small">users, sessions, workspaces</text>
<text x="675" y="180" class="small">investigations, feedback</text>
<text x="675" y="203" class="small">reports, knowledge</text>

<rect x="1010" y="95" width="280" height="120" class="data"/>
<text x="1035" y="130" class="text">Target Database</text>
<text x="1035" y="157" class="small">MySQL / SQL Server</text>
<text x="1035" y="180" class="small">PostgreSQL / SQLite</text>
<text x="1035" y="203" class="small">Oracle later</text>

<rect x="330" y="280" width="230" height="95" class="core"/>
<text x="355" y="315" class="text">/chat/ask</text>
<text x="355" y="342" class="small">Investigation route</text>

<rect x="50" y="460" width="220" height="100" class="box"/>
<text x="75" y="495" class="text">Intent + Entities</text>
<text x="75" y="522" class="small">question type, keys</text>

<rect x="330" y="460" width="230" height="100" class="box"/>
<text x="355" y="495" class="text">Problem Parser</text>
<text x="355" y="522" class="small">target, parent, causes</text>

<rect x="620" y="460" width="230" height="100" class="box"/>
<text x="645" y="495" class="text">Metadata Discovery</text>
<text x="645" y="522" class="small">tables, FKs, indexes</text>

<rect x="920" y="460" width="240" height="100" class="box"/>
<text x="945" y="495" class="text">Safe SQL Planner</text>
<text x="945" y="522" class="small">read-only evidence</text>

<rect x="1230" y="460" width="220" height="100" class="warn"/>
<text x="1255" y="495" class="text">Evidence Gate</text>
<text x="1255" y="522" class="small">prove issue first</text>

<rect x="250" y="665" width="240" height="110" class="core"/>
<text x="275" y="700" class="text">Reasoning Engine</text>
<text x="275" y="727" class="small">facts, inferences</text>
<text x="275" y="750" class="small">hypotheses, confidence</text>

<rect x="590" y="665" width="230" height="110" class="box"/>
<text x="615" y="700" class="text">Optional LLM</text>
<text x="615" y="727" class="small">evidence-only text</text>

<rect x="910" y="665" width="230" height="110" class="core"/>
<text x="935" y="700" class="text">Report Generator</text>
<text x="935" y="727" class="small">HTML, PDF, Word</text>
<text x="935" y="750" class="small">Excel evidence</text>

<rect x="1210" y="665" width="230" height="110" class="data"/>
<text x="1235" y="700" class="text">Learning Loop</text>
<text x="1235" y="727" class="small">feedback approval</text>
<text x="1235" y="750" class="small">knowledge articles</text>

<path class="arrow" d="M260 155 L330 155"/>
<path class="arrow" d="M560 155 L650 155"/>
<path class="arrow" d="M560 155 C760 250 875 250 1010 155"/>
<path class="arrow" d="M445 200 L445 280"/>
<path class="arrow" d="M445 375 L160 460"/>
<path class="arrow" d="M270 510 L330 510"/>
<path class="arrow" d="M560 510 L620 510"/>
<path class="arrow" d="M850 510 L920 510"/>
<path class="arrow" d="M1160 510 L1230 510"/>
<path class="arrow" d="M1340 560 C1150 625 700 615 490 700"/>
<path class="arrow" d="M490 720 L590 720"/>
<path class="arrow" d="M820 720 L910 720"/>
<path class="arrow" d="M1140 720 L1210 720"/>
<path class="arrow" d="M1325 665 C1325 610 1325 260 1290 215"/>
</svg>
"""


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def write_text_files() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "technical_document.md").write_text(TECH_DOC, encoding="utf-8")
    (OUT / "architecture_diagram.mmd").write_text(MERMAID, encoding="utf-8")
    (OUT / "architecture_diagram.svg").write_text(SVG, encoding="utf-8")


def ppt_slide_xml(title: str, bullets: list[str]) -> str:
    bullet_xml = ""
    y = 170
    for bullet in bullets:
        bullet_xml += f"""
        <p:sp>
          <p:nvSpPr><p:cNvPr id="{y}" name="Bullet"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
          <p:spPr><a:xfrm><a:off x="900000" y="{y * 5000}"/><a:ext cx="10500000" cy="420000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
          <p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:pPr marL="285750" indent="-285750"><a:buChar char="•"/></a:pPr><a:r><a:rPr lang="en-US" sz="2200"/><a:t>{esc(bullet)}</a:t></a:r></a:p></p:txBody>
        </p:sp>"""
        y += 75
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="650000" y="450000"/><a:ext cx="11200000" cy="800000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="3600" b="1"><a:solidFill><a:srgbClr val="0F172A"/></a:solidFill></a:rPr><a:t>{esc(title)}</a:t></a:r></a:p></p:txBody>
      </p:sp>
      {bullet_xml}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def write_pptx() -> None:
    path = OUT / "Database_Support_AI_Architecture.pptx"
    slide_count = len(SLIDES)
    slide_overrides = "\n".join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, slide_count + 1))
    slide_ids = "\n".join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1))
    slide_rels = "\n".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1, slide_count + 1))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
{slide_overrides}
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""")
        z.writestr("ppt/presentation.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldIdLst>{slide_ids}</p:sldIdLst>
<p:sldSz cx="12192000" cy="6858000" type="wide"/>
<p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>""")
        z.writestr("ppt/_rels/presentation.xml.rels", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{slide_rels}</Relationships>""")
        for idx, (title, bullets) in enumerate(SLIDES, start=1):
            z.writestr(f"ppt/slides/slide{idx}.xml", ppt_slide_xml(title, bullets))


def docx_document_xml(markdown_text: str) -> str:
    body = []
    for line in markdown_text.splitlines():
        if not line.strip():
            body.append("<w:p/>")
            continue
        style = "Normal"
        text = line
        if line.startswith("# "):
            style = "Title"
            text = line[2:]
        elif line.startswith("## "):
            style = "Heading1"
            text = line[3:]
        elif line.startswith("### "):
            style = "Heading2"
            text = line[4:]
        elif line.startswith("- "):
            text = "• " + line[2:]
        body.append(f"""<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>""")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{''.join(body)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body>
</w:document>"""


def write_docx() -> None:
    path = OUT / "Database_Support_AI_Technical_Document.docx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        z.writestr("word/document.xml", docx_document_xml(TECH_DOC))
        z.writestr("word/styles.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz w:val="22"/><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
</w:styles>""")


def main() -> None:
    write_text_files()
    write_pptx()
    write_docx()
    print(f"Generated study materials in {OUT}")


if __name__ == "__main__":
    main()
