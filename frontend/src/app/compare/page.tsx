"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getBacktestResult, listBacktests } from "@/lib/api";
import type {
  BacktestListItem,
  BacktestResult,
  MetricsSummary,
} from "@/types/backtest";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function backtestLabel(item: BacktestListItem): string {
  const date = new Date(item.created_at).toLocaleDateString();
  const ratio = item.parameters?.ratio ?? "?";
  return `${date} (${ratio}:1)`;
}

interface MetricRow {
  label: string;
  key: keyof MetricsSummary;
  format: (v: number) => string;
  higherIsBetter: boolean;
}

const METRIC_ROWS: MetricRow[] = [
  {
    label: "最終權益",
    key: "final_equity",
    format: (v) => `NT$${Math.round(v).toLocaleString()}`,
    higherIsBetter: true,
  },
  {
    label: "總報酬率",
    key: "total_return",
    format: (v) => `${(v * 100).toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    label: "XIRR",
    key: "xirr",
    format: (v) => `${(v * 100).toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    label: "Sharpe Ratio",
    key: "sharpe",
    format: (v) => v.toFixed(2),
    higherIsBetter: true,
  },
  {
    label: "最大回撤",
    key: "max_drawdown",
    format: (v) => `${(v * 100).toFixed(1)}%`,
    higherIsBetter: false,
  },
  {
    label: "最大回撤金額",
    key: "max_drawdown_amount",
    format: (v) => `NT$${Math.round(v).toLocaleString()}`,
    higherIsBetter: false,
  },
  {
    label: "PUT 總成本",
    key: "total_put_cost",
    format: (v) => `NT$${Math.round(v).toLocaleString()}`,
    higherIsBetter: false,
  },
  {
    label: "轉倉成本",
    key: "total_rollover_cost",
    format: (v) => `NT$${Math.round(v).toLocaleString()}`,
    higherIsBetter: false,
  },
];

function diffColor(diff: number, higherIsBetter: boolean): string {
  const positive = higherIsBetter ? diff > 0 : diff < 0;
  const negative = higherIsBetter ? diff < 0 : diff > 0;
  if (positive) return "text-green-600";
  if (negative) return "text-red-600";
  return "";
}

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground">載入中...</p>}>
      <CompareContent />
    </Suspense>
  );
}

function CompareContent() {
  const searchParams = useSearchParams();
  const [history, setHistory] = useState<BacktestListItem[]>([]);
  const [idA, setIdA] = useState<string>(searchParams.get("a") ?? "");
  const [idB, setIdB] = useState<string>(searchParams.get("b") ?? "");
  const [resultA, setResultA] = useState<BacktestResult | null>(null);
  const [resultB, setResultB] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBacktests(100, 0)
      .then((res) =>
        setHistory(res.items.filter((i) => i.status === "completed")),
      )
      .catch((e: Error) => setError(e.message));
  }, []);

  async function handleCompare() {
    if (!idA || !idB) return;
    setLoading(true);
    setError(null);
    try {
      const [a, b] = await Promise.all([
        getBacktestResult(idA),
        getBacktestResult(idB),
      ]);
      setResultA(a);
      setResultB(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : "載入失敗");
    } finally {
      setLoading(false);
    }
  }

  const mergedEquity = useMemo(() => {
    if (!resultA?.snapshots?.length || !resultB?.snapshots?.length) return [];
    const dateMap = new Map<
      string,
      { date: string; equityA?: number; equityB?: number }
    >();
    for (const s of resultA.snapshots) {
      const entry = dateMap.get(s.trade_date) ?? { date: s.trade_date };
      entry.equityA = Math.round(s.equity);
      dateMap.set(s.trade_date, entry);
    }
    for (const s of resultB.snapshots) {
      const entry = dateMap.get(s.trade_date) ?? { date: s.trade_date };
      entry.equityB = Math.round(s.equity);
      dateMap.set(s.trade_date, entry);
    }
    return Array.from(dateMap.values()).sort((a, b) =>
      a.date.localeCompare(b.date),
    );
  }, [resultA, resultB]);

  const labelA = resultA?.parameters
    ? `${resultA.parameters.ratio}:1`
    : "A";
  const labelB = resultB?.parameters
    ? `${resultB.parameters.ratio}:1`
    : "B";

  const mA = resultA?.metrics;
  const mB = resultB?.metrics;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">回測比較</h1>

      <Card>
        <CardHeader>
          <CardTitle>選擇回測</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] items-end">
            <div className="space-y-2">
              <Label>回測 A</Label>
              <Select value={idA} onValueChange={setIdA}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="選擇回測 A" />
                </SelectTrigger>
                <SelectContent>
                  {history.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {backtestLabel(item)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>回測 B</Label>
              <Select value={idB} onValueChange={setIdB}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="選擇回測 B" />
                </SelectTrigger>
                <SelectContent>
                  {history.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {backtestLabel(item)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleCompare}
              disabled={!idA || !idB || idA === idB || loading}
            >
              {loading ? "載入中..." : "比較"}
            </Button>
          </div>
          {error && <p className="text-red-600 mt-2">{error}</p>}
        </CardContent>
      </Card>

      {mA && mB && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>指標比較</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>指標</TableHead>
                    <TableHead className="text-right">
                      回測 A ({labelA})
                    </TableHead>
                    <TableHead className="text-right">
                      回測 B ({labelB})
                    </TableHead>
                    <TableHead className="text-right">差異 (B-A)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {METRIC_ROWS.map((row) => {
                    const valA = mA[row.key] as number;
                    const valB = mB[row.key] as number;
                    const diff = valB - valA;
                    return (
                      <TableRow key={row.key}>
                        <TableCell className="font-medium">
                          {row.label}
                        </TableCell>
                        <TableCell className="text-right">
                          {row.format(valA)}
                        </TableCell>
                        <TableCell className="text-right">
                          {row.format(valB)}
                        </TableCell>
                        <TableCell
                          className={`text-right font-medium ${diffColor(diff, row.higherIsBetter)}`}
                        >
                          {diff > 0 ? "+" : ""}
                          {row.format(diff)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>權益曲線對比</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={mergedEquity}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(v: string) => v.slice(5)}
                    fontSize={12}
                  />
                  <YAxis
                    tickFormatter={(v: number) =>
                      `${(v / 1000).toFixed(0)}k`
                    }
                    fontSize={12}
                  />
                  <Tooltip
                    formatter={(v) =>
                      typeof v === "number"
                        ? `NT$${v.toLocaleString()}`
                        : String(v)
                    }
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="equityA"
                    stroke="#2563eb"
                    name={`回測 A (${labelA})`}
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="equityB"
                    stroke="#dc2626"
                    name={`回測 B (${labelB})`}
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
