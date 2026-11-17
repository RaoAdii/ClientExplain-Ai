import { NextRequest, NextResponse } from "next/server";
export async function GET(request: NextRequest) {
  const local =
    process.env.AUTH_MODE === "development" && !!process.env.DEV_AUTH_TOKEN;
  const authenticated =
    local &&
    request.cookies.get("ce_dev_session")?.value === process.env.DEV_AUTH_TOKEN;
  return NextResponse.json(
    { authenticated, local },
    { headers: { "Cache-Control": "no-store" } },
  );
}
