export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  is_active: boolean;
}

export interface WorkspaceCreate {
  organization_id: string;
  name: string;
  slug: string;
}

export interface WorkspaceUpdate {
  name?: string | null;
  slug?: string | null;
  is_active?: boolean | null;
}
