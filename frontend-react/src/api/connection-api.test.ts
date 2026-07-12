import { afterEach, describe, expect, it, vi } from "vitest";
import { createConnection, deleteConnection, listConnections, testConnection, updateConnection } from "./connection-api";

const connection = { id: "CONN-1", organization_id: "ORG-1", workspace_id: "WS-1", engine: "mysql", name: "ERP", is_active: true };
afterEach(() => vi.unstubAllGlobals());

describe("connection API", () => {
  it("lists all connections or filters by workspace", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify([connection])));
    vi.stubGlobal("fetch", fetchMock);
    await listConnections("ORG-1", "WS-1");
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8001/databases/connections?organization_id=ORG-1&workspace_id=WS-1");
  });

  it("preserves create and safe edit payloads", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify(connection), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...connection, name: "ERP 2" })));
    vi.stubGlobal("fetch", fetchMock);
    await createConnection({ organization_id: "ORG-1", workspace_id: "WS-1", engine: "mysql", name: "ERP", host: "db", port: 3306, database_name: "erp", secret_ref: "env://DB", connection_string: null });
    await updateConnection("CONN-1", { name: "ERP 2" });
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ organization_id: "ORG-1", workspace_id: "WS-1", engine: "mysql", name: "ERP", host: "db", port: 3306, database_name: "erp", secret_ref: "env://DB", connection_string: null }));
    expect(fetchMock.mock.calls[1][1]?.body).toBe(JSON.stringify({ name: "ERP 2" }));
  });

  it("deletes and validates using existing endpoints", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ connection_id: "CONN-1", is_valid: false, message: "Connection error" })));
    vi.stubGlobal("fetch", fetchMock);
    await deleteConnection("CONN-1");
    await expect(testConnection("CONN-1")).resolves.toMatchObject({ is_valid: false });
    expect(fetchMock.mock.calls[1][0]).toBe("http://127.0.0.1:8001/databases/connections/CONN-1/test");
  });
});
