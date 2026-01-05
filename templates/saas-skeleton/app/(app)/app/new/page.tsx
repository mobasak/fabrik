"use client";

import { useState } from "react";
import { Upload } from "lucide-react";
import { PageHeader, SectionCard } from "@/components/common";

export default function NewJobPage() {
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Implement job creation
    console.log("Creating job with file:", file?.name);
  };

  return (
    <div>
      <PageHeader
        title="Create New"
        description="Upload an input and start a new job."
      />

      <SectionCard>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="text-sm font-medium">Input File</label>
            <div className="mt-2 rounded-xl border border-dashed p-8 text-center">
              <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
              <div className="mt-2 text-sm text-muted-foreground">
                {file ? file.name : "Drag & drop or click to select"}
              </div>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="mt-4 text-sm"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Option A</label>
              <input
                type="text"
                placeholder="e.g., language"
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Option B</label>
              <input
                type="text"
                placeholder="e.g., model"
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Start Processing
          </button>
        </form>
      </SectionCard>
    </div>
  );
}
