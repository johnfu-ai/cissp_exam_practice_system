import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";
import { Providers } from "@/components/providers";
import type { Locale } from "@/lib/i18n/types";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CISSP Exam Practice",
  description: "CISSP exam preparation platform",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const uiLang = (await cookies()).get("ui_lang")?.value;
  const locale: Locale = uiLang === "zh" ? "zh" : "en";
  return (
    <html lang={locale} className={dmSans.variable}>
      <body className="font-sans antialiased">
        <Providers initialLocale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
