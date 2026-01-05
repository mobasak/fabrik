import { NextRequest } from "next/server";
import { spawn } from "child_process";

export async function POST(request: NextRequest) {
  const { message, systemPrompt } = await request.json();

  if (!message) {
    return new Response(JSON.stringify({ error: "Message required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const model = process.env.DROID_MODEL_ID || "gemini-3-flash-preview";
      const reasoning = process.env.DROID_REASONING;

      const args = ["exec", "--output-format", "debug", "-m", model];
      if (reasoning) args.push("-r", reasoning);

      const fullPrompt = systemPrompt
        ? `${systemPrompt}\n\nUser: ${message}`
        : message;
      args.push(fullPrompt);

      const proc = spawn("droid", args, {
        stdio: ["ignore", "pipe", "pipe"],
      });

      proc.stdout.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.trim()) {
            const event = `data: ${JSON.stringify({ type: "text_delta", text: line + "\n" })}\n\n`;
            controller.enqueue(encoder.encode(event));
          }
        }
      });

      proc.stderr.on("data", (chunk: Buffer) => {
        console.error("droid stderr:", chunk.toString());
      });

      proc.on("close", (code) => {
        const event = `data: ${JSON.stringify({ type: "done", code })}\n\n`;
        controller.enqueue(encoder.encode(event));
        controller.close();
      });

      proc.on("error", (error) => {
        const event = `data: ${JSON.stringify({ type: "error", error: error.message })}\n\n`;
        controller.enqueue(encoder.encode(event));
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
