import Link from "next/link";
import { Plus, FileText, Clock } from "lucide-react";
import { PageHeader, SectionCard, EmptyState } from "@/components/common";

export default function DashboardPage() {
  const hasItems = false;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Welcome back! Here's an overview of your activity."
        actions={
          <Link
            href="/app/new"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Plus className="h-4 w-4" /> New
          </Link>
        }
      />

      <div className="grid gap-6 sm:grid-cols-3 mb-6">
        <SectionCard>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="text-2xl font-bold">0</div>
              <div className="text-sm text-muted-foreground">Total Jobs</div>
            </div>
          </div>
        </SectionCard>
        <SectionCard>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-green-500/10 p-2">
              <FileText className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <div className="text-2xl font-bold">0</div>
              <div className="text-sm text-muted-foreground">Completed</div>
            </div>
          </div>
        </SectionCard>
        <SectionCard>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-orange-500/10 p-2">
              <Clock className="h-5 w-5 text-orange-500" />
            </div>
            <div>
              <div className="text-2xl font-bold">0</div>
              <div className="text-sm text-muted-foreground">In Progress</div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Recent Items">
        {hasItems ? (
          <div>Items will appear here</div>
        ) : (
          <EmptyState
            title="No items yet"
            description="Create your first item to get started."
            action={
              <Link
                href="/app/new"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                <Plus className="h-4 w-4" /> Create First Item
              </Link>
            }
          />
        )}
      </SectionCard>
    </div>
  );
}
