import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, MODE_LABELS, Spinner, fmtDate } from "../ui.jsx";

const READINESS_STYLE = {
  ready: { cls: "bg-good/15 text-[#087a08] dark:text-[#5fd35f]", icon: "✓" },
  almost: { cls: "bg-warn/20 text-[#8a5d00] dark:text-[#fac85a]", icon: "◐" },
  developing: { cls: "bg-[#ec835a]/20 text-[#a3461f] dark:text-[#f2a585]", icon: "▲" },
  not_ready: { cls: "bg-critical/15 text-[#b02d2d] dark:text-[#f08a8a]", icon: "✕" },
  insufficient: { cls: "bg-slate-100 text-slate-600 dark:bg-[#2c2c2a] dark:text-[#c3c2b7]", icon: "…" },
};

function Readiness({ r }) {
  const st = READINESS_STYLE[r.status] || READINESS_STYLE.insufficient;
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-[#2c2c2a]">
      <div className="flex items-center justify-between gap-2">
        <span className="label mb-0">Readiness</span>
        <span className={`chip ${st.cls}`}>
          <span aria-hidden>{st.icon}</span> {r.label}
        </span>
      </div>
      <p className="mt-2 text-sm muted">{r.message}</p>
      {r.scores.length > 0 && (
        <p className="mt-1 text-xs muted">
          Last {r.scores.length} full simulation{r.scores.length > 1 ? "s" : ""}: {r.scores.join(", ")}
          {r.average != null && ` · average ${r.average}`} · pass {r.passing_score}
        </p>
      )}
    </div>
  );
}

function ExamCard({ e }) {
  const empty = e.active_questions === 0;
  return (
    <div className="card flex flex-col gap-4">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-xs font-semibold tracking-wide text-brand-600 dark:text-[#86b6ef]">{e.code}</div>
            <h2 className="text-lg font-semibold leading-snug">{e.name}</h2>
          </div>
        </div>
        <p className="mt-1 text-sm muted">
          {e.question_count} questions · {e.time_limit_minutes} min · pass {e.passing_score}/1000
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-slate-50 p-2 dark:bg-[#222220]">
          <div className="text-xl font-semibold">{e.active_questions}</div>
          <div className="text-xs muted">questions</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-2 dark:bg-[#222220]">
          <div className="text-xl font-semibold">{e.pending_questions}</div>
          <div className="text-xs muted">to review</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-2 dark:bg-[#222220]">
          <div className="text-xl font-semibold">{e.review.due}</div>
          <div className="text-xs muted">due retests</div>
        </div>
      </div>
      <Readiness r={e.readiness} />
      {empty ? (
        <p className="text-sm muted">
          No active questions yet. Drop a CSV into <code>question_bank/{e.key}/</code> or approve generated ones in{" "}
          <Link to="/review">Review</Link>.
        </p>
      ) : (
        <div className="mt-auto grid grid-cols-2 gap-2">
          <Link to={`/start?exam=${e.key}&mode=full`} className="btn-primary col-span-2 no-underline hover:no-underline">
            Full exam simulation
          </Link>
          <Link to={`/start?exam=${e.key}&mode=practice`} className="btn-secondary no-underline hover:no-underline">
            Practice
          </Link>
          <Link to={`/start?exam=${e.key}&mode=drill`} className="btn-secondary no-underline hover:no-underline">
            Domain drill
          </Link>
          <Link
            to={`/start?exam=${e.key}&mode=weak`}
            className={`btn-secondary col-span-2 no-underline hover:no-underline ${e.review.total ? "" : "pointer-events-none opacity-50"}`}
            aria-disabled={!e.review.total}
          >
            Weak-area review {e.review.total ? `(${e.review.total} tracked)` : ""}
          </Link>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.get("/api/exams").then(setData).catch(setError);
  }, []);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Spinner />;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Your exams</h1>
        <p className="muted text-sm">Pick an exam to start a timed simulation, practice with instant feedback, or drill a weak domain.</p>
      </div>
      {data.in_progress.length > 0 && (
        <div className="card border-brand-500/40">
          <h2 className="mb-2 font-semibold">Tests in progress</h2>
          <ul className="space-y-1 text-sm">
            {data.in_progress.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {a.exam.toUpperCase()} · {MODE_LABELS[a.mode]} · {a.total} questions · started {fmtDate(a.started_at)}
                </span>
                <Link to={`/test/${a.id}`} className="btn-secondary py-1 no-underline hover:no-underline">
                  Resume
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {data.exams.map((e) => (
          <ExamCard key={e.key} e={e} />
        ))}
      </div>
      <p className="text-xs muted">
        Scores are estimates. AWS reports scaled scores from 100 to 1000 and does not publish how raw answers map to them.
      </p>
    </div>
  );
}
