"use client";

import type { Snapshot } from "@/types/backtest";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  snapshots: Snapshot[];
}

export default function DailyPnL({ snapshots }: Props) {
  const data = snapshots.map((s) => ({
    date: s.trade_date,
    pnl: Math.round(s.daily_pnl),
  }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
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
            "Daily P&L",
          ]}
        />
        <Bar dataKey="pnl" fill="#2563eb" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
