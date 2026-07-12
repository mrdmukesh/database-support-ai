export interface ReportLinks {
  investigation_id?: string;
  mode?: string;
  html?: string;
  pdf?: string;
  docx?: string;
  xlsx?: string;
  audit_html?: string;
  audit_pdf?: string;
  audit_docx?: string;
  audit_xlsx?: string;
  ai_trace?: string;
  [key: string]: string | undefined;
}

export interface AiDebugTraceDownload {
  investigation_id: string;
  trace: unknown;
}
