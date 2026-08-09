export type EnvironmentType = "production" | "uat" | "test" | "evaluation" | "demo";

export interface DatabaseConnection {
  id: string;
  organization_id: string;
  workspace_id: string;
  engine: string;
  name: string;
  environment_type: EnvironmentType;
  max_scan_rows: number;
  is_active: boolean;
}

export interface DatabaseConnectionCreate {
  organization_id: string;
  workspace_id: string;
  engine: string;
  name: string;
  host?: string;
  port?: number | null;
  database_name?: string;
  secret_ref?: string;
  connection_string?: string | null;
  environment_type: EnvironmentType;
  max_scan_rows?: number;
}

export interface DatabaseConnectionUpdate {
  name?: string | null;
  connection_string?: string | null;
  is_active?: boolean | null;
  environment_type?: EnvironmentType;
  max_scan_rows?: number;
}

export interface ConnectionValidationResult {
  connection_id: string;
  is_valid: boolean;
  message: string;
  [key: string]: unknown;
}

export interface MetadataCatalogSummary {
  snapshot_id?: string;
  status: "NOT_DISCOVERED" | "DISCOVERING" | "READY" | "FAILED" | "STALE";
  version: number | null;
  last_refresh: string | null;
  schema_hash?: string;
  counts: Record<string, number>;
  completeness: Record<string, string>;
  changes?: { structural_change?: boolean; added?: number; removed?: number };
  error_summary?: string;
}
