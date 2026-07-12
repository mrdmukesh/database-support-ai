import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiHealth, getDashboardSummary, getDisclaimer } from "./dashboard-api";

afterEach(() => vi.unstubAllGlobals());

describe("dashboard API", () => {
  it("uses the current summary, disclaimer, and health endpoints", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ organizations: 1, users: 2, active_subscriptions: 0, documents: 3, incidents: 4 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ disclaimer: ["Verify AI output"] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "healthy", components: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDashboardSummary()).resolves.toMatchObject({ users: 2 });
    await expect(getDisclaimer()).resolves.toEqual(["Verify AI output"]);
    await expect(getApiHealth()).resolves.toMatchObject({ status: "healthy" });
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://127.0.0.1:8001/admin/summary",
      "http://127.0.0.1:8001/ai/disclaimer",
      "http://127.0.0.1:8001/health",
    ]);
  });
});
