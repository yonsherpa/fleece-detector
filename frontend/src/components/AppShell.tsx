import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../services/api";
import type { DatasetInfo } from "../types/api";
import { LeagueSwitcher } from "./LeagueSwitcher";
import { cx } from "./ui";

const NAV = [
  { to: "/", label: "Trade" },
  { to: "/moves", label: "Moves" },
  { to: "/rankings", label: "Rankings" },
  { to: "/league", label: "League" },
  { to: "/history", label: "History", soon: true },
];

function Logo() {
  return (
    <NavLink to="/" className="flex shrink-0 items-center gap-2">
      {/* Magnifying glass inspecting a tuft of fleece. Same artwork as public/favicon.svg. */}
      <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden>
        <rect width="32" height="32" rx="7" className="fill-ink-800" />
        <g fill="#E9EDF5">
          <circle cx="11.6" cy="15.2" r="2.3" />
          <circle cx="14" cy="13.2" r="2.7" />
          <circle cx="16.4" cy="15.2" r="2.3" />
          <rect x="11.6" y="14.4" width="4.8" height="3.1" />
        </g>
        <circle cx="14" cy="14.5" r="7.6" fill="none" stroke="#00CEB8" strokeWidth="2.4" />
        <path d="M19.6 20.1l5.2 5.2" stroke="#00CEB8" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <span className="hidden text-sm font-semibold tracking-tight text-ink-100 sm:inline">Fleece Detector</span>
    </NavLink>
  );
}

function updatedLabel(asOf: string): string {
  const date = new Date(asOf);
  if (Number.isNaN(date.getTime())) return "";
  return `updated ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

type ApiStatus = { state: "checking" } | { state: "online"; dataset: DatasetInfo } | { state: "offline" };

function useApiStatus() {
  const [status, setStatus] = useState<ApiStatus>({ state: "checking" });
  const check = () => {
    setStatus({ state: "checking" });
    api
      .health()
      .then((h) => setStatus({ state: "online", dataset: h.dataset }))
      .catch(() => setStatus({ state: "offline" }));
  };
  useEffect(check, []);
  return { status, retry: check };
}

function DataStatus({ status, retry }: ReturnType<typeof useApiStatus>) {
  if (status.state === "checking") return <span className="text-xs text-ink-500">Connecting…</span>;
  if (status.state === "offline")
    return (
      <button onClick={retry} className="flex items-center gap-1.5 text-xs text-flag-400 hover:underline">
        <span className="h-1.5 w-1.5 rounded-full bg-flag-400" /> API offline · retry
      </button>
    );
  const { dataset } = status;
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-400" title={dataset.description}>
      <span className="h-1.5 w-1.5 rounded-full bg-mint-500" />
      {dataset.is_sample ? "Sample data" : `Week ${dataset.week ?? "?"}`} · {updatedLabel(dataset.as_of)}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const apiStatus = useApiStatus();
  const sample = apiStatus.status.state === "online" && apiStatus.status.dataset.is_sample;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-900">
        <div className="mx-auto flex h-12 max-w-6xl items-center gap-2 px-4 sm:px-6">
          <Logo />
          <span className="text-ink-600" aria-hidden>
            /
          </span>
          <LeagueSwitcher />
          <div className="ml-auto hidden sm:block">
            <DataStatus {...apiStatus} />
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-5 overflow-x-auto overflow-y-hidden no-scrollbar px-4 sm:px-6" aria-label="Main">
          {NAV.map(({ to, label, soon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cx(
                  "-mb-px flex shrink-0 items-center gap-1.5 border-b-2 py-2.5 text-sm transition-colors",
                  isActive ? "border-mint-500 text-ink-100" : "border-transparent text-ink-400 hover:text-ink-100",
                )
              }
            >
              {label}
              {soon && <span className="text-[10px] text-ink-500">soon</span>}
            </NavLink>
          ))}
        </nav>
        {sample && (
          <div className="border-t border-amber-400/20 bg-amber-400/[0.06] px-4 py-1.5 text-center text-xs text-amber-400">
            Players and projections are fictional sample data, not real NFL stats.
          </div>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">{children}</main>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 px-4 py-4 text-xs text-ink-500 sm:px-6">
        <DataStatus {...apiStatus} />
        <span>Projections via Sleeper · schedule via nflverse · grades are estimates, not guarantees</span>
      </footer>
    </div>
  );
}
