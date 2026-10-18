"use client";

import { useState, useCallback } from "react";
import { Loader2, Search, FileText, Brain, CheckCircle } from "lucide-react";

interface StreamEvent {
  type: "tool_call" | "text_delta" | "tool_result" | "done" | "error";
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  error?: string;
}

interface UseSSEStreamOptions {
  onEvent?: (event: StreamEvent) => void;
  onComplete?: (fullText: string) => void;
  onError?: (error: string) => void;
}

// The backend's double-submit CSRF cookie: `__Host-csrf_token` over HTTPS, `csrf_token` otherwise.
const CSRF_COOKIES = ["__Host-csrf_token", "csrf_token"];

/** The CSRF token, read afresh on every call: a cookie-borne refresh rotates it. */
function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const cookies = document.cookie.split(";").map((c) => c.trim());
  for (const name of CSRF_COOKIES) {
    const hit = cookies.find((c) => c.startsWith(`${name}=`));
    if (hit) return decodeURIComponent(hit.slice(name.length + 1));
  }
  return "";
}

function send(url: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
    body: JSON.stringify(body),
  });
}

async function refreshSession(): Promise<boolean> {
  const response = await fetch("/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrfToken() },
  });
  return response.ok;
}

/** The message a refused request shows: problem+json `detail`, else the CSRF middleware's `{detail}`. */
async function refusal(response: Response): Promise<string> {
  if (response.status === 401) return "You are signed out. Sign in to chat.";
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    return wait ? `Too many messages. Try again in ${wait} seconds.` : "Too many messages. Try again later.";
  }
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail) return detail;
    }
  } catch {
    // not JSON: fall through to the status line
  }
  return `The chat request failed (HTTP ${response.status}).`;
}

export function useSSEStream(options: UseSSEStreamOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [toolCalls, setToolCalls] = useState<Array<{ tool: string; status: string }>>([]);

  const startStream = useCallback(
    async (url: string, body: Record<string, unknown>) => {
      setIsStreaming(true);
      setStreamText("");
      setToolCalls([]);
      let fullText = "";

      const handle = (event: StreamEvent) => {
        options.onEvent?.(event);
        switch (event.type) {
          case "text_delta":
            if (event.text) {
              fullText += event.text;
              setStreamText(fullText);
            }
            break;
          case "tool_call":
            if (event.tool) {
              const tool = event.tool;
              setToolCalls((prev) => [...prev, { tool, status: "running" }]);
            }
            break;
          case "tool_result":
            setToolCalls((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last) last.status = "done";
              return updated;
            });
            break;
          case "error":
            options.onError?.(event.error || "The chat stream reported an error.");
            break;
          case "done":
            break;
        }
      };

      const dispatch = (line: string) => {
        if (!line.startsWith("data: ")) return;
        let event: StreamEvent;
        try {
          event = JSON.parse(line.slice(6)) as StreamEvent;
        } catch {
          options.onError?.("The chat stream sent a malformed frame.");
          return;
        }
        handle(event);
      };

      try {
        let response = await send(url, body);
        if (response.status === 401 && (await refreshSession())) {
          response = await send(url, body); // once: the retry reads the rotated CSRF cookie
        }
        if (!response.ok) {
          options.onError?.(await refusal(response));
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("The chat response had no body.");

        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? ""; // a frame cut across chunks waits for its other half
          lines.forEach(dispatch);
        }
        buffer += decoder.decode();
        if (buffer) dispatch(buffer);
      } catch (error) {
        options.onError?.(error instanceof Error ? error.message : "The chat stream failed.");
      } finally {
        setIsStreaming(false);
        options.onComplete?.(fullText);
      }
    },
    [options]
  );

  return { isStreaming, streamText, toolCalls, startStream };
}

const toolIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  grep: Search,
  read_file: FileText,
  search: Search,
  default: Brain,
};

export function ToolCallIndicator({
  tool,
  status,
}: {
  tool: string;
  status: string;
}) {
  const Icon = toolIcons[tool] || toolIcons.default;
  const isDone = status === "done";

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {isDone ? (
        <CheckCircle className="h-3 w-3 text-green-500" />
      ) : (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      <Icon className="h-3 w-3" />
      <span>{tool}</span>
    </div>
  );
}

export function StreamingIndicator({ toolCalls }: { toolCalls: Array<{ tool: string; status: string }> }) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-2 p-2 rounded-lg bg-muted/50">
      {toolCalls.map((tc, i) => (
        <ToolCallIndicator key={i} tool={tc.tool} status={tc.status} />
      ))}
    </div>
  );
}
