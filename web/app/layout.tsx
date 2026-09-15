import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "DataTrio — Analiz stüdyosu",
  description: "Kontrollü araçlarla finansal analiz çalışma alanı",
  robots: { index: false, follow: false },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
