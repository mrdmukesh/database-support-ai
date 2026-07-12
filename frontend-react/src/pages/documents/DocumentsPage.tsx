import { useCallback, useEffect, useState } from "react";
import { listDocuments, uploadDocument } from "../../api/document-api";
import { listWorkspaces } from "../../api/workspace-api";
import { DocumentList } from "../../components/documents/DocumentList";
import { DocumentUpload } from "../../components/documents/DocumentUpload";
import { useAuth } from "../../hooks/use-auth";
import type { DocumentSummary, DocumentUploadFields } from "../../models/document";
import type { Workspace } from "../../models/workspace";

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Document request failed.";
}

export function DocumentsPage() {
  const { organizationId } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!organizationId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [workspaceRows, documentRows] = await Promise.all([
        listWorkspaces(organizationId, signal),
        listDocuments(organizationId, undefined, signal),
      ]);
      setWorkspaces(workspaceRows);
      setDocuments(documentRows);
      setMessage("Documents loaded.");
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(messageOf(cause));
    } finally {
      setIsLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function upload(fields: DocumentUploadFields) {
    setIsUploading(true);
    setError(null);
    try {
      await uploadDocument(fields);
      setMessage("Document uploaded.");
      await load();
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="management-page" aria-labelledby="documents-page-title">
      <div className="management-page-heading"><p className="eyebrow">Knowledge</p><h2 id="documents-page-title">Documents</h2></div>
      {error ? <div className="form-message error" role="alert">{error}</div> : null}
      {!error && message ? <div className="form-message" role="status">{message}</div> : null}
      <div className="management-grid">
        <DocumentUpload organizationId={organizationId ?? ""} workspaces={workspaces} isUploading={isUploading} onUpload={upload} />
        {isLoading ? <p>Loading documents...</p> : <DocumentList documents={documents} workspaces={workspaces} />}
      </div>
    </section>
  );
}
