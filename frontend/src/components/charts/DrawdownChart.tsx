"use client";

import type { Snapshot } from "@/types/backtest";
import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  snapshots: Snapshot[];
}

function computeDrawdown(snapshots: Snapshot[]) {
  let peak = 0;
  return snapshots.map((s) => {
    peak = Math.max(peak, s.equity);
    const dd = peak > 0 ? ((s.equity - peak) / peak) * 100 : 0;
    return { date: s.trade_date, drawdown: Math.round(dd * 100) / 100 };
  });
}

export default function DrawdownChart({ snapshots }: Props) {
  const data = useMemo(() => computeDrawdown(snapshots), [snapshots]);

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip formatter={(value) => [`${value}%`, "Drawdown"]} />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="#dc2626"
          fill="#ef4444"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
