import { apiRequest } from "./client";
import type { AdminUserCreate, AdminUserUpdate, ManagedUser, WorkspaceMembership, WorkspaceRole } from "../models/access";

export const listManagedUsers = async (organizationId: string, signal?: AbortSignal) => (await apiRequest<ManagedUser[]>(`/admin/users?organization_id=${encodeURIComponent(organizationId)}`, { signal })) ?? [];
export const createManagedUser = async (payload: AdminUserCreate) => (await apiRequest<ManagedUser>("/admin/users", { method: "POST", body: payload }))!;
export const updateManagedUser = async (userId: string, payload: AdminUserUpdate) => (await apiRequest<ManagedUser>(`/admin/users/${encodeURIComponent(userId)}`, { method: "PATCH", body: payload }))!;
export const listWorkspaceMembers = async (workspaceId: string, signal?: AbortSignal) => (await apiRequest<WorkspaceMembership[]>(`/workspaces/${encodeURIComponent(workspaceId)}/members`, { signal })) ?? [];
export const assignWorkspaceMember = async (workspaceId: string, userId: string, role: WorkspaceRole) => (await apiRequest<WorkspaceMembership>(`/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`, { method: "PUT", body: { user_id: userId, role } }))!;
export const deactivateWorkspaceMember = async (workspaceId: string, userId: string) => { await apiRequest(`/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`, { method: "DELETE" }); };
