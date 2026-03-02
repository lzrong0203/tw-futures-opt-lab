/** API client for backend communication. */

import type {
  BacktestCreated,
  BacktestListResponse,
  BacktestRequest,
  BacktestResult,
  BacktestStatus,
} from "@/types/backtest";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function createBacktest(req: BacktestRequest): Promise<BacktestCreated> {
  return fetchJSON("/api/backtest", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getBacktestStatus(id: string): Promise<BacktestStatus> {
  return fetchJSON(`/api/backtest/${id}/status`);
}

export function getBacktestResult(id: string): Promise<BacktestResult> {
  return fetchJSON(`/api/backtest/${id}`);
}

export function listBacktests(
  limit = 50,
  offset = 0,
): Promise<BacktestListResponse> {
  return fetchJSON(`/api/backtest?limit=${limit}&offset=${offset}`);
}
