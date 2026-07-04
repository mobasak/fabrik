import { NextResponse } from "next/server";

interface HealthStatus {
  status: "ok" | "degraded" | "error";
  timestamp: string;
  uptime: number;
  environment: string;
  backend?: "connected" | "error" | "not_configured";
  error?: string;
}

// Pattern A: the Next.js frontend holds NO database credentials — the FastAPI
// backend owns auth + Postgres and exposes its own /api/health with the real DB
// check. This route reports frontend liveness, and (when NEXT_PUBLIC_API_URL is
// set) reflects the backend's health so a single probe covers the pair.
export async function GET() {
  const health: HealthStatus = {
    status: "ok",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || "development",
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (apiUrl) {
    try {
      const res = await fetch(`${apiUrl.replace(/\/$/, "")}/api/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(3000),
      });
      health.backend = res.ok ? "connected" : "error";
      if (!res.ok) health.status = "degraded";
    } catch (err) {
      health.backend = "error";
      health.status = "degraded";
      health.error = err instanceof Error ? err.message : "Backend unreachable";
    }
  } else {
    health.backend = "not_configured";
  }

  const statusCode = health.status === "ok" ? 200 : 503;
  return NextResponse.json(health, { status: statusCode });
}
