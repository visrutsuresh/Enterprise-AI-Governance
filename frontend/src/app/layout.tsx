import type { Metadata } from "next";
import { array, cabinet, gsans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Governance",
  description: "Enterprise AI governance control tower",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${gsans.variable} ${cabinet.variable} ${array.variable} h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full">
        {children}
      </body>
    </html>
  );
}
