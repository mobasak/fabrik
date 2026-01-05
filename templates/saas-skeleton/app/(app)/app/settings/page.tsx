"use client";

import { useState } from "react";
import { PageHeader, SectionCard } from "@/components/common";

export default function SettingsPage() {
  const [name, setName] = useState("John Doe");
  const [email, setEmail] = useState("john@example.com");

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Manage your account and preferences."
      />

      <div className="space-y-6">
        <SectionCard title="Profile">
          <div className="space-y-4 max-w-md">
            <div>
              <label className="text-sm font-medium">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              />
            </div>
            <button className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
              Save Changes
            </button>
          </div>
        </SectionCard>

        <SectionCard title="API Keys">
          <div className="space-y-4 max-w-md">
            <p className="text-sm text-muted-foreground">
              Use API keys to access your data programmatically.
            </p>
            <button className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">
              Generate New Key
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Billing">
          <div className="space-y-4 max-w-md">
            <div className="rounded-xl border p-4">
              <div className="text-sm font-medium">Current Plan</div>
              <div className="text-2xl font-bold">Free</div>
              <div className="text-sm text-muted-foreground">5 jobs/month</div>
            </div>
            <button className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
              Upgrade to Pro
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Danger Zone">
          <div className="space-y-4 max-w-md">
            <p className="text-sm text-muted-foreground">
              Permanently delete your account and all associated data.
            </p>
            <button className="rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground">
              Delete Account
            </button>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
