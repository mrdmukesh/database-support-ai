import { useState, type FormEvent } from "react";
import { DOCUMENT_ACCEPT } from "../../api/document-api";
import type { DocumentUploadFields } from "../../models/document";
import type { Workspace } from "../../models/workspace";

interface DocumentUploadProps {
  organizationId: string;
  workspaces: Workspace[];
  isUploading: boolean;
  onUpload: (fields: DocumentUploadFields) => Promise<void> | void;
}

export function DocumentUpload({ organizationId, workspaces, isUploading, onUpload }: DocumentUploadProps) {
  const [formKey, setFormKey] = useState(0);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const fileInput = formElement.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) return;
    await onUpload({
      organization_id: organizationId,
      workspace_id: String(form.get("workspaceId") ?? ""),
      title: String(form.get("title") ?? "").trim(),
      file,
    });
    setFormKey((value) => value + 1);
  }

  return (
    <form key={formKey} className="document-upload" onSubmit={submit}>
      <h2>Upload document</h2>
      <label htmlFor="document-workspace">Workspace</label>
      <select id="document-workspace" name="workspaceId" required disabled={isUploading || !workspaces.length}>
        {workspaces.length ? workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
        )) : <option value="">Create a workspace first</option>}
      </select>
      <label htmlFor="document-title">Title</label>
      <input id="document-title" name="title" required disabled={isUploading} />
      <label htmlFor="document-file">File</label>
      <input id="document-file" name="file" type="file" accept={DOCUMENT_ACCEPT} required disabled={isUploading} />
      <p className="field-note">Allowed files: PDF, DOCX, TXT, CSV, SQL, Markdown, and ZIP. Maximum size is 25 MB.</p>
      <button type="submit" disabled={isUploading || !workspaces.length}>
        {isUploading ? "Uploading..." : "Upload document"}
      </button>
    </form>
  );
}
