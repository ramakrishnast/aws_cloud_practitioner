import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { DIFFICULTIES, ErrorBox, MODE_LABELS, Spinner, title } from "../ui.jsx";

const MODE_HELP = {
  full: "Exact question count and time limit, questions drawn by domain weight. No answers until the end.",
  practice: "Untimed or a custom timer. See the correct answer and explanation after each question.",
  drill: "10–25 questions from one domain or one AWS service.",
  weak: "Retest questions you got wrong or flagged. Wrong answers come back sooner (spaced repetition).",
};

export default function StartTest() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [exams, setExams] = useState(null);
  const [exam, setExam] = useState(params.get("exam") || "clf-c02");
  const [detail, setDetail] = useState(null);
  const [mode, setMode] = useState(params.get("mode") || "full");
  const [difficulty, setDifficulty] = useState("mixed");
  const [count, setCount] = useState(20);
  const [timed, setTimed] = useState(false);
  const [minutes, setMinutes] = useState(30);
  const [feedback, setFeedback] = useState("immediate");
  const [drillBy, setDrillBy] = useState("domain");
  const [domainId, setDomainId] = useState(1);
  const [service, setService] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/exams").then((d) => setExams(d.exams)).catch(setError);
  }, []);
  useEffect(() => {
    setDetail(null);
    api.get(`/api/exams/${exam}`).then((d) => {
      setDetail(d);
      setService(d.services?.[0]?.name || "");
    }).catch(setError);
  }, [exam]);
  useEffect(() => {
    if (mode === "drill") setCount((c) => Math.min(Math.max(c, 10), 25));
  }, [mode]);

  const e = useMemo(() => exams?.find((x) => x.key === exam), [exams, exam]);
  if (!exams) return error ? <ErrorBox error={error} /> : <Spinner />;

  async function start() {
    setBusy(true);
    setError(null);
    const body = { exam, mode, difficulty: mode === "weak" ? "mixed" : difficulty };
    if (mode !== "full") {
      body.count = Number(count);
      body.feedback = feedback;
      if (timed) body.time_limit_min = Number(minutes);
    }
    if (mode === "drill") {
      if (drillBy === "domain") body.domain_id = Number(domainId);
      else body.service = service;
    }
    try {
      const a = await api.post("/api/attempts", body);
      nav(`/test/${a.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const avail = mode === "drill" && drillBy === "domain"
    ? detail?.domains.find((d) => d.id === Number(domainId))?.active
    : mode === "drill"
      ? detail?.services?.find((s) => s.name === service)?.count
      : difficulty === "mixed" ? e?.active_questions : e?.by_difficulty?.[difficulty];

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-semibold">Start a test</h1>
      <ErrorBox error={error} />

      <section className="card space-y-3">
        <span className="label">1 · Exam</span>
        <div className="grid gap-2 sm:grid-cols-3">
          {exams.map((x) => (
            <button
              key={x.key}
              onClick={() => setExam(x.key)}
              className={`rounded-lg border p-3 text-left transition ${
                exam === x.key ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-[#1c2a3d]" : "border-slate-200 hover:border-slate-400 dark:border-[#3a3a37]"
              }`}
            >
              <div className="text-xs font-semibold text-brand-600 dark:text-[#86b6ef]">{x.code}</div>
              <div className="text-sm font-medium">{x.short_name}</div>
              <div className="text-xs muted">{x.active_questions} questions available</div>
            </button>
          ))}
        </div>
      </section>

      <section className="card space-y-3">
        <span className="label">2 · Mode</span>
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(MODE_LABELS).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setMode(k)}
              disabled={k === "weak" && !e?.review.total}
              className={`rounded-lg border p-3 text-left transition disabled:opacity-40 ${
                mode === k ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-[#1c2a3d]" : "border-slate-200 hover:border-slate-400 dark:border-[#3a3a37]"
              }`}
            >
              <div className="text-sm font-semibold">{label}</div>
              <div className="text-xs muted">{MODE_HELP[k]}</div>
            </button>
          ))}
        </div>
      </section>

      {mode !== "weak" && (
        <section className="card space-y-3">
          <span className="label">3 · Difficulty</span>
          <div className="flex flex-wrap gap-2">
            {[...DIFFICULTIES, "mixed"].map((d) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`rounded-full border px-4 py-1.5 text-sm transition ${
                  difficulty === d ? "border-brand-500 bg-brand-500 text-white" : "border-slate-300 hover:border-slate-500 dark:border-[#3a3a37]"
                }`}
              >
                {d === "mixed" ? "Mixed (realistic blend)" : title(d)}
                {d !== "mixed" && e ? <span className="ml-1 opacity-70">· {e.by_difficulty[d]}</span> : null}
              </button>
            ))}
          </div>
          <p className="text-xs muted">
            Easy: definitions and single-service recall · Medium: right service for a stated need · Hard: multi-service tradeoffs ·
            Tough: long professional scenarios and multiple-response.
          </p>
        </section>
      )}

      <section className="card space-y-4">
        <span className="label">{mode === "weak" ? "3" : "4"} · Settings</span>
        {mode === "full" && e && (
          <ul className="list-inside list-disc text-sm">
            <li>{e.question_count} questions, {e.time_limit_minutes} minutes; the test submits itself when time runs out.</li>
            <li>Questions are drawn by domain weight: {e.domains.map((d) => `${d.weight}%`).join(" / ")}.</li>
            <li>Flag questions and use the navigator; a review screen appears before you submit.</li>
            <li>Shortcuts: 1–6 select · N next · P previous · F flag.</li>
          </ul>
        )}
        {mode === "drill" && detail && (
          <div className="space-y-3">
            <div className="flex gap-2">
              {["domain", "service"].map((b) => (
                <button key={b} className={drillBy === b ? "btn-primary" : "btn-secondary"} onClick={() => setDrillBy(b)}>
                  By {b === "domain" ? "domain" : "AWS service"}
                </button>
              ))}
            </div>
            {drillBy === "domain" ? (
              <select className="input" value={domainId} onChange={(ev) => setDomainId(ev.target.value)}>
                {detail.domains.map((d) => (
                  <option key={d.id} value={d.id}>
                    Domain {d.id}: {d.name} ({d.active})
                  </option>
                ))}
              </select>
            ) : (
              <select className="input" value={service} onChange={(ev) => setService(ev.target.value)}>
                {(detail.services || []).map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} ({s.count})
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
        {mode !== "full" && (
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="count">Questions</label>
              <input
                id="count"
                type="number"
                className="input"
                min={mode === "drill" ? 10 : 1}
                max={mode === "drill" ? 25 : 150}
                value={count}
                onChange={(ev) => setCount(ev.target.value)}
              />
            </div>
            <div>
              <span className="label">Timer</span>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={timed} onChange={(ev) => setTimed(ev.target.checked)} /> Timed
                </label>
                {timed && (
                  <input type="number" min={1} className="input w-24" value={minutes} onChange={(ev) => setMinutes(ev.target.value)} aria-label="Minutes" />
                )}
                {timed && <span className="text-sm muted">min</span>}
              </div>
            </div>
            <div>
              <span className="label">Answers</span>
              <select className="input" value={feedback} onChange={(ev) => setFeedback(ev.target.value)}>
                <option value="immediate">After each question</option>
                <option value="end">At the end</option>
              </select>
            </div>
          </div>
        )}
        {avail != null && mode !== "weak" && (
          <p className="text-xs muted">{avail} matching question{avail === 1 ? "" : "s"} in the bank.</p>
        )}
      </section>

      <div className="flex justify-end">
        <button className="btn-primary px-6 py-2.5 text-base" disabled={busy} onClick={start}>
          {busy ? "Starting…" : "Start test"}
        </button>
      </div>
    </div>
  );
}
