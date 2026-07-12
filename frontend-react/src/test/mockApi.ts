import { afterEach, vi } from "vitest";

export function mockJsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

export function mockApiOnce(body: unknown, init?: ResponseInit) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(mockJsonResponse(body, init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});
