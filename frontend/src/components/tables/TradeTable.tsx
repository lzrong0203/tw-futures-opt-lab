"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Trade } from "@/types/backtest";
import { useState } from "react";

interface Props {
  trades: Trade[];
}

export default function TradeTable({ trades }: Props) {
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const totalPages = Math.ceil(trades.length / pageSize);
  const visible = trades.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Instrument</TableHead>
              <TableHead>Action</TableHead>
              <TableHead className="text-right">Price</TableHead>
              <TableHead className="text-right">Contracts</TableHead>
              <TableHead className="text-right">P&L</TableHead>
              <TableHead className="text-right">Strike</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((t, i) => (
              <TableRow key={`${t.trade_date}-${i}`}>
                <TableCell className="text-xs">{t.trade_date}</TableCell>
                <TableCell>
                  <Badge variant={t.instrument === "MTX" ? "default" : "secondary"}>
                    {t.instrument}
                  </Badge>
                </TableCell>
                <TableCell>{t.action}</TableCell>
                <TableCell className="text-right">
                  {t.price.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">{t.contracts}</TableCell>
                <TableCell
                  className={`text-right ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}
                >
                  {t.pnl.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {t.strike ?? "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {totalPages > 1 && (
        <div className="mt-2 flex items-center justify-between text-sm">
          <span>
            Page {page + 1} of {totalPages} ({trades.length} trades)
          </span>
          <div className="space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 border rounded disabled:opacity-50"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 border rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
