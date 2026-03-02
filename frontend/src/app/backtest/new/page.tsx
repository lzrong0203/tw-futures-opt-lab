"use client";

import BacktestForm from "@/components/forms/BacktestForm";
import { createBacktest, getBacktestStatus } from "@/lib/api";
import type { BacktestRequest } from "@/types/backtest";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function NewBacktestPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(req: BacktestRequest) {
    setLoading(true);
    setError(null);
    try {
      const created = await createBacktest(req);

      // Poll until done
      let status = await getBacktestStatus(created.id);
      while (status.status === "running") {
        await new Promise((r) => setTimeout(r, 2000));
        status = await getBacktestStatus(created.id);
      }

      if (status.status === "failed") {
        setError(status.error_message ?? "Backtest failed");
        setLoading(false);
        return;
      }

      router.push(`/backtest/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">New Backtest</h1>
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
          {error}
        </div>
      )}
      <BacktestForm onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
