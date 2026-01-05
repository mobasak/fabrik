import Link from "next/link";
import { Check } from "lucide-react";
import { siteConfig } from "@/lib/config/site";

const plans = [
  {
    name: "Free",
    price: "$0",
    description: "For trying things out",
    features: ["5 jobs per month", "Basic processing", "Email support"],
    cta: "Get Started",
    href: "/app",
  },
  {
    name: "Pro",
    price: "$29",
    description: "For professionals",
    features: ["Unlimited jobs", "Priority processing", "API access", "Priority support"],
    cta: "Start Free Trial",
    href: "/app",
    popular: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For large teams",
    features: ["Everything in Pro", "Custom integrations", "Dedicated support", "SLA"],
    cta: "Contact Sales",
    href: "mailto:sales@example.com",
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-lg font-semibold">{siteConfig.name}</Link>
          <Link
            href="/app"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Get Started
          </Link>
        </div>
      </header>

      <main className="py-24">
        <div className="mx-auto max-w-7xl px-4">
          <div className="text-center">
            <h1 className="text-3xl font-bold">Simple, transparent pricing</h1>
            <p className="mt-4 text-muted-foreground">Choose the plan that works for you</p>
          </div>

          <div className="mt-16 grid gap-8 sm:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-2xl border p-8 ${plan.popular ? "border-primary ring-1 ring-primary" : ""}`}
              >
                {plan.popular && (
                  <div className="mb-4 inline-block rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                    Most Popular
                  </div>
                )}
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <div className="mt-2">
                  <span className="text-3xl font-bold">{plan.price}</span>
                  {plan.price !== "Custom" && <span className="text-muted-foreground">/month</span>}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{plan.description}</p>
                <ul className="mt-6 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-500" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.href}
                  className={`mt-8 block rounded-lg px-4 py-2 text-center text-sm font-medium ${
                    plan.popular
                      ? "bg-primary text-primary-foreground"
                      : "border hover:bg-muted"
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
