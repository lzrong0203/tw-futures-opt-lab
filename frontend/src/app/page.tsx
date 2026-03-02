import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          TW Futures Options Lab
        </h1>
        <p className="text-muted-foreground mt-2">
          Backtest dashboard for micro TAIEX futures + weekly PUT protection
          strategy.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>New Backtest</CardTitle>
            <CardDescription>
              Configure parameters and run a new backtest scenario.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/backtest/new">
              <Button className="w-full">Run Backtest</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>History</CardTitle>
            <CardDescription>
              Browse and compare previous backtest results.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/history">
              <Button variant="outline" className="w-full">
                View History
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
