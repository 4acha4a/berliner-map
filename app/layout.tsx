import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
const kanashSans = localFont({
  src: "./fonts/Kanash-SansFont.woff2",
  weight: "100 900",
  style: "normal",
  variable: "--font-kanash-sans",
  display: "swap",
});
export const metadata: Metadata = {
  title: "Berliner Map — Explore Berlin Through Time",
  icons: {
    icon: { url: "/data/berliner-map-logo-min.svg", type: "image/svg+xml" },
  },
  description:
    "Explore Berlin’s history through an approximate reconstruction of the Allied occupation sectors. Historical coverage is partial and boundaries are uncertain.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={kanashSans.variable}>
      <body>{children}</body>
    </html>
  );
}
