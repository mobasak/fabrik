import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  children: ReactNode;
  title?: string;
  className?: string;
}

export function SectionCard({ children, title, className }: SectionCardProps) {
  return (
    <div className={cn("rounded-2xl border p-6 shadow-sm", className)}>
      {title && <div className="mb-4 text-sm font-medium">{title}</div>}
      {children}
    </div>
  );
}
