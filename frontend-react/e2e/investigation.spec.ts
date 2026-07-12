import { expect, test, type Page, type Route } from "@playwright/test";

const user={id:"USER-1",organization_id:"ORG-1",email:"admin@example.com",full_name:"Admin",role:"organization_admin",is_active:true};
const workspace={id:"WS-1",organization_id:"ORG-1",name:"Finance",slug:"finance",is_active:true};
const connection={id:"CONN-1",organization_id:"ORG-1",workspace_id:"WS-1",engine:"postgresql",name:"Finance DB",is_active:true};
const answer=`Investigation ID: INV-1\nDetected Intent: duplicate_data\n## Root Cause Analysis\n- Retry execution\n## Confirmed Facts\n- SQL-1 returned two rows\n## Recommendation\n- Verify idempotency`;
const saved={id:"INV-1",organization_id:"ORG-1",workspace_id:"WS-1",user_question:"Why duplicate?",detected_intent:"duplicate_data",ai_answer:answer,confidence_score:0.8,report_path:"reports/INV-1",status:"AI_ANSWERED",created_at:"2026-07-12",report:{investigation_id:"INV-1",html:"/reports/INV-1/report.html",pdf:"/reports/INV-1/report.pdf"}};
const check={id:"CHECK-1",investigation_id:"INV-1",claim:"Duplicates still exist",purpose:"Confirm live condition",claim_being_verified:"Duplicate rows exist",evidence_logic:"",expected_result_explanation:"",interpretation:"",conclusion_template:"",verification_sql:"SELECT id FROM payments",expected_result:"Rows returned",risk_level:"Read only",source:"SQL-1",status:"Pending",actual_result_summary:"",confidence_impact:"Not recorded",notes:"",verified_by:"",verified_at:null};

async function json(route:Route,value:unknown,status=200){await route.fulfill({status,contentType:"application/json",body:JSON.stringify(value)});}
async function mockApi(page:Page, submit:unknown={investigation_id:"INV-1"}) {
  await page.route("http://127.0.0.1:8001/**",async(route)=>{const url=new URL(route.request().url()), path=url.pathname;
    if(path==="/auth/login")return json(route,{access_token:"token",token_type:"bearer",user});
    if(path==="/workspaces")return json(route,[workspace]);
    if(path==="/databases/connections")return json(route,[connection]);
    if(path==="/chat/ask"){if(submit instanceof Error)return json(route,{detail:submit.message},500);if(typeof submit==="function")return (submit as (r:Route)=>Promise<void>)(route);const id=(submit as {investigation_id:string|null}).investigation_id;return json(route,{conversation:{id:"C",organization_id:"ORG-1",workspace_id:"WS-1",user_id:"USER-1",title:"Q"},user_message:{id:"U",conversation_id:"C",role:"user",content:"Why duplicate?",confidence:null,source_count:0,requires_human_review:false},assistant_message:{id:"A",conversation_id:"C",role:"assistant",content:answer,confidence:0.8,source_count:1,requires_human_review:false},findings:[],confidence:0.8,requires_human_review:false,sources:["SQL-1"],report:id?saved.report:null,investigation_id:id});}
    if(path==="/learning/investigations/INV-1")return json(route,saved);
    if(path==="/learning/investigations")return json(route,[saved]);
    if(path==="/chat/investigations/INV-1/verification-checks")return json(route,[check]);
    if(path==="/chat/verification-checks/CHECK-1/run")return json(route,{...check,status:"Passed",actual_result_summary:"2 rows returned"});
    if(path==="/reports/INV-1/report.pdf")return route.fulfill({body:"PDF",headers:{"Content-Type":"application/pdf","Content-Disposition":'attachment; filename="investigation.pdf"',"Access-Control-Expose-Headers":"Content-Disposition"}});
    if(path==="/reports/INV-1/report.html")return route.fulfill({body:"<h1>Safe report</h1>",headers:{"Content-Type":"text/html"}});
    if(path==="/admin/summary")return json(route,{organizations:1,workspaces:1,connections:1,documents:0});
    if(path==="/ai/disclaimer")return json(route,{disclaimer:"AI output requires verification."});
    if(path==="/health")return json(route,{status:"ok"});
    return json(route,[]);
  });
}
async function login(page:Page){await page.goto("/login");await page.getByLabel("Email").fill("admin@example.com");await page.getByLabel("Password").fill("StrongPass123!");await page.getByRole("button",{name:"Login"}).click();await expect(page).toHaveURL(/\/app\/dashboard/);}
async function openForm(page:Page){await page.goto("/app/investigations");await expect(page.getByRole("button",{name:"Ask AI"})).toBeVisible();}
async function submitQuestion(page:Page){await page.getByLabel("Workspace").selectOption("WS-1");await expect(page.getByLabel("Database connection")).toContainText("Finance DB");await page.getByLabel("Database connection").selectOption("CONN-1");await page.getByLabel("Question").fill("Why duplicate?");await page.getByRole("button",{name:"Ask AI"}).click();}

