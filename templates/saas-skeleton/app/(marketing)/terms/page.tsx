import Link from "next/link";
import { siteConfig } from "@/lib/config/site";

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-lg font-semibold">{siteConfig.name}</Link>
        </div>
      </header>

      <main className="py-24">
        <div className="mx-auto max-w-3xl px-4 prose prose-sm">
          <h1>Terms of Service</h1>
          <p>Last updated: {new Date().toLocaleDateString()}</p>

          <h2>1. Terms</h2>
          <p>
            By accessing this website, you agree to be bound by these Terms of Service
            and agree that you are responsible for compliance with applicable local laws.
          </p>

          <h2>2. Use License</h2>
          <p>
            Permission is granted to temporarily use the service for personal,
            non-commercial transitory viewing only.
          </p>

          <h2>3. Disclaimer</h2>
          <p>
            The materials on this website are provided on an &apos;as is&apos; basis.
            We make no warranties, expressed or implied, and hereby disclaim all warranties.
          </p>

          <h2>4. Limitations</h2>
          <p>
            In no event shall we be liable for any damages arising out of the use
            or inability to use the materials on this website.
          </p>

          <h2>5. Contact</h2>
          <p>
            If you have any questions about these Terms, please contact us.
          </p>
        </div>
      </main>
    </div>
  );
}
