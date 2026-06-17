import { NextRequest } from "next/server";

// AI chat backed by OpenRouter (https://openrouter.ai/api/v1) — one API key,
// every provider. Per `.windsurf/rules/core/65-rag-search.md` + `cost-budget.md`,
// application LLM calls go through the OpenRouter HTTP API (no vendor SDKs, no
// shelling out to a CLI). Responses are streamed to the client as Server-Sent
// Events; `useSSEStream` consumes `{ type: "text_delta" | "done" | "error" }`.
const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";
// Override per project via OPENROUTER_MODEL — see https://openrouter.ai/models.
const DEFAULT_MODEL = process.env.OPENROUTER_MODEL || "anthropic/claude-sonnet-4.6";

export async function POST(request: NextRequest) {
  const { message, systemPrompt } = await request.json();

  if (!message) {
    return new Response(JSON.stringify({ error: "Message required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    // Fail clearly instead of streaming a broken response when AI isn't configured.
    return new Response(
      JSON.stringify({ error: "OPENROUTER_API_KEY is not configured" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  const messages: Array<{ role: string; content: string }> = [];
  if (systemPrompt) messages.push({ role: "system", content: systemPrompt });
  messages.push({ role: "user", content: message });

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: Record<string, unknown>) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));

      try {
        const upstream = await fetch(OPENROUTER_URL, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ model: DEFAULT_MODEL, messages, stream: true }),
        });

        if (!upstream.ok || !upstream.body) {
          const detail = await upstream.text().catch(() => "");
          send({
            type: "error",
            error: `OpenRouter HTTP ${upstream.status}${detail ? `: ${detail.slice(0, 200)}` : ""}`,
          });
          controller.close();
          return;
        }

        const reader = upstream.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          // Keep the last (possibly incomplete) line for the next chunk.
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const data = trimmed.slice(5).trim();
            if (data === "" || data === "[DONE]") continue;
            try {
              const json = JSON.parse(data);
              const delta: string | undefined = json?.choices?.[0]?.delta?.content;
              if (delta) send({ type: "text_delta", text: delta });
            } catch {
              // Skip keep-alive comments / partial frames.
            }
          }
        }

        send({ type: "done" });
        controller.close();
      } catch (error) {
        send({
          type: "error",
          error: error instanceof Error ? error.message : "Stream failed",
        });
        controller.close();
      }
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