test("login, selections, question loading, successful result and verification",async({page})=>{await mockApi(page,async(route)=>{await new Promise(r=>setTimeout(r,250));await json(route,{conversation:{id:"C",organization_id:"ORG-1",workspace_id:"WS-1",user_id:"USER-1",title:"Q"},user_message:{id:"U",conversation_id:"C",role:"user",content:"Q",confidence:null,source_count:0,requires_human_review:false},assistant_message:{id:"A",conversation_id:"C",role:"assistant",content:answer,confidence:.8,source_count:1,requires_human_review:false},findings:[],confidence:.8,requires_human_review:false,sources:["SQL-1"],report:saved.report,investigation_id:"INV-1"});});await login(page);await openForm(page);await submitQuestion(page);await expect(page.getByRole("button",{name:"Analyzing..."})).toBeDisabled();await expect(page).toHaveURL(/INV-1/);await expect(page.getByRole("heading",{name:"Investigation INV-1"})).toBeVisible();await expect(page.getByText("Retry execution",{exact:true})).toBeVisible();await expect(page.getByText("Duplicates still exist",{exact:true})).toBeVisible();await page.getByRole("button",{name:"Run this check"}).click();});
test("partial and insufficient-evidence results stay inline",async({page})=>{await mockApi(page,{investigation_id:null});await login(page);await openForm(page);await submitQuestion(page);await expect(page.getByRole("heading",{name:"Investigation result"})).toBeVisible();await expect(page.getByText(/Confirmed Facts/)).toBeVisible();});
test("API failures restore the form",async({page})=>{await mockApi(page,new Error("Evidence collection failed."));await login(page);await openForm(page);await submitQuestion(page);await expect(page.getByRole("alert")).toContainText("Evidence collection failed.");await expect(page.getByRole("button",{name:"Ask AI"})).toBeEnabled();});
test("report download uses backend filename",async({page})=>{await mockApi(page);await login(page);await page.goto("/app/investigations/INV-1");const download=page.waitForEvent("download");await page.getByRole("button",{name:"Download PDF"}).click();expect((await download).suggestedFilename()).toBe("investigation.pdf");});
test("saved investigation reopens from history",async({page})=>{await mockApi(page);await login(page);await page.goto("/app/investigations/history");await page.getByRole("link",{name:"Open"}).click();await expect(page).toHaveURL(/INV-1/);await expect(page.getByText("SQL-1 returned two rows",{exact:true})).toBeVisible();});
test("logout clears the session and returns to login",async({page})=>{await mockApi(page);await login(page);await openForm(page);await page.getByRole("button",{name:"Logout"}).click();await expect(page).toHaveURL(/\/login/);await page.goto("/app/investigations");await expect(page).toHaveURL(/\/login/);});
