import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import { getServerApiBaseUrl } from "./api-base-url-server";
import "./globals.css";


const sansFont = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});


export const metadata: Metadata = {
  title: "Bookkeeping Tax Support",
  description: "Internal bookkeeping and tax support system for Australian companies.",
};


export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const apiBaseUrl = await getServerApiBaseUrl();

  return (
    <html lang="en">
      <body className={`${sansFont.variable} ${monoFont.variable}`}>
        <header className="app-header">
          <nav className="app-nav">
            <Link href="/">Operator Workspace</Link>
            <Link href="/workbench">Workbench</Link>
            <Link href="/operations">Operations</Link>
            <a href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">
              Swagger
            </a>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
