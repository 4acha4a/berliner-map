import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
const paths = new Set(["health", "sectors", "sectors/identify"]);

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const path = (await context.params).path.join("/");
  if (!paths.has(path)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const origin = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  try {
    const url = new URL(`/api/v1/${path}`, origin);
    url.search = request.nextUrl.search;
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    return NextResponse.json(await response.json(), {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Historical API unavailable. Please try again later." },
      { status: 502 },
    );
  }
}
