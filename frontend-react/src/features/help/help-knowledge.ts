import type { HelpArticle } from "../../models/help";

export const HELP_KNOWLEDGE_VERSION = "2026.07.1";
export const helpArticles: HelpArticle[] = [
  ["sign-in","Getting Started","How do sign-in and session expiry work?",["sign in","login","session"]],
  ["dashboard","Dashboard","What information is on the dashboard?",["dashboard","overview"],"/app/dashboard"],
  ["create-workspace","Workspaces","How do I create a workspace?",["workspace","create workspace"],"/app/workspaces",["super_admin","organization_admin"]],
  ["edit-workspace","Workspaces","How do I edit or deactivate a workspace?",["edit workspace","deactivate workspace"],"/app/workspaces",["super_admin","organization_admin"]],
  ["workspace-members","Workspaces","How do I add workspace members?",["member","workspace member"],"/app/admin/users",["super_admin","organization_admin"]],
  ["roles","Roles and Permissions","What is the difference between organization and workspace roles?",["role","permission","organization role","workspace role"],"/app/admin/users"],
  ["create-connection","Database Connections","How do I connect a database?",["connect","database connection"],"/app/connections"],
  ["test-connection","Database Connections","How do I test a database connection?",["test connection"],"/app/connections"],
  ["database-types","Database Connections","Which database types are supported?",["database type","mysql","postgresql","oracle","sql server","sqlite"],"/app/connections"],
  ["credentials","Security and Privacy","How are database credentials protected?",["credential","password","secret","security"],"/app/connections"],
  ["connection-failure","Troubleshooting","Why did database connection testing fail?",["connection failed","timeout","ssl"],"/app/connections"],
  ["documents","Documents","How do I upload or manage documents?",["document","upload"],"/app/documents"],
  ["start-investigation","Investigations","How do I start an investigation?",["start investigation","ask ai"],"/app/investigations"],
  ["choose-connection","Investigations","How do I choose the correct database connection?",["choose connection","selected database"],"/app/investigations"],
  ["useful-question","Investigations","How do I write a useful investigation question?",["question","business key","issue"],"/app/investigations"],
  ["investigation-status","Investigation Results","What does the investigation status mean?",["status","open","answered","review"],"/app/investigations/history"],
  ["confidence","Investigation Results","What does confidence mean?",["confidence","score"],"/app/investigations"],
  ["evidence","Investigation Results","How do I review evidence and citations?",["evidence","citation","sql"],"/app/investigations"],
  ["insufficient-evidence","Investigation Results","Why is the result marked insufficient evidence?",["insufficient evidence","missing evidence"],"/app/investigations"],
  ["reports","Reports","How do I download an investigation report?",["report","download","pdf","docx","xlsx"],"/app/investigations/history"],
  ["feedback","Feedback","How do I submit investigation feedback?",["feedback","submit feedback"],"/app/learning"],
  ["after-feedback","Feedback","What happens after feedback is submitted?",["after feedback","pending approval"],"/app/learning"],
  ["developer-review","Feedback","What is developer review?",["developer review"],"/app/learning"],
  ["approval","Learning Loop","How does feedback approval work?",["approval","approve feedback"],"/app/learning"],
  ["no-training","Learning Loop","Does feedback automatically train the model?",["train","training","fine tune"],"/app/learning"],
  ["learning-loop","Learning Loop","How does the Learning Loop work?",["learning loop","knowledge"],"/app/learning"],
  ["add-user","Users & Access","How do I add a user?",["add user","invite user"],"/app/admin/users",["super_admin","organization_admin"]],
  ["change-role","Users & Access","How do I change an organization role?",["change role","organization role"],"/app/admin/users",["super_admin","organization_admin"]],
  ["workspace-access","Users & Access","How do I manage workspace access?",["workspace access","membership"],"/app/admin/users",["super_admin","organization_admin"]],
  ["deactivate-user","Users & Access","How do I deactivate a user or membership?",["deactivate user","remove access"],"/app/admin/users",["super_admin","organization_admin"]],
  ["permission-denied","Troubleshooting","Why am I seeing permission denied?",["permission denied","forbidden","unauthorized"]],
  ["page-error","Troubleshooting","What should I do when a page or API fails to load?",["page loading","api error","retry"]],
  ["privacy","Security and Privacy","What security and privacy guidance should I follow?",["privacy","security","secret"]],
  ["support","Troubleshooting","How do I report an application defect?",["support","defect","bug","documentation gap"]],
].map(([id, category, question, keywords, route, requiredRoles]) => ({ id, category, question, keywords, route, requiredRoles })) as HelpArticle[];

const routeCategory: [RegExp, string][] = [[/workspaces/,"Workspaces"],[/connections/,"Database Connections"],[/documents/,"Documents"],[/investigations\//,"Investigation Results"],[/investigations/,"Investigations"],[/learning/,"Learning Loop"],[/admin\/users/,"Users & Access"],[/dashboard/,"Dashboard"]];
export function suggestionsForRoute(pathname: string, role?: string, limit = 4): HelpArticle[] {
  const category = routeCategory.find(([pattern]) => pattern.test(pathname))?.[1] || "Getting Started";
  const visible = helpArticles.filter(article => !article.requiredRoles || article.requiredRoles.includes(role || ""));
  return [...visible.filter(article => article.category === category), ...visible.filter(article => article.category !== category)].slice(0, limit);
}
export function articleForQuestion(question: string): HelpArticle | undefined {
  const value = question.toLowerCase(); return helpArticles.find(article => article.question.toLowerCase() === value || article.keywords.some(keyword => value.includes(keyword)));
}
