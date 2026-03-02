"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { BacktestRequest } from "@/types/backtest";
import { useState } from "react";

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  loading?: boolean;
}

export default function BacktestForm({ onSubmit, loading }: Props) {
  const [ratios, setRatios] = useState("3,5");
  const [capital, setCapital] = useState(200000);
  const [start, setStart] = useState("2025-01-01");
  const [end, setEnd] = useState("2026-02-28");
  const [monthly, setMonthly] = useState(30000);
  const [autoInject, setAutoInject] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      ratios: ratios.split(",").map((s) => parseInt(s.trim(), 10)),
      initial_capital: capital,
      backtest_start: start,
      backtest_end: end,
      monthly_contribution: monthly,
      allow_auto_injection: autoInject,
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Parameters</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="ratios">Futures:PUT Ratios</Label>
            <Input
              id="ratios"
              value={ratios}
              onChange={(e) => setRatios(e.target.value)}
              placeholder="3,5"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="capital">Initial Capital (NT$)</Label>
            <Input
              id="capital"
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="start">Start Date</Label>
            <Input
              id="start"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="end">End Date</Label>
            <Input
              id="end"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="monthly">Monthly Contribution (NT$)</Label>
            <Input
              id="monthly"
              type="number"
              value={monthly}
              onChange={(e) => setMonthly(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end space-x-2">
            <input
              id="autoInject"
              type="checkbox"
              checked={autoInject}
              onChange={(e) => setAutoInject(e.target.checked)}
              className="h-4 w-4"
            />
            <Label htmlFor="autoInject">Auto Cash Injection</Label>
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Running..." : "Run Backtest"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
