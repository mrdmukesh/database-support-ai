import { afterEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../models/auth";
import { DOCUMENT_MAX_SIZE_BYTES, listDocuments, uploadDocument, validateDocumentFile } from "./document-api";
import { SESSION_STORAGE_KEY } from "./client";

const session: Session = { access_token: "token", token_type: "bearer", user: { id: "U1", organization_id: "O1", email: "a@b.com", full_name: "A", role: "dba", is_active: true } };
const document = { id: "DOC-1", organization_id: "O1", workspace_id: "W1", title: "Runbook", current_version: 1 };

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals(); });

describe("document API", () => {
  it("lists documents with optional workspace association", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify([document])));
    vi.stubGlobal("fetch", fetchMock);
    await expect(listDocuments("O1", "W1")).resolves.toEqual([document]);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/documents?organization_id=O1&workspace_id=W1");
  });

  it("uploads multipart fields to the current endpoint", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(document), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["content"], "runbook.pdf", { type: "application/pdf" });
    await expect(uploadDocument({ organization_id: "O1", workspace_id: "W1", title: "Runbook", file })).resolves.toEqual(document);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/documents/upload");
    const request = fetchMock.mock.calls[0][1];
    expect(new Headers(request?.headers).get("Authorization")).toBe("bearer token");
    expect(request?.body).toBeInstanceOf(FormData);
    expect((request?.body as FormData).get("workspace_id")).toBe("W1");
    expect(new Headers(request?.headers).has("Content-Type")).toBe(false);
  });

  it("rejects invalid extension, empty file, and oversized file", () => {
    expect(() => validateDocumentFile(new File(["x"], "runbook.exe"))).toThrow("Unsupported file extension: .exe");
    expect(() => validateDocumentFile(new File([], "empty.pdf"))).toThrow("Uploaded file must not be empty");
    const oversized = new File([new Uint8Array(DOCUMENT_MAX_SIZE_BYTES + 1)], "large.pdf");
    expect(() => validateDocumentFile(oversized)).toThrow("Uploaded file exceeds maximum size");
  });

  it("preserves upload failure detail", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ detail: "Unsupported upload" }), { status: 422, statusText: "Unprocessable Entity" })));
    const file = new File(["content"], "runbook.pdf");
    await expect(uploadDocument({ organization_id: "O1", workspace_id: "W1", title: "Runbook", file })).rejects.toMatchObject({ status: 422, message: "Unsupported upload" });
  });
});
