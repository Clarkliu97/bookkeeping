import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import { getServerApiBaseUrl } from "./api-base-url-server";
import { ThemeToggle } from "./theme-toggle";
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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(() => { try { const saved = localStorage.getItem("bookkeeping-tax-theme"); const theme = saved === "dark" || saved === "light" ? saved : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); document.documentElement.dataset.theme = theme; } catch { document.documentElement.dataset.theme = "light"; } })();`,
          }}
        />
      </head>
      <body className={`${sansFont.variable} ${monoFont.variable}`}>
        <header className="app-header">
          <nav className="app-nav">
            <Link className="app-brand" href="/">
              <span className="app-brand-mark" aria-hidden="true">BT</span>
              <span className="app-brand-copy">
                <strong>Bookkeeping Tax</strong>
                <small>Operator console</small>
              </span>
            </Link>
            <div className="app-nav-links">
              <Link href="/">Workspace</Link>
              <Link href="/operations">Operations</Link>
              <Link href="/workbench">API workbench</Link>
              <a href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer">API docs</a>
            </div>
            <ThemeToggle />
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
