import { NextRequest, NextResponse } from "next/server";
import { developmentAuthEnabled } from "@/lib/development-auth";
export async function GET(request: NextRequest) {
  const local = developmentAuthEnabled();
  const authenticated =
    local &&
    request.cookies.get("ce_dev_session")?.value === process.env.DEV_AUTH_TOKEN;
  return NextResponse.json(
    { authenticated, local },
    { headers: { "Cache-Control": "no-store" } },
  );
}
