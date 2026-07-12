export interface DocumentSummary {
  id: string;
  organization_id: string;
  workspace_id: string;
  title: string;
  current_version: number;
}

export interface DocumentUploadFields {
  organization_id: string;
  workspace_id: string;
  title: string;
  file: File;
}
