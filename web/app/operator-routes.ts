export type SectionKey = "dashboard" | "setup" | "bookkeeping" | "banking" | "employment" | "budget_forecast" | "reports" | "year_end";

export const sectionOptions: Array<{ key: SectionKey; label: string; detail: string; href: string }> = [
  { key: "dashboard", label: "Dashboard", detail: "Company queues, summaries, and next actions.", href: "/" },
  { key: "setup", label: "Setup", detail: "Companies, users, access, and reference data.", href: "/setup" },
  { key: "bookkeeping", label: "Bookkeeping", detail: "Periods, journals, AI drafting, ledger review, and source documents.", href: "/bookkeeping" },
  { key: "banking", label: "Banking & BAS", detail: "Imports, reconciliation, BAS preparation, and export.", href: "/banking" },
  { key: "employment", label: "Employment", detail: "Worker records, work-rights reviews, leave support, and report packs.", href: "/employment" },
  { key: "budget_forecast", label: "Budget & Forecast", detail: "Monthly P&L budgets, future income and expenses, scenarios, and projected year-end profit.", href: "/budget-forecast" },
  { key: "reports", label: "Reports", detail: "Six core statements with browser, CSV, and PDF outputs.", href: "/reports" },
  { key: "year_end", label: "Year-end", detail: "Fixed assets, depreciation runs, and tax workpapers.", href: "/year-end" },
];
