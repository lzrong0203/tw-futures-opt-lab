"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listBacktests } from "@/lib/api";
import type { BacktestListItem } from "@/types/backtest";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function HistoryPage() {
  const [items, setItems] = useState<BacktestListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBacktests()
      .then((res) => setItems(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Backtest History</h1>

      {error && <p className="text-red-600">Error: {error}</p>}

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            No backtests yet.{" "}
            <Link href="/backtest/new" className="underline">
              Run one now
            </Link>
            .
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{items.length} Backtests</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>比例</TableHead>
                  <TableHead className="text-right">Capital</TableHead>
                  <TableHead className="text-right">Return</TableHead>
                  <TableHead className="text-right">XIRR</TableHead>
                  <TableHead className="text-right">MDD</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-xs">
                      {new Date(item.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          item.status === "completed"
                            ? "default"
                            : item.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {item.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {item.parameters?.ratio != null
                        ? `${item.parameters.ratio}:1`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.parameters
                        ? `${item.parameters.initial_capital.toLocaleString()}`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.metrics
                        ? `${(item.metrics.total_return * 100).toFixed(1)}%`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.metrics
                        ? `${(item.metrics.xirr * 100).toFixed(1)}%`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.metrics
                        ? `${(item.metrics.max_drawdown * 100).toFixed(1)}%`
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/backtest/${item.id}`}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        View
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
