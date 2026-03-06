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

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>新增回測</CardTitle>
            <CardDescription>
              設定參數並執行新的回測。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/backtest/new">
              <Button className="w-full">開始回測</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>歷史紀錄</CardTitle>
            <CardDescription>
              瀏覽過去的回測結果。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/history">
              <Button variant="outline" className="w-full">
                查看紀錄
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>比較回測</CardTitle>
            <CardDescription>
              選擇兩次回測進行並排比較。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/compare">
              <Button variant="outline" className="w-full">
                開始比較
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
