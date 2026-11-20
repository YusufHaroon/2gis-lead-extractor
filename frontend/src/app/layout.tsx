import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Business Lead Extractor",
  description: "Search businesses by category and location and export to Excel.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
