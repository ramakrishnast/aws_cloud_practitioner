import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import {
  DifficultyChip,
  ErrorBox,
  Explanation,
  MODE_LABELS,
  PassBadge,
  Spinner,
  chartColors,
  fmtDate,
  fmtDuration,
  title,
  useTheme,
} from "../ui.jsx";

function PctTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow dark:border-[#3a3a37] dark:bg-[#222220]">
      <div className="font-semibold">{d.full}</div>
      <div>{d.total ? `${d.correct} of ${d.total} correct (${d.pct}%)` : "No questions"}</div>
    </div>
  );
}

function PctBars({ data, height = 220 }) {
  const [dark] = useTheme();
  const c = chartColors(dark);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} stroke={c.grid} />
        <XAxis dataKey="name" tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.grid }} interval={0} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
        <Tooltip content={<PctTooltip />} cursor={{ fill: dark ? "#ffffff0d" : "#0000000a" }} />
        <Bar dataKey="pct" fill={c.series} radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function BreakdownTable({ rows }) {
  return (
    <table className="mt-3 w-full text-sm">
      <thead>
        <tr className="text-left text-xs muted">
          <th className="py-1 font-medium">Area</th>
          <th className="py-1 text-right font-medium">Correct</th>
          <th className="py-1 text-right font-medium">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.full} className="border-t border-slate-100 dark:border-[#2c2c2a]">
            <td className="py-1.5">{r.full}</td>
            <td className="py-1.5 text-right tabular-nums">{r.total ? `${r.correct}/${r.total}` : "–"}</td>
            <td className="py-1.5 text-right font-medium tabular-nums">{r.pct == null ? "–" : `${r.pct}%`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AnswerReview({ answers }) {
  const [filter, setFilter] = useState("all");
  const counts = {
    all: answers.length,
    incorrect: answers.filter((a) => !a.feedback?.is_correct).length,
    flagged: answers.filter((a) => a.flagged).length,
  };
  const shown = answers.filter((a) => filter === "all" || (filter === "incorrect" ? !a.feedback?.is_correct : a.flagged));
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Answer review</h2>
        <div className="flex gap-2">
          {Object.keys(counts).map((k) => (
            <button key={k} className={filter === k ? "btn-primary py-1" : "btn-secondary py-1"} onClick={() => setFilter(k)}>
              {title(k)} ({counts[k]})
            </button>
          ))}
        </div>
      </div>
      {shown.map((a) => {
        const fb = a.feedback || {};
        return (
          <article key={a.position} className="card space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold">Question {a.position + 1}</span>
              <span className={`chip ${fb.is_correct ? "bg-good/15 text-[#087a08] dark:text-[#5fd35f]" : "bg-critical/15 text-[#b02d2d] dark:text-[#f08a8a]"}`}>
                {fb.is_correct ? "✓ Correct" : a.selected.length ? "✕ Incorrect" : "✕ Unanswered"}
              </span>
              {a.flagged && <span className="chip bg-warn/20 text-[#8a5d00] dark:text-[#fac85a]">⚑ Flagged</span>}
              <DifficultyChip value={fb.difficulty} />
              <span className="muted">Domain {fb.domain_id}: {fb.domain_name}</span>
            </div>
            <p className="whitespace-pre-wrap">{a.question.text}</p>
            <ul className="space-y-1.5">
              {a.question.options.map((o) => {
                const mine = a.selected.includes(o.letter);
                const right = fb.correct?.includes(o.letter);
                return (
                  <li
                    key={o.letter}
                    className={`flex gap-2 rounded-md border px-3 py-2 text-sm ${
                      right ? "border-good bg-good/10" : mine ? "border-critical bg-critical/10" : "border-slate-200 dark:border-[#2c2c2a]"
                    }`}
                  >
                    <span className="font-semibold">{o.letter}.</span>
                    <span className="flex-1">{o.text}</span>
                    {mine && <span className="text-xs font-semibold">Your answer</span>}
                    {right && <span className="text-xs font-semibold text-[#087a08] dark:text-[#5fd35f]">✓ Correct</span>}
                  </li>
                );
              })}
            </ul>
            <div className="rounded-md bg-slate-50 p-3 dark:bg-[#222220]">
              <div className="mb-1 text-sm">
                <strong>Your answer:</strong> {a.selected.length ? a.selected.join(", ") : "none"} · <strong>Correct:</strong>{" "}
                {fb.correct?.join(", ")}
              </div>
              <Explanation text={fb.explanation} />
              {fb.reference_url && (
                <a className="mt-2 inline-block text-sm" href={fb.reference_url} target="_blank" rel="noreferrer">
                  AWS documentation ↗
                </a>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}

export default function Results() {
  const { id } = useParams();
  const [r, setR] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.get(`/api/attempts/${id}/results`).then(setR).catch(setError);
  }, [id]);
  if (error) return <ErrorBox error={error} />;
  if (!r) return <Spinner />;

  const domains = r.breakdown.by_domain.map((d) => ({ ...d, name: `D${d.id}`, full: `Domain ${d.id}: ${d.name}` }));
  const diffs = r.breakdown.by_difficulty.filter((d) => d.total).map((d) => ({ ...d, name: title(d.difficulty), full: title(d.difficulty) }));
  const isFull = r.mode === "full";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="text-xs font-semibold text-brand-600 dark:text-[#86b6ef]">{r.exam_code} · {MODE_LABELS[r.mode]}</div>
          <h1 className="text-2xl font-semibold">Results</h1>
          <p className="text-sm muted">{fmtDate(r.submitted_at)}{r.auto_submitted && " · submitted automatically when time ran out"}</p>
        </div>
        <div className="flex gap-2">
          <Link className="btn-secondary no-underline hover:no-underline" to={`/start?exam=${r.exam}&mode=${r.mode}`}>New test</Link>
          <Link className="btn-secondary no-underline hover:no-underline" to="/history">History</Link>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-4">
        <div className="card md:col-span-2">
          <div className="label">Estimated scaled score</div>
          <div className="flex items-center gap-4">
            <div className="text-5xl font-semibold tabular-nums">{r.scaled_score}</div>
            <div className="space-y-1">
              <PassBadge passed={r.passed} large />
              <div className="text-xs muted">Passing score {r.passing_score} / 1000</div>
            </div>
          </div>
          <div className="relative mt-4 h-2 rounded-full bg-slate-200 dark:bg-[#2c2c2a]">
            <div className={`h-2 rounded-full ${r.passed ? "bg-good" : "bg-critical"}`} style={{ width: `${((r.scaled_score - 100) / 900) * 100}%` }} />
            <div className="absolute -top-1 h-4 w-0.5 bg-ink-900 dark:bg-white" style={{ left: `${((r.passing_score - 100) / 900) * 100}%` }} title="Passing score" />
          </div>
          <p className="mt-3 text-xs muted">
            Estimate only. AWS uses scaled scoring (100–1000) and does not publish the conversion, and real exams include
            unscored questions.{!isFull && " Pass/fail is only meaningful for full simulations."}
          </p>
        </div>
        <div className="card">
          <div className="label">Raw score</div>
          <div className="text-3xl font-semibold tabular-nums">{r.raw_pct}%</div>
          <div className="text-sm muted">{r.correct_count} of {r.total} correct · {r.answered} answered</div>
        </div>
        <div className="card">
          <div className="label">Time</div>
          <div className="text-3xl font-semibold tabular-nums">{fmtDuration(r.duration_sec)}</div>
          <div className="text-sm muted">
            {r.avg_time_per_question_sec != null ? `${fmtDuration(r.avg_time_per_question_sec)} per question` : ""}
            {r.time_limit_sec ? ` · limit ${fmtDuration(r.time_limit_sec)}` : ""}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="font-semibold">Score by domain</h2>
          <p className="text-xs muted">Percent correct in each exam domain</p>
          <PctBars data={domains} />
          <BreakdownTable rows={domains} />
        </div>
        <div className="card">
          <h2 className="font-semibold">Score by difficulty</h2>
          <p className="text-xs muted">Percent correct at each difficulty level</p>
          <PctBars data={diffs} />
          <BreakdownTable rows={diffs} />
        </div>
      </section>

      <AnswerReview answers={r.answers} />
    </div>
  );
}
