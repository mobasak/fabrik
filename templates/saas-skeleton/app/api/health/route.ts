import { NextResponse } from "next/server";

interface HealthStatus {
  status: "ok" | "degraded" | "error";
  timestamp: string;
  uptime: number;
  environment: string;
  database?: "configured" | "connected" | "error";
}

export async function GET() {
  const health: HealthStatus = {
    status: "ok",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || "development",
  };

  // Add database check if Supabase is configured
  if (process.env.NEXT_PUBLIC_SUPABASE_URL) {
    try {
      // TODO: Add actual Supabase health check
      health.database = "configured";
    } catch {
      health.database = "error";
      health.status = "degraded";
    }
  }

  return NextResponse.json(health);
}
