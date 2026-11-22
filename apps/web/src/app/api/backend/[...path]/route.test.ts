// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";
import { POST } from "./route";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const path = ["projects", "11111111-1111-4111-8111-111111111111", "documents"];
const context = { params: Promise.resolve({ path }) };
function request(body: BodyInit, headers: Record<string, string> = {}) {
  return new NextRequest("http://localhost:3000/api/backend/" + path.join("/"), {
    method: "POST", body, duplex: "half",
    headers: { host: "localhost:3000", origin: "http://localhost:3000", authorization: "Bearer session",
      "content-type": "multipart/form-data; boundary=exact-boundary", ...headers },
  } as ConstructorParameters<typeof NextRequest>[1]);
}

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
