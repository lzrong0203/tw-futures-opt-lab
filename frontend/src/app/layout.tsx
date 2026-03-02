import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TW Futures Options Lab",
  description: "Backtest dashboard for TMF + weekly PUT protection strategy",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <nav className="border-b px-6 py-3 flex items-center gap-6 text-sm">
          <Link href="/" className="font-bold text-lg">
            TW Futures Lab
          </Link>
          <Link href="/backtest/new" className="hover:underline">
            New Backtest
          </Link>
          <Link href="/history" className="hover:underline">
            History
          </Link>
        </nav>
        <main className="mx-auto max-w-6xl p-6">{children}</main>
      </body>
    </html>
  );
}
