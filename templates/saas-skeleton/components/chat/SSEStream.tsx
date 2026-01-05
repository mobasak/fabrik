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

export function useSSEStream(options: UseSSEStreamOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [toolCalls, setToolCalls] = useState<Array<{ tool: string; status: string }>>([]);

  const startStream = useCallback(
    async (url: string, body: Record<string, unknown>) => {
      setIsStreaming(true);
      setStreamText("");
      setToolCalls([]);

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event: StreamEvent = JSON.parse(line.slice(6));
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
                      setToolCalls((prev) => [...prev, { tool: event.tool!, status: "running" }]);
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
                    options.onError?.(event.error || "Unknown error");
                    break;
                  case "done":
                    options.onComplete?.(fullText);
                    break;
                }
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }

        setIsStreaming(false);
        options.onComplete?.(fullText);
      } catch (error) {
        setIsStreaming(false);
        options.onError?.(error instanceof Error ? error.message : "Stream failed");
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
