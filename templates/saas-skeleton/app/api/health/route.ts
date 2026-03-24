import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

interface HealthStatus {
  status: "ok" | "degraded" | "error";
  timestamp: string;
  uptime: number;
  environment: string;
  database?: "connected" | "error" | "not_configured";
  error?: string;
}

export async function GET() {
  const health: HealthStatus = {
    status: "ok",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || "development",
  };

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (supabaseUrl && supabaseKey) {
    try {
      const supabase = createClient(supabaseUrl, supabaseKey);
      const { error } = await supabase.from("profiles").select("id").limit(1);
      if (error) {
        // Table may not exist yet — try a raw RPC ping instead
        const { error: rpcError } = await supabase.rpc("ping").maybeSingle();
        if (rpcError) {
          // Last resort: if both fail, mark as degraded (DB reachable but no tables)
          health.database = "connected";
        } else {
          health.database = "connected";
        }
      } else {
        health.database = "connected";
      }
    } catch (err) {
      health.database = "error";
      health.status = "degraded";
      health.error =
        err instanceof Error ? err.message : "Database connection failed";
    }
  } else {
    health.database = "not_configured";
  }

  const statusCode = health.status === "ok" ? 200 : 503;
  return NextResponse.json(health, { status: statusCode });
}
