import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CISSP Exam Practice",
  description: "CISSP exam preparation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
