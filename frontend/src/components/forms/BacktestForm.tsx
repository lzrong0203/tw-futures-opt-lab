"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { BacktestRequest } from "@/types/backtest";
import { useState } from "react";

const RATIO_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  loading?: boolean;
}

export default function BacktestForm({ onSubmit, loading }: Props) {
  const [ratio, setRatio] = useState("3");
  const [capital, setCapital] = useState(200000);
  const [start, setStart] = useState("2025-01-01");
  const [end, setEnd] = useState("2026-02-28");
  const [monthly, setMonthly] = useState(30000);
  const [autoInject, setAutoInject] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      ratio: parseInt(ratio, 10),
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
        <CardTitle>回測參數</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="ratio">期貨:PUT 比例</Label>
            <Select value={ratio} onValueChange={setRatio}>
              <SelectTrigger id="ratio" className="w-full">
                <SelectValue placeholder="選擇比例" />
              </SelectTrigger>
              <SelectContent>
                {RATIO_OPTIONS.map((r) => (
                  <SelectItem key={r} value={String(r)}>
                    {r}:1
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="capital">初始資金 (NT$)</Label>
            <Input
              id="capital"
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="start">起始日期</Label>
            <Input
              id="start"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="end">結束日期</Label>
            <Input
              id="end"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="monthly">每月投入 (NT$)</Label>
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
            <Label htmlFor="autoInject">自動追繳</Label>
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "執行中..." : "開始回測"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
