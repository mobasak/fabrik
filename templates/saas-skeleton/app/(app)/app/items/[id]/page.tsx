import Link from "next/link";
import { ArrowLeft, Download, RefreshCw } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/common";

const mockJob = {
  id: "job_123",
  name: "Sample Job",
  status: "RUNNING" as const,
  progress: 65,
  createdAt: "2024-01-01T12:00:00Z",
  outputs: [
    { name: "result.json", size: "12 KB" },
    { name: "report.pdf", size: "1.2 MB" },
  ],
};

export default function ItemDetailPage() {
  const job = mockJob;

  return (
    <div>
      <div className="mb-4">
        <Link
          href="/app/items"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Items
        </Link>
      </div>

      <PageHeader
        title={job.name}
        description={`Status: ${job.status} • Created: ${new Date(job.createdAt).toLocaleDateString()}`}
        actions={
          <>
            <button className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
              <Download className="h-4 w-4" /> Download All
            </button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="Progress">
          <div className="space-y-3">
            <div className="h-2 w-full rounded-full bg-muted">
              <div
                className="h-2 rounded-full bg-primary transition-all"
                style={{ width: `${job.progress}%` }}
              />
            </div>
            <div className="text-sm text-muted-foreground">{job.progress}% complete</div>
          </div>
        </SectionCard>

        <div className="lg:col-span-2">
          <SectionCard title="Outputs">
            {job.outputs.length === 0 ? (
              <div className="text-sm text-muted-foreground">No outputs yet</div>
            ) : (
              <div className="space-y-2">
                {job.outputs.map((output) => (
                  <div
                    key={output.name}
                    className="flex items-center justify-between rounded-xl border p-3"
                  >
                    <div>
                      <div className="text-sm font-medium">{output.name}</div>
                      <div className="text-xs text-muted-foreground">{output.size}</div>
                    </div>
                    <button className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted">
                      Download
                    </button>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
