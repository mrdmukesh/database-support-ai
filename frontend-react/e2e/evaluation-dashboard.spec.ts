import { expect, test } from "@playwright/test";

test("evaluation dashboard renders its real-data empty state",async({page})=>{
  await page.addInitScript(()=>localStorage.setItem("legacydb-session",JSON.stringify({access_token:"test",token_type:"bearer",user:{id:"U1",organization_id:"O1",email:"admin@example.com",full_name:"Admin",role:"organization_admin",is_active:true}})));
  await page.route("**/evaluation-dashboard/runs",route=>route.fulfill({status:200,contentType:"application/json",body:"[]"}));
  await page.goto("/app/evaluation");
  await expect(page.getByRole("heading",{name:"Evaluation Dashboard"})).toBeVisible();
  await expect(page.getByText("No completed evaluation runs yet")).toBeVisible();
  await expect(page.getByText("Deterministic score")).toHaveCount(0);
});
