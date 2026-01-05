import Link from "next/link";
import { siteConfig } from "@/lib/config/site";

const faqs = [
  {
    question: "How does the free trial work?",
    answer: "You can try all Pro features free for 14 days. No credit card required.",
  },
  {
    question: "Can I cancel anytime?",
    answer: "Yes, you can cancel your subscription at any time. No questions asked.",
  },
  {
    question: "What file formats do you support?",
    answer: "We support most common formats including PDF, DOCX, TXT, and more.",
  },
  {
    question: "Is my data secure?",
    answer: "Yes, all data is encrypted in transit and at rest. We never share your data with third parties.",
  },
  {
    question: "Do you offer refunds?",
    answer: "Yes, we offer a 30-day money-back guarantee if you're not satisfied.",
  },
];

export default function FAQPage() {
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
        <div className="mx-auto max-w-3xl px-4">
          <h1 className="text-3xl font-bold text-center">Frequently Asked Questions</h1>
          <div className="mt-12 space-y-6">
            {faqs.map((faq) => (
              <div key={faq.question} className="rounded-2xl border p-6">
                <h3 className="font-semibold">{faq.question}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
