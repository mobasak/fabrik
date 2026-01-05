import Link from "next/link";
import { ArrowRight, Zap, Shield, Sparkles } from "lucide-react";
import { siteConfig } from "@/lib/config/site";

const features = [
  {
    icon: Zap,
    title: "Lightning Fast",
    description: "Process your files in seconds with our optimized pipeline.",
  },
  {
    icon: Shield,
    title: "Secure by Default",
    description: "Your data is encrypted and never stored longer than needed.",
  },
  {
    icon: Sparkles,
    title: "AI-Powered",
    description: "Leverage cutting-edge AI models for best-in-class results.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center justify-between">
          <div className="text-lg font-semibold">{siteConfig.name}</div>
          <nav className="flex items-center gap-6">
            <Link href="/pricing" className="text-sm text-muted-foreground hover:text-foreground">
              Pricing
            </Link>
            <Link href="/faq" className="text-sm text-muted-foreground hover:text-foreground">
              FAQ
            </Link>
            <Link
              href="/app"
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Get Started
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="py-24">
          <div className="mx-auto max-w-3xl px-4 text-center">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Your SaaS Tagline Here
            </h1>
            <p className="mt-6 text-lg text-muted-foreground">
              A brief description of what your SaaS does and why users should care.
              Keep it concise and compelling.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link
                href="/app/new"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
              >
                Start Free <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/pricing"
                className="rounded-lg border px-6 py-3 text-sm font-medium hover:bg-muted"
              >
                View Pricing
              </Link>
            </div>
          </div>
        </section>

        <section id="features" className="border-t py-24">
          <div className="mx-auto max-w-7xl px-4">
            <h2 className="text-center text-2xl font-bold">Features</h2>
            <div className="mt-12 grid gap-8 sm:grid-cols-3">
              {features.map((feature) => (
                <div key={feature.title} className="rounded-2xl border p-6">
                  <feature.icon className="h-8 w-8 text-primary" />
                  <h3 className="mt-4 font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="mx-auto max-w-7xl px-4 flex items-center justify-between text-sm text-muted-foreground">
          <div>&copy; {new Date().getFullYear()} {siteConfig.name}</div>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
            <Link href="/terms" className="hover:text-foreground">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
