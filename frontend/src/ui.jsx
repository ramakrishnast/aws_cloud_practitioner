import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

export const DIFFICULTIES = ["easy", "medium", "hard", "tough"];
export const MODE_LABELS = { full: "Full simulation", practice: "Practice", drill: "Domain drill", weak: "Weak-area review" };

export function title(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

export function fmtDuration(sec) {
  if (sec == null) return "–";
  if (sec > 0 && sec < 1) return "<1s";
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

export function fmtClock(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function fmtDate(iso) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

// One shared theme state: every component using useTheme() (charts included)
// re-renders when the theme is toggled anywhere.
const themeListeners = new Set();

function setDarkMode(dark) {
  document.documentElement.classList.toggle("dark", dark);
  try {
    localStorage.setItem("cc-theme", dark ? "dark" : "light");
  } catch {
    /* storage unavailable */
  }
  themeListeners.forEach((fn) => fn(dark));
}

export function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    themeListeners.add(setDark);
    return () => themeListeners.delete(setDark);
  }, []);
  return [dark, setDarkMode];
}

/** Chart colors per theme (reference palette, validated for both surfaces). */
export function chartColors(dark) {
  return dark
    ? { series: "#3987e5", grid: "#2c2c2a", axis: "#a3a29b", text: "#f0efec", ref: "#c3c2b7", surface: "#1a1a19" }
    : { series: "#2a78d6", grid: "#e7e6e2", axis: "#52514e", text: "#0b0b0b", ref: "#52514e", surface: "#fcfcfb" };
}

export function ThemeToggle({ className = "" }) {
  const [dark, setDark] = useTheme();
  return (
    <button
      type="button"
      className={`btn-ghost px-2 ${className}`}
      onClick={() => setDark(!dark)}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
    >
      {dark ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}

const NAV = [
  ["/", "Dashboard"],
  ["/start", "Start a test"],
  ["/history", "History"],
  ["/bank", "Question bank"],
  ["/review", "Review & generate"],
];

export function Layout({ children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-[#2c2c2a] dark:bg-[#1a1a19]/90">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-ink-900 no-underline hover:no-underline dark:text-[#f0efec]">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 17h11a3.5 3.5 0 0 0 .4-7A5 5 0 0 0 8 8.6 4 4 0 0 0 6 17z" /></svg>
            </span>
            CloudCert Lab
          </NavLink>
          <nav className="ml-4 hidden flex-1 gap-1 md:flex">
            {NAV.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm no-underline hover:no-underline ${
                    isActive
                      ? "bg-brand-50 font-semibold text-brand-700 dark:bg-[#1c2a3d] dark:text-[#86b6ef]"
                      : "text-slate-600 hover:bg-slate-100 dark:text-[#c3c2b7] dark:hover:bg-[#2c2c2a]"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            <button className="btn-ghost px-2 md:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
              ☰
            </button>
          </div>
        </div>
        {open && (
          <nav className="flex flex-col gap-1 border-t border-slate-200 px-4 py-2 md:hidden dark:border-[#2c2c2a]">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)} className="rounded px-2 py-1.5 text-sm">
                {label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-[#2a1515] dark:text-red-200">
      {String(error.message || error)}
    </div>
  );
}

export function DifficultyChip({ value }) {
  const cls = {
    easy: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
    medium: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
    hard: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
    tough: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
    mixed: "bg-slate-100 text-slate-700 dark:bg-[#2c2c2a] dark:text-[#c3c2b7]",
  }[value] || "bg-slate-100 text-slate-700";
  return <span className={`chip ${cls}`}>{title(value)}</span>;
}

export function PassBadge({ passed, large = false }) {
  const size = large ? "px-4 py-1.5 text-base" : "px-2.5 py-0.5 text-xs";
  return passed ? (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-good/15 font-semibold text-[#087a08] dark:text-[#5fd35f] ${size}`}>
      <span aria-hidden>✓</span> Pass
    </span>
  ) : (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-critical/15 font-semibold text-[#b02d2d] dark:text-[#f08a8a] ${size}`}>
      <span aria-hidden>✕</span> Fail
    </span>
  );
}

export function Modal({ open, onClose, title: heading, children, wide = false }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 sm:items-center" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={heading}
        className={`card w-full ${wide ? "max-w-4xl" : "max-w-lg"} my-8`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold">{heading}</h2>
          <button className="btn-ghost px-2" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Explanation({ text }) {
  return <div className="whitespace-pre-wrap text-sm leading-relaxed">{text}</div>;
}
