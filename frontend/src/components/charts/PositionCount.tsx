"use client";

import type { Snapshot } from "@/types/backtest";
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

interface Props {
  snapshots: Snapshot[];
}

export default function PositionCount({ snapshots }: Props) {
  const data = snapshots.map((s) => ({
    date: s.trade_date,
    futures: s.futures_count,
    puts: s.puts_count,
  }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Line
          type="stepAfter"
          dataKey="futures"
          stroke="#2563eb"
          name="Futures"
          dot={false}
          strokeWidth={2}
        />
        <Line
          type="stepAfter"
          dataKey="puts"
          stroke="#dc2626"
          name="PUTs"
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
