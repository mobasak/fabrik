"use client";

import { useState, useRef, useEffect } from "react";
import { Send, User, Bot, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSSEStream, StreamingIndicator } from "./SSEStream";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatUIProps {
  endpoint: string;
  placeholder?: string;
  systemPrompt?: string;
  className?: string;
}

export function ChatUI({
  endpoint,
  placeholder = "Type a message...",
  systemPrompt,
  className,
}: ChatUIProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { isStreaming, streamText, toolCalls, startStream } = useSSEStream({
    onComplete: (fullText) => {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant") {
          last.content = fullText;
        }
        return updated;
      });
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
    };

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");

    await startStream(endpoint, {
      message: userMessage.content,
      systemPrompt,
    });
  };

  return (
    <div className={cn("flex flex-col h-[600px] rounded-2xl border", className)}>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Start a conversation
          </div>
        )}

        {messages.map((message, index) => {
          const isLast = index === messages.length - 1;
          const isStreamingThis = isLast && message.role === "assistant" && isStreaming;

          return (
            <div
              key={message.id}
              className={cn(
                "flex gap-3",
                message.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              {message.role === "assistant" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary-foreground" />
                </div>
              )}

              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-2",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                )}
              >
                {isStreamingThis && <StreamingIndicator toolCalls={toolCalls} />}
                <p className="text-sm whitespace-pre-wrap">
                  {isStreamingThis ? streamText : message.content}
                  {isStreamingThis && (
                    <span className="inline-block w-1 h-4 ml-1 bg-current animate-pulse" />
                  )}
                </p>
              </div>

              {message.role === "user" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={placeholder}
            disabled={isStreaming}
            className="flex-1 rounded-xl border px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="rounded-xl bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
