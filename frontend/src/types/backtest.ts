/** API types mirroring api/schemas.py */

export interface BacktestRequest {
  ratio: number;
  initial_capital: number;
  backtest_start: string;
  backtest_end: string;
  monthly_contribution: number;
  allow_auto_injection: boolean;
}

export interface Trade {
  trade_date: string;
  instrument: string;
  action: string;
  price: number;
  contracts: number;
  pnl: number;
  commission: number;
  tax: number;
  strike: number | null;
  expiry: string | null;
}

export interface Snapshot {
  trade_date: string;
  equity: number;
  cash: number;
  margin_used: number;
  futures_unrealized_pnl: number;
  puts_market_value: number;
  total_put_cost: number;
  futures_count: number;
  puts_count: number;
  daily_pnl: number;
}

export interface CashFlow {
  date: string;
  amount: number;
}

export interface MetricsSummary {
  final_equity: number;
  total_return: number;
  xirr: number;
  sharpe: number;
  max_drawdown: number;
  max_drawdown_amount: number;
  total_put_cost: number;
  total_rollover_cost: number;
  total_injected: number;
  total_monthly: number;
  futures_per_put: number;
}

export interface BacktestCreated {
  id: string;
  status: string;
  created_at: string;
}

export interface BacktestStatus {
  id: string;
  status: "running" | "completed" | "failed";
  error_message: string | null;
}

export interface BacktestResult {
  id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  parameters: BacktestRequest | null;
  snapshots: Snapshot[];
  trades: Trade[];
  cash_flows: CashFlow[];
  metrics: MetricsSummary | null;
}

export interface BacktestListItem {
  id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  parameters: BacktestRequest | null;
  metrics: MetricsSummary | null;
}

export interface BacktestListResponse {
  items: BacktestListItem[];
  total: number;
}
