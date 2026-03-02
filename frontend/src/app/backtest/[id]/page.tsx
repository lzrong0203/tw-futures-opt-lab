"use client";

import DailyPnL from "@/components/charts/DailyPnL";
import DrawdownChart from "@/components/charts/DrawdownChart";
import EquityCurve from "@/components/charts/EquityCurve";
import PositionCount from "@/components/charts/PositionCount";
import PutCostChart from "@/components/charts/PutCostChart";
import TradeTable from "@/components/tables/TradeTable";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getBacktestResult } from "@/lib/api";
import type { BacktestResult } from "@/types/backtest";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-muted-foreground text-xs">{label}</p>
        <p className="text-xl font-bold">{value}</p>
        {sub && <p className="text-muted-foreground text-xs">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export default function BacktestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBacktestResult(id)
      .then(setResult)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <p className="text-red-600">Error: {error}</p>;
  if (!result) return <p className="text-muted-foreground">Loading...</p>;

  const m = result.metrics;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Backtest Result</h1>
          <p className="text-muted-foreground text-sm">ID: {result.id}</p>
        </div>
        <Badge
          variant={
            result.status === "completed" ? "default" : "destructive"
          }
        >
          {result.status}
        </Badge>
      </div>

      {m && (
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
          <MetricCard
            label="Final Equity"
            value={`NT$${m.final_equity.toLocaleString()}`}
          />
          <MetricCard
            label="Total Return"
            value={`${(m.total_return * 100).toFixed(1)}%`}
          />
          <MetricCard label="XIRR" value={`${(m.xirr * 100).toFixed(1)}%`} />
          <MetricCard label="Sharpe Ratio" value={m.sharpe.toFixed(2)} />
          <MetricCard
            label="Max Drawdown"
            value={`${(m.max_drawdown * 100).toFixed(1)}%`}
            sub={`NT$${m.max_drawdown_amount.toLocaleString()}`}
          />
          <MetricCard
            label="Total PUT Cost"
            value={`NT$${m.total_put_cost.toLocaleString()}`}
          />
          <MetricCard
            label="Rollover Cost"
            value={`NT$${m.total_rollover_cost.toLocaleString()}`}
          />
          <MetricCard
            label="Ratio"
            value={`1:${m.futures_per_put}`}
            sub="PUT:Futures"
          />
        </div>
      )}

      <Separator />

      <Tabs defaultValue="equity">
        <TabsList>
          <TabsTrigger value="equity">Equity Curve</TabsTrigger>
          <TabsTrigger value="drawdown">Drawdown</TabsTrigger>
          <TabsTrigger value="pnl">Daily P&L</TabsTrigger>
          <TabsTrigger value="positions">Positions</TabsTrigger>
          <TabsTrigger value="putcost">PUT Cost</TabsTrigger>
        </TabsList>
        <TabsContent value="equity">
          <Card>
            <CardHeader>
              <CardTitle>Equity Curve</CardTitle>
            </CardHeader>
            <CardContent>
              <EquityCurve snapshots={result.snapshots} />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="drawdown">
          <Card>
            <CardHeader>
              <CardTitle>Drawdown</CardTitle>
            </CardHeader>
            <CardContent>
              <DrawdownChart snapshots={result.snapshots} />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="pnl">
          <Card>
            <CardHeader>
              <CardTitle>Daily P&L</CardTitle>
            </CardHeader>
            <CardContent>
              <DailyPnL snapshots={result.snapshots} />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="positions">
          <Card>
            <CardHeader>
              <CardTitle>Position Count</CardTitle>
            </CardHeader>
            <CardContent>
              <PositionCount snapshots={result.snapshots} />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="putcost">
          <Card>
            <CardHeader>
              <CardTitle>Cumulative PUT Cost</CardTitle>
            </CardHeader>
            <CardContent>
              <PutCostChart snapshots={result.snapshots} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Trade History ({result.trades.length} trades)</CardTitle>
        </CardHeader>
        <CardContent>
          <TradeTable trades={result.trades} />
        </CardContent>
      </Card>
    </div>
  );
}
