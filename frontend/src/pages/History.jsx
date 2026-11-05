import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { DifficultyChip, ErrorBox, MODE_LABELS, PassBadge, Spinner, chartColors, fmtDate, fmtDuration, useTheme } from "../ui.jsx";

function TrendTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow dark:border-[#3a3a37] dark:bg-[#222220]">
      <div className="font-semibold">{fmtDate(d.date)}</div>
      <div>{MODE_LABELS[d.mode]}</div>
      <div>Estimated score {d.scaled_score} · raw {d.raw_pct}%</div>
    </div>
  );
}

function Trend({ points, passing }) {
  const [dark] = useTheme();
  const c = chartColors(dark);
  if (points.length === 0) return <p className="py-10 text-center text-sm muted">No completed tests for this exam yet.</p>;
  const data = points.map((p, i) => ({ ...p, n: i + 1 }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 12, right: 16, bottom: 0, left: -12 }}>
        <CartesianGrid vertical={false} stroke={c.grid} />
        <XAxis dataKey="n" tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={{ stroke: c.grid }} allowDecimals={false} />
        <YAxis domain={[100, 1000]} ticks={[100, 400, 700, 1000]} tick={{ fill: c.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
        <ReferenceLine y={passing} stroke={c.ref} strokeDasharray="4 4" label={{ value: `Pass ${passing}`, position: "insideTopLeft", fill: c.axis, fontSize: 11 }} />
        <Tooltip content={<TrendTooltip />} cursor={{ stroke: c.axis, strokeDasharray: "2 2" }} />
        <Line
          type="linear"
          dataKey="scaled_score"
          stroke={c.series}
          strokeWidth={2}
          dot={{ r: 4, fill: c.series, stroke: c.surface, strokeWidth: 2 }}
          activeDot={{ r: 6, stroke: c.surface, strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function History() {
  const [rows, setRows] = useState(null);
  const [trend, setTrend] = useState(null);
  const [exams, setExams] = useState([]);
  const [exam, setExam] = useState("all");
  const [fullOnly, setFullOnly] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    Promise.all([api.get("/api/attempts"), api.get("/api/stats/trend"), api.get("/api/exams")])
      .then(([a, t, e]) => {
        setRows(a);
        setTrend(t);
        setExams(e.exams);
      })
      .catch(setError);
  }
  useEffect(load, []);

  const trendExam = exam === "all" ? exams[0]?.key : exam;
  const points = useMemo(() => (trend?.[trendExam] || []).filter((p) => !fullOnly || p.mode === "full"), [trend, trendExam, fullOnly]);
  const shown = (rows || []).filter((r) => exam === "all" || r.exam === exam);

  async function remove(id) {
    if (!window.confirm("Delete this attempt from your history?")) return;
    await api.del(`/api/attempts/${id}`);
    load();
  }

  if (error) return <ErrorBox error={error} />;
  if (!rows) return <Spinner />;
  const passing = exams.find((e) => e.key === trendExam)?.passing_score || 700;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold">History</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input w-auto" value={exam} onChange={(e) => setExam(e.target.value)} aria-label="Exam filter">
            <option value="all">All exams</option>
            {exams.map((e) => (
              <option key={e.key} value={e.key}>{e.code}</option>
            ))}
          </select>
        </div>
      </div>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-semibold">Score trend · {exams.find((e) => e.key === trendExam)?.code}</h2>
            <p className="text-xs muted">Estimated scaled score per completed test, oldest to newest</p>
          </div>
          <div className="flex items-center gap-3">
            {exam === "all" && (
              <select className="input w-auto py-1" value={trendExam} onChange={(e) => setExam(e.target.value)} aria-label="Trend exam">
                {exams.map((e) => <option key={e.key} value={e.key}>{e.code}</option>)}
              </select>
            )}
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={fullOnly} onChange={(e) => setFullOnly(e.target.checked)} /> Full simulations only
            </label>
          </div>
        </div>
        <Trend points={points} passing={passing} />
      </section>

      <section className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide muted dark:bg-[#222220]">
            <tr>
              <th className="px-4 py-2 font-medium">Date</th>
              <th className="px-4 py-2 font-medium">Exam</th>
              <th className="px-4 py-2 font-medium">Mode</th>
              <th className="px-4 py-2 font-medium">Difficulty</th>
              <th className="px-4 py-2 text-right font-medium">Score</th>
              <th className="px-4 py-2 text-right font-medium">Raw</th>
              <th className="px-4 py-2 text-right font-medium">Time</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center muted">No tests yet. <Link to="/start">Start one</Link>.</td></tr>
            )}
            {shown.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 dark:border-[#2c2c2a]">
                <td className="px-4 py-2">{fmtDate(r.submitted_at || r.started_at)}</td>
                <td className="px-4 py-2 font-medium">{r.exam_code}</td>
                <td className="px-4 py-2">
                  {MODE_LABELS[r.mode]}
                  {r.domain_name && <span className="muted"> · D{r.domain_id}</span>}
                  {r.service && <span className="muted"> · {r.service}</span>}
                </td>
                <td className="px-4 py-2"><DifficultyChip value={r.difficulty} /></td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {r.status === "submitted" ? (
                    <span className="inline-flex items-center gap-2">
                      {r.scaled_score} {r.mode === "full" && <PassBadge passed={r.passed} />}
                    </span>
                  ) : (
                    <span className="muted">in progress</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{r.raw_pct != null ? `${r.raw_pct}%` : "–"}</td>
                <td className="px-4 py-2 text-right tabular-nums">{fmtDuration(r.duration_sec)}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right">
                  {r.status === "submitted" ? (
                    <Link to={`/results/${r.id}`}>Results</Link>
                  ) : (
                    <Link to={`/test/${r.id}`}>Resume</Link>
                  )}
                  <button className="ml-3 text-xs muted hover:text-critical" onClick={() => remove(r.id)} aria-label="Delete attempt">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
