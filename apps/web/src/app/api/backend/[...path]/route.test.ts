// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";
import { DELETE, GET, PATCH, POST } from "./route";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const path = ["projects", "11111111-1111-4111-8111-111111111111", "documents"];
const context = { params: Promise.resolve({ path }) };
const projectId = "11111111-1111-4111-8111-111111111111";
const resourceId = "22222222-2222-4222-8222-222222222222";
const handlers = { DELETE, GET, PATCH, POST };

function request(body: BodyInit, headers: Record<string, string> = {}) {
  return new NextRequest("http://localhost:3000/api/backend/" + path.join("/"), {
    method: "POST", body, duplex: "half",
    headers: { host: "localhost:3000", origin: "http://localhost:3000", authorization: "Bearer session",
      "content-type": "multipart/form-data; boundary=exact-boundary", ...headers },
  } as ConstructorParameters<typeof NextRequest>[1]);
}

const frontendBackendCalls = [
  { name: "load workspace session", method: "GET", route: "auth/me", status: 200 },
  { name: "list projects with filters", method: "GET", route: "projects?limit=12&offset=12&search=Civil", status: 200 },
  { name: "create project", method: "POST", route: "projects", status: 201, body: '{"name":"Civil claim"}' },
  { name: "load project", method: "GET", route: `projects/${projectId}`, status: 200 },
  { name: "update project", method: "PATCH", route: `projects/${projectId}`, status: 200, body: '{"name":"Updated"}' },
  { name: "delete project", method: "DELETE", route: `projects/${projectId}`, status: 204 },
  { name: "load project activity", method: "GET", route: `projects/${projectId}/activity`, status: 200 },
  { name: "list project documents", method: "GET", route: `projects/${projectId}/documents`, status: 200 },
  { name: "submit analysis", method: "POST", route: `projects/${projectId}/analyze`, status: 202, body: `{"selected_document_ids":["${resourceId}"]}`, idempotencyKey: "analysis-request-1" },
  { name: "poll analysis job", method: "GET", route: `jobs/${resourceId}`, status: 200 },
  { name: "load stored stages", method: "GET", route: `projects/${projectId}/stages`, status: 200 },
  { name: "load citations", method: "GET", route: `projects/${projectId}/citations`, status: 200 },
  { name: "load document details", method: "GET", route: `documents/${resourceId}`, status: 200 },
  { name: "delete document", method: "DELETE", route: `documents/${resourceId}`, status: 204 },
] as const;

test.each(frontendBackendCalls)("forwards frontend call: $name", async ({ method, route, status, ...call }) => {
  const [pathname, query] = route.split("?");
  const requestHeaders: Record<string, string> = {
    authorization: "Bearer session",
    host: "localhost:3000",
  };
  if (method !== "GET") requestHeaders.origin = "http://localhost:3000";
  if ("idempotencyKey" in call)
    requestHeaders["idempotency-key"] = call.idempotencyKey;
  const upstreamBody = status === 204 ? null : JSON.stringify({ route: pathname, status });
  let forwardedBody: string | undefined;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    expect(url).toBe(`http://127.0.0.1:8000/api/v1/${pathname}${query ? `?${query}` : ""}`);
    expect(init.method).toBe(method);
    expect(init.headers).toMatchObject({ Authorization: "Bearer session" });
    if ("idempotencyKey" in call)
      expect(init.headers).toMatchObject({ "Idempotency-Key": call.idempotencyKey });
    if (init.body) forwardedBody = await new Response(init.body).text();
    return new Response(upstreamBody, { status });
  });
  vi.stubGlobal("fetch", fetch);
  const response = await handlers[method](
    new NextRequest(`http://localhost:3000/api/backend/${route}`, {
      method,
      headers: requestHeaders,
      ...("body" in call ? { body: call.body, duplex: "half" } : {}),
    } as ConstructorParameters<typeof NextRequest>[1]),
    { params: Promise.resolve({ path: pathname.split("/") }) },
  );
  expect(response.status).toBe(status);
  expect(status === 204 ? await response.text() : await response.json()).toEqual(
    status === 204 ? "" : { route: pathname, status },
  );
  if ("body" in call) expect(forwardedBody).toBe(call.body);
});

test("forwards multipart binary bytes and boundary without text decoding", async () => {
  const bytes = new Uint8Array([45, 45, 0, 255, 128, 13, 10]);
  let forwarded: Uint8Array | undefined;
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    expect(url).toContain("/api/v1/projects/" + path[1] + "/documents");
    expect(init.headers).toMatchObject({ "Content-Type": "multipart/form-data; boundary=exact-boundary", Authorization: "Bearer session" });
    expect(init.body).toBeInstanceOf(ReadableStream);
    forwarded = new Uint8Array(await new Response(init.body).arrayBuffer());
    return new Response('{"document":{},"job":{}}', { status: 202 });
  });
  const response = await POST(request(bytes), context);
  expect(response.status).toBe(202);
  expect(forwarded).toEqual(bytes);
});

test("rejects an oversized Content-Length before contacting the API", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const response = await POST(request("body", { "content-length": String(26 * 1024 * 1024) }), context);
  expect(response.status).toBe(413);
  expect(fetch).not.toHaveBeenCalled();
});

test("cancels oversized streams even without Content-Length", async () => {
  vi.stubEnv("MAX_UPLOAD_BYTES", "1024");
  let cancelled = false;
  const stream = new ReadableStream({
    pull(controller) { controller.enqueue(new Uint8Array(8192)); },
    cancel() { cancelled = true; },
  });
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    await new Response(init.body).arrayBuffer();
    return new Response("{}", { status: 202 });
  });
  const response = await POST(request(stream), context);
  expect(response.status).toBe(413);
  expect(cancelled).toBe(true);
});

test.each(["https://other.test", "invalid-origin"])("rejects mutation origin %s", async (origin) => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const response = await POST(request("body", { origin }), context);
  expect(response.status).toBe(403);
  expect(fetch).not.toHaveBeenCalled();
});
