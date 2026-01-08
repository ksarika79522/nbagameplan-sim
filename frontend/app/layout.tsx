import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NBA Team Gameplan Simulator",
  description: "Generate data-driven scouting reports for NBA matchups",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

