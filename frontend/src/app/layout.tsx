import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Urban Optimization Benchmark",
  description: "Classical vs Hybrid Quantum Urban Optimization Benchmarks"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
