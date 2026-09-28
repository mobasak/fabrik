import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";
import { siteConfig } from "@/lib/config/site";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: siteConfig.name,
  description: siteConfig.description,
};

// Runs before first paint: applies the stored theme (localStorage "theme" = "dark" | "light")
// or, when none is stored, the OS preference — so class-based dark mode never flashes the
// wrong theme on load — and an unreadable localStorage (private mode) still gets the OS
// preference. A theme toggle writes that same key.
const themeScript = `(function(){var t=null;try{t=localStorage.getItem("theme")}catch(e){}try{var d=t?t==="dark":window.matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={inter.className}>
        {children}
        {/* Sonner: Enables mandatory Success, Error, Loading states per UI patterns */}
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
