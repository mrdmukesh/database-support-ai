import type {
  LoginRequest,
  Organization,
  OrganizationCreate,
  Session,
  SignupRequest,
  User,
} from "../models/auth";
import type { Workspace, WorkspaceCreate } from "../models/workspace";
import { ApiClientError, apiRequest } from "./client";

export async function login(
  credentials: LoginRequest,
  signal?: AbortSignal,
): Promise<Session> {
  const session = await apiRequest<Session>("/auth/login", {
    method: "POST",
    body: credentials,
    signal,
  });
  if (!session) {
    throw new ApiClientError("Login returned an empty response.", 200);
  }
  return session;
}

export async function createOrganization(payload: OrganizationCreate): Promise<Organization> {
  const organization = await apiRequest<Organization>("/organizations", {
    method: "POST",
    body: payload,
  });
  if (!organization) throw new ApiClientError("Organization creation returned an empty response.", 201);
  return organization;
}

export async function listOrganizations(): Promise<Organization[]> {
  return (await apiRequest<Organization[]>("/organizations")) ?? [];
}

export async function signup(payload: SignupRequest): Promise<User> {
  const user = await apiRequest<User>("/auth/signup", {
    method: "POST",
    body: payload,
  });
  if (!user) throw new ApiClientError("Signup returned an empty response.", 201);
  return user;
}

export async function createDefaultWorkspace(organizationId: string): Promise<Workspace> {
  const payload: WorkspaceCreate = {
    organization_id: organizationId,
    name: "Default Workspace",
    slug: "default-workspace",
  };
  const workspace = await apiRequest<Workspace>("/workspaces", {
    method: "POST",
    body: payload,
  });
  if (!workspace) throw new ApiClientError("Workspace creation returned an empty response.", 201);
  return workspace;
}
