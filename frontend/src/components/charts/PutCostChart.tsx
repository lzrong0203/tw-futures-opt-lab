"use client";

import type { Snapshot } from "@/types/backtest";
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

export default function PutCostChart({ snapshots }: Props) {
  const data = snapshots.map((s) => ({
    date: s.trade_date,
    cost: Math.round(s.total_put_cost),
  }));

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
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          formatter={(value) => [
            `NT$${Number(value).toLocaleString()}`,
            "PUT Cost",
          ]}
        />
        <Area
          type="monotone"
          dataKey="cost"
          stroke="#f59e0b"
          fill="#fbbf24"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
