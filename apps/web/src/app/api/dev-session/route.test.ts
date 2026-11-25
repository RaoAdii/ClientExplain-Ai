// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";
import { POST } from "./route";
import { GET as session } from "../session/route";

afterEach(() => vi.unstubAllEnvs());
const request = () => new NextRequest("http://127.0.0.1:3000/api/dev-session", {
  method: "POST", headers: { origin: "http://127.0.0.1:3000", host: "127.0.0.1:3000" },
});

test.each([
  ["production app", "production", "development", "development", "valid-development-token-1234567890"],
  ["production runtime", "development", "production", "development", "valid-development-token-1234567890"],
  ["public Supabase mode", "development", "development", "supabase", "valid-development-token-1234567890"],
  ["missing token", "development", "development", "development", ""],
  ["short token", "development", "development", "development", "short"],
])("rejects %s", async (_name, appEnv, nodeEnv, publicMode, token) => {
  vi.stubEnv("APP_ENV", appEnv);
  vi.stubEnv("NODE_ENV", nodeEnv);
  vi.stubEnv("AUTH_MODE", "development");
  vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", publicMode);
  vi.stubEnv("DEV_AUTH_TOKEN", token);
  expect((await POST(request())).status).toBe(403);
  await expect((await session(new NextRequest("http://127.0.0.1:3000/api/session"))).json()).resolves.toMatchObject({ authenticated: false, local: false });
});

test("opens a local session without returning the credential in the body", async () => {
  vi.stubEnv("APP_ENV", "development");
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("AUTH_MODE", "development");
  vi.stubEnv("NEXT_PUBLIC_AUTH_MODE", "development");
  vi.stubEnv("DEV_AUTH_TOKEN", "valid-development-token-1234567890");
  const result = await POST(request());
  expect(result.status).toBe(200);
  expect(await result.json()).toEqual({ ok: true });
  expect(result.headers.get("set-cookie")).toContain("HttpOnly");
});
