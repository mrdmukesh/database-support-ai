import type { User } from "./auth";

export type OrganizationRole = "organization_admin" | "developer" | "dba" | "support_engineer" | "read_only_user" | "auditor";
export type WorkspaceRole = "OWNER" | "ADMIN" | "DBA" | "DEVELOPER" | "VIEWER" | "AUDITOR";
export interface AdminUserCreate { organization_id: string; email: string; password: string; full_name: string; role: OrganizationRole }
export interface AdminUserUpdate { full_name?: string; role?: OrganizationRole; is_active?: boolean }
export interface WorkspaceMembership { id: string; organization_id: string; workspace_id: string; user_id: string; role: WorkspaceRole; is_active: boolean }
export type ManagedUser = User;
