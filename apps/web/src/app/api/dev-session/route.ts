import { NextRequest, NextResponse } from "next/server";
import { developmentAuthEnabled } from "@/lib/development-auth";

export async function POST(request: NextRequest) {
  const host = request.nextUrl.hostname;
  const origin = request.headers.get("origin");
  if (
    !developmentAuthEnabled() ||
    !["localhost", "127.0.0.1", "[::1]"].includes(host) ||
    !origin ||
    new URL(origin).host !== request.headers.get("host")
  ) {
    return NextResponse.json(
      { error: { message: "Local development sign-in is unavailable." } },
      { status: 403 },
    );
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set("ce_dev_session", process.env.DEV_AUTH_TOKEN!, {
    httpOnly: true,
    sameSite: "strict",
    secure: request.nextUrl.protocol === "https:",
    path: "/",
    maxAge: 8 * 60 * 60,
  });
  return response;
}
export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("ce_dev_session");
  return response;
}
