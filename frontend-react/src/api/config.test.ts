import { describe, expect, it } from "vitest";
import { resolveApiBaseUrl } from "./config";

describe("resolveApiBaseUrl", () => {
  it("uses and normalizes the configured URL", () => {
    expect(
      resolveApiBaseUrl("  https://api.example.com/v1///  ", { hostname: "app.example.com" }),
    ).toBe("https://api.example.com/v1");
  });

  it.each(["localhost", "127.0.0.1"])(
    "uses the existing local FastAPI URL for %s",
    (hostname) => {
      expect(resolveApiBaseUrl(undefined, { hostname })).toBe("http://127.0.0.1:8001");
    },
  );

  it("uses same-origin requests for deployed hosts by default", () => {
    expect(resolveApiBaseUrl(undefined, { hostname: "copilot.example.com" })).toBe("");
  });

  it.each([
    "api.example.com",
    "ftp://api.example.com",
    "https://api.example.com?tenant=one",
    "https://api.example.com#token",
  ])("rejects unsafe or invalid configuration: %s", (value) => {
    expect(() => resolveApiBaseUrl(value, { hostname: "localhost" })).toThrow(
      /VITE_API_BASE_URL/,
    );
  });
});
