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

/** The CSRF token, read afresh on every call: a cookie-borne refresh rotates it. The raw value,
 * as the server compares it (quotes stripped, never URL-decoded). */
function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const cookies = document.cookie.split(";").map((c) => c.trim());
  for (const name of CSRF_COOKIES) {
    const hit = cookies.find((c) => c.startsWith(`${name}=`));
    if (hit) return hit.slice(name.length + 1).replace(/^"|"$/g, "");
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

// One refresh at a time for the whole page: the backend rotates a refresh token once, so a second
// concurrent refresh would lose and sign the user out.
let refreshing: Promise<boolean> | null = null;
const REFRESH_TIMEOUT_MS = 10_000;

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch("/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrfToken() },
    signal: AbortSignal.timeout(REFRESH_TIMEOUT_MS), // a hung refresh is signed out, never a stuck page
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail) return detail;
    }
  } catch {
    // not JSON
  }
  return null;
}

function isStreamEvent(value: unknown): value is StreamEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  return (
    typeof event.type === "string" &&
    (event.text === undefined || typeof event.text === "string") &&
    (event.error === undefined || typeof event.error === "string") &&
    (event.tool === undefined || typeof event.tool === "string")
  );
}

/** The message a refused request shows: problem+json `detail`, else the CSRF middleware's `{detail}`. */
async function refusal(response: Response): Promise<string> {
  if (response.status === 401) return "You are signed out. Sign in to chat.";
  const detail = await readDetail(response);
  if (response.status === 429) {
    // the detail names the bucket: a full tenant or app bucket is a shared budget, not the user's own
    const wait = response.headers.get("Retry-After");
    const limit = detail ?? "Too many messages.";
    return wait ? `${limit} Try again in ${wait} seconds.` : `${limit} Try again later.`;
  }
  return detail ?? `The chat request failed (HTTP ${response.status}).`;
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
      let failed = false;
      let finished = false;

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
            setToolCalls((prev) =>
              prev.map((call, i) => (i === prev.length - 1 ? { ...call, status: "done" } : call))
            );
            break;
          case "error":
            failed = true;
            options.onError?.(event.error || "The chat stream reported an error.");
            break;
          case "done":
            finished = true;
            break;
        }
      };

      const dispatch = (line: string) => {
        if (!line.startsWith("data: ")) return;
        let event: unknown;
        try {
          event = JSON.parse(line.slice(6));
        } catch {
          event = undefined;
        }
        if (!isStreamEvent(event)) {
          failed = true;
          options.onError?.("The chat stream sent a malformed frame.");
          return;
        }
        handle(event);
      };

      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        let response = await send(url, body);
        if (response.status === 401 && (await refreshSession())) {
          await response.body?.cancel();
          response = await send(url, body); // once: the retry reads the rotated CSRF cookie
        }
        if (!response.ok) {
          options.onError?.(await refusal(response));
          return;
        }

        reader = response.body?.getReader();
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
        if (!failed && !finished) {
          // the backend always ends with `done` or `error`: a stream without either was cut off
          options.onError?.("The reply was cut off. Try again.");
        } else if (!failed && !fullText) {
          // a reasoning model capped by the server's max_tokens can finish with no visible text
          options.onError?.("The model returned an empty reply. Try again.");
        }
      } catch (error) {
        options.onError?.(error instanceof Error ? error.message : "The chat stream failed.");
      } finally {
        // an early exit (a throwing handler) must not leave the backend relaying to max_tokens
        await reader?.cancel().catch(() => undefined);
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
