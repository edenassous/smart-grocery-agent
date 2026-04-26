import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "סל הירקות הזול",
  description: "סוכן AI שמוצא את סל הירקות הזול ביותר",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
