"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Plus, List, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { siteConfig, navConfig } from "@/lib/config/site";

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  Plus,
  List,
  Settings,
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
          <aside className="rounded-2xl border p-4">
            <div className="text-sm font-semibold">{siteConfig.name}</div>
            <nav className="mt-4 space-y-1 text-sm">
              {navConfig.appNav.map((item) => {
                const Icon = iconMap[item.icon];
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-muted",
                      isActive && "bg-muted font-medium"
                    )}
                  >
                    {Icon && <Icon className="h-4 w-4" />}
                    {item.title}
                  </Link>
                );
              })}
            </nav>
            <div className="mt-auto pt-4 border-t mt-6">
              <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </aside>
          <main className="rounded-2xl border p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
