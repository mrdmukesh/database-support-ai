import { afterEach, describe, expect, it, vi } from "vitest";
import { loadVerificationChecks, runAllVerificationChecks, runVerificationCheck, skipVerificationCheck } from "./verification-api";
afterEach(() => vi.unstubAllGlobals());
const check = { id: "C/1", status: "Pending" };
function response(value: unknown) { return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } }); }
describe("verification API", () => {
  it("loads, runs stored SQL, skips, and runs all through current routes", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response([check])).mockResolvedValueOnce(response(check)).mockResolvedValueOnce(response(check)).mockResolvedValueOnce(response({ checks: [check], report: null }));
    vi.stubGlobal("fetch", fetchMock);
    await loadVerificationChecks("INV/1"); await runVerificationCheck("C/1"); await skipVerificationCheck("C/1"); await runAllVerificationChecks("INV/1");
    expect(fetchMock.mock.calls[0][0]).toContain("INV%2F1/verification-checks");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", body: "{}" });
    expect(fetchMock.mock.calls[2][0]).toContain("C%2F1/skip");
    expect(fetchMock.mock.calls[3][0]).toContain("run-all");
  });
});
