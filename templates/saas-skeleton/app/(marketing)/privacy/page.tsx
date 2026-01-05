import Link from "next/link";
import { siteConfig } from "@/lib/config/site";

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-lg font-semibold">{siteConfig.name}</Link>
        </div>
      </header>

      <main className="py-24">
        <div className="mx-auto max-w-3xl px-4 prose prose-sm">
          <h1>Privacy Policy</h1>
          <p>Last updated: {new Date().toLocaleDateString()}</p>

          <h2>Information We Collect</h2>
          <p>We collect information you provide directly, such as account information and uploaded files.</p>

          <h2>How We Use Your Information</h2>
          <p>We use your information to provide and improve our services.</p>

          <h2>Data Retention</h2>
          <p>We retain your data only as long as necessary to provide our services.</p>

          <h2>Contact</h2>
          <p>If you have questions about this Privacy Policy, please contact us.</p>
        </div>
      </main>
    </div>
  );
}
