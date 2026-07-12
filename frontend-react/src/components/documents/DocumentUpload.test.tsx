import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DOCUMENT_ACCEPT } from "../../api/document-api";
import { DocumentUpload } from "./DocumentUpload";

const workspace = { id: "W1", organization_id: "O1", name: "Finance", slug: "finance", is_active: true };

describe("DocumentUpload", () => {
  it("submits the selected workspace, title, and file", async () => {
    const onUpload = vi.fn();
    render(<DocumentUpload organizationId="O1" workspaces={[workspace]} isUploading={false} onUpload={onUpload} />);
    const file = new File(["content"], "runbook.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Runbook" } });
    const fileInput = screen.getByLabelText("File");
    Object.defineProperty(fileInput, "files", { configurable: true, value: [file] });
    fireEvent.change(fileInput);
    fireEvent.submit(screen.getByRole("button", { name: "Upload document" }).closest("form")!);
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith({ organization_id: "O1", workspace_id: "W1", title: "Runbook", file }));
    expect(screen.getByLabelText("File")).toHaveAttribute("accept", DOCUMENT_ACCEPT);
  });
});
