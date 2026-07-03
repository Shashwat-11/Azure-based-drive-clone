import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Drive — Cloud Storage",
  description: "Production-grade cloud storage platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
