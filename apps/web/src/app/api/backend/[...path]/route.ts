import { NextRequest, NextResponse } from "next/server";
import { developmentAuthEnabled } from "@/lib/development-auth";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const method = request.method;
  const upload =
    path.length === 3 && path[0] === "projects" &&
    path[2] === "documents" && method === "POST";
  const isUuid = (value: string | undefined) =>
    !!value && /^[0-9a-f-]{36}$/i.test(value);
  const projectCollection =
    path.length === 1 && path[0] === "projects" && ["GET", "POST"].includes(method);
  const project =
    path.length === 2 && path[0] === "projects" && isUuid(path[1]) &&
    ["GET", "PATCH", "DELETE"].includes(method);
  const projectResource =
    path.length === 3 && path[0] === "projects" && isUuid(path[1]) &&
    ((path[2] === "documents" && ["GET", "POST"].includes(method)) ||
      (["activity", "stages", "citations"].includes(path[2]) && method === "GET") ||
      (path[2] === "workflow" && ["GET", "PATCH"].includes(method)) ||
      (path[2] === "analyze" && method === "POST"));
  const workspaceSession =
    path.length === 2 && path[0] === "auth" && path[1] === "me" && method === "GET";
  const profileUpdate =
    path.length === 2 && path[0] === "auth" && path[1] === "me" && method === "PATCH";
  const aiStatus =
    path.length === 2 && path[0] === "ai" && path[1] === "status" && method === "GET";
  const document =
    path.length === 2 && path[0] === "documents" && isUuid(path[1]) &&
    ["GET", "DELETE"].includes(method);
  const documentRetry =
    path.length === 3 && path[0] === "documents" && isUuid(path[1]) &&
    path[2] === "retry" && method === "POST";
  const job =
    path.length === 2 && path[0] === "jobs" && isUuid(path[1]) && method === "GET";
  if (![projectCollection, project, projectResource, workspaceSession, profileUpdate, aiStatus, document, documentRetry, job].some(Boolean)) {
    return NextResponse.json(
      { error: { message: "Endpoint not found." } },
      { status: 404 },
    );
  }
  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    let sameOrigin = false;
    try {
      sameOrigin =
        !!origin &&
        new URL(origin).host === request.headers.get("host");
    } catch {}
    if (!sameOrigin) {
      return NextResponse.json(
        { error: { message: "Invalid request origin." } },
        { status: 403 },
      );
    }
  }
  let authorization = request.headers.get("authorization");
  if (!authorization && developmentAuthEnabled()) {
    const cookie = request.cookies.get("ce_dev_session")?.value;
    if (cookie && cookie === process.env.DEV_AUTH_TOKEN)
      authorization = `Bearer ${cookie}`;
  }
  if (!authorization)
    return NextResponse.json(
      { error: { message: "Sign in to access your workspace." } },
      { status: 401 },
    );
  const configuredLimit = Number(process.env.MAX_UPLOAD_BYTES || 25 * 1024 * 1024);
  const fileLimit = Number.isSafeInteger(configuredLimit) && configuredLimit > 0
    ? Math.min(configuredLimit, 25 * 1024 * 1024)
    : 25 * 1024 * 1024;
  // Reserve bounded space for multipart framing; the API checks the file limit itself.
  const requestLimit = upload ? fileLimit + 64 * 1024 : 80000;
  const contentLength = request.headers.get("content-length");
  if (contentLength && (!/^\d+$/.test(contentLength) || Number(contentLength) > requestLimit)) {
    return NextResponse.json(
      { error: { message: "Request is too large." } },
      { status: 413 },
    );
  }
  let tooLarge = false;
  const reader = !["GET", "DELETE"].includes(request.method) ? request.body?.getReader() : undefined;
  let bytes = 0;
  const body = reader ? new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const chunk = await reader.read();
        if (chunk.done) {
          controller.close();
          return;
        }
        bytes += chunk.value.byteLength;
        if (bytes > requestLimit) {
          tooLarge = true;
          await reader.cancel();
          controller.error(new Error("Request is too large."));
          return;
        }
        controller.enqueue(chunk.value);
      } catch (error) {
        controller.error(error);
      }
    },
    cancel(reason) { return reader.cancel(reason); },
  }) : undefined;
  try {
    const init: RequestInit & { duplex?: "half" } = {
      method: request.method,
      headers: {
        "Content-Type": request.headers.get("content-type") || "application/json",
        Authorization: authorization,
        ...(request.headers.get("idempotency-key")
          ? { "Idempotency-Key": request.headers.get("idempotency-key")! }
          : {}),
      },
      body,
      ...(body ? { duplex: "half" as const } : {}),
      cache: "no-store",
      signal: AbortSignal.timeout(upload ? 120000 : 10000),
    };
    const response = await fetch(
      `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/api/v1/${path.join("/")}${request.nextUrl.search}`,
      init,
    );
    if (tooLarge)
      return NextResponse.json(
        { error: { message: "Request is too large." } },
        { status: 413 },
      );
    return new NextResponse(
      response.status === 204 ? null : await response.text(),
      {
        status: response.status,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      },
    );
  } catch {
    if (tooLarge)
      return NextResponse.json(
        { error: { message: "Request is too large." } },
        { status: 413 },
      );
    return NextResponse.json(
      {
        error: {
          message:
            "The workspace service is unavailable. Please try again shortly.",
        },
      },
      { status: 503 },
    );
  } finally {
    await reader?.cancel().catch(() => {});
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
