import { NextRequest, NextResponse } from "next/server";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    path[0] !== "projects" ||
    path.length > 2 ||
    (path[1] && !/^[0-9a-f-]{36}$/i.test(path[1]))
  ) {
    return NextResponse.json(
      { error: { message: "Endpoint not found." } },
      { status: 404 },
    );
  }
  if (request.method !== "GET") {
    const origin = request.headers.get("origin");
    if (!origin || new URL(origin).host !== request.headers.get("host")) {
      return NextResponse.json(
        { error: { message: "Invalid request origin." } },
        { status: 403 },
      );
    }
  }
  let authorization = request.headers.get("authorization");
  if (!authorization && process.env.AUTH_MODE === "development") {
    const cookie = request.cookies.get("ce_dev_session")?.value;
    if (cookie && cookie === process.env.DEV_AUTH_TOKEN)
      authorization = `Bearer ${cookie}`;
  }
  if (!authorization)
    return NextResponse.json(
      { error: { message: "Sign in to access your workspace." } },
      { status: 401 },
    );
  try {
    const body = ["GET", "DELETE"].includes(request.method)
      ? undefined
      : await request.text();
    if (body && body.length > 20000)
      return NextResponse.json(
        { error: { message: "Request is too large." } },
        { status: 413 },
      );
    const response = await fetch(
      `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/api/v1/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          Authorization: authorization,
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
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
    return NextResponse.json(
      {
        error: {
          message:
            "The workspace service is unavailable. Please try again shortly.",
        },
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
