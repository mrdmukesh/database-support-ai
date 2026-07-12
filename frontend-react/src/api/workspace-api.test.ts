import { afterEach, describe, expect, it, vi } from "vitest";
import { createWorkspace, deleteWorkspace, listWorkspaces, updateWorkspace } from "./workspace-api";

const workspace = { id: "WS-1", organization_id: "ORG-1", name: "Finance", slug: "finance", is_active: true };

afterEach(() => vi.unstubAllGlobals());

describe("workspace API", () => {
  it("uses the tenant-scoped list endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify([workspace])));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listWorkspaces("ORG 1")).resolves.toEqual([workspace]);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/workspaces?organization_id=ORG%201");
  });

  it("preserves create and update payloads", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify(workspace), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...workspace, name: "Finance Ops" })));
    vi.stubGlobal("fetch", fetchMock);

    await createWorkspace({ organization_id: "ORG-1", name: "Finance", slug: "finance" });
    await updateWorkspace("WS-1", { name: "Finance Ops", slug: "finance-ops" });

    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify({ organization_id: "ORG-1", name: "Finance", slug: "finance" }) });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "PATCH", body: JSON.stringify({ name: "Finance Ops", slug: "finance-ops" }) });
  });

  it("uses the existing delete endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteWorkspace("WS-1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/workspaces/WS-1");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "DELETE" });
  });
});
