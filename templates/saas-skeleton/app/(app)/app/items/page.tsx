import Link from "next/link";
import { Plus, MoreHorizontal } from "lucide-react";
import { PageHeader, SectionCard, EmptyState } from "@/components/common";

const mockItems = [
  { id: "1", name: "Job 1", status: "SUCCEEDED", createdAt: "2024-01-01" },
  { id: "2", name: "Job 2", status: "RUNNING", createdAt: "2024-01-02" },
];

const statusColors: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  QUEUED: "bg-blue-100 text-blue-800",
  RUNNING: "bg-yellow-100 text-yellow-800",
  SUCCEEDED: "bg-green-100 text-green-800",
  FAILED: "bg-red-100 text-red-800",
};

export default function ItemsPage() {
  const items = mockItems;

  return (
    <div>
      <PageHeader
        title="Items"
        description="View and manage all your jobs."
        actions={
          <Link
            href="/app/new"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Plus className="h-4 w-4" /> New
          </Link>
        }
      />

      {items.length === 0 ? (
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
      ) : (
        <SectionCard>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-3 text-left font-medium">Name</th>
                  <th className="py-3 text-left font-medium">Status</th>
                  <th className="py-3 text-left font-medium">Created</th>
                  <th className="py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="py-3">
                      <Link href={`/app/items/${item.id}`} className="hover:underline">
                        {item.name}
                      </Link>
                    </td>
                    <td className="py-3">
                      <span className={`rounded-full px-2 py-1 text-xs ${statusColors[item.status]}`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 text-muted-foreground">{item.createdAt}</td>
                    <td className="py-3 text-right">
                      <button className="rounded-lg p-1 hover:bg-muted">
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
