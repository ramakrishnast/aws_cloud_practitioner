import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { DIFFICULTIES, DifficultyChip, ErrorBox, Explanation, Spinner, title } from "../ui.jsx";
import QuestionEditor from "./QuestionEditor.jsx";

function Generator({ exams, health, onDone }) {
  const [exam, setExam] = useState("clf-c02");
  const [domain, setDomain] = useState(1);
  const [difficulty, setDifficulty] = useState("medium");
  const [count, setCount] = useState(5);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const e = exams.find((x) => x.key === exam);

  useEffect(() => () => clearInterval(timer.current), []);

  function poll(id) {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const j = await api.get(`/api/generate/jobs/${id}`);
        setJob(j);
        if (j.status !== "running") {
          clearInterval(timer.current);
          onDone();
        }
      } catch (err) {
        clearInterval(timer.current);
        setError(err);
      }
    }, 2000);
  }

  async function run(seed = false) {
    setError(null);
    try {
      const j = seed
        ? await api.post("/api/generate/seed", { exam, total: 100 })
        : await api.post("/api/generate", { exam, domain_id: Number(domain), difficulty, count: Number(count) });
      setJob(j);
      poll(j.id);
    } catch (err) {
      setError(err);
    }
  }

  if (!health?.generator_enabled) {
    return (
      <div className="card space-y-2">
        <h2 className="font-semibold">AI question generator</h2>
        <p className="text-sm">
          The generator writes original questions with Claude, checks each one with a second review pass, and saves them here for your
          approval. To turn it on, add your key to <code>.env</code>:
        </p>
        <pre className="overflow-x-auto rounded-md bg-slate-100 p-3 text-xs dark:bg-[#222220]">ANTHROPIC_API_KEY=sk-ant-…</pre>
        <p className="text-xs muted">Then restart the app. Everything else works offline.</p>
      </div>
    );
  }

  const running = job?.status === "running";
  return (
    <div className="card space-y-4">
      <div>
        <h2 className="font-semibold">AI question generator</h2>
        <p className="text-xs muted">Model: {health.model}. Questions follow the exam guide's task statements and land below as pending review.</p>
      </div>
      <ErrorBox error={error} />
      <div className="grid gap-3 sm:grid-cols-5">
        <select className="input" value={exam} onChange={(ev) => { setExam(ev.target.value); setDomain(1); }} aria-label="Exam">
          {exams.map((x) => <option key={x.key} value={x.key}>{x.code}</option>)}
        </select>
        <select className="input sm:col-span-2" value={domain} onChange={(ev) => setDomain(ev.target.value)} aria-label="Domain">
          {e?.domains.map((d) => <option key={d.id} value={d.id}>{d.id}. {d.name}</option>)}
        </select>
        <select className="input" value={difficulty} onChange={(ev) => setDifficulty(ev.target.value)} aria-label="Difficulty">
          {DIFFICULTIES.map((d) => <option key={d} value={d}>{title(d)}</option>)}
        </select>
        <input type="number" min={1} max={25} className="input" value={count} onChange={(ev) => setCount(ev.target.value)} aria-label="Count" />
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" disabled={running} onClick={() => run(false)}>Generate {count}</button>
        <button className="btn-secondary" disabled={running} onClick={() => run(true)} title="About 100 questions spread by domain weight and difficulty">
          Seed starter set for {e?.code} (~100)
        </button>
      </div>
      {job && (
        <div className="rounded-md bg-slate-50 p-3 text-xs dark:bg-[#222220]">
          <div className="mb-1 font-semibold">
            Job #{job.id}: {job.status}
            {running && <span className="ml-2 inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand-500 border-t-transparent align-middle" />}
          </div>
          <ul className="max-h-40 space-y-0.5 overflow-y-auto">
            {job.log.slice(-12).map((l, i) => <li key={i}>{l}</li>)}
          </ul>
          {job.results.length > 0 && (
            <p className="mt-2">
              Accepted {job.results.reduce((s, r) => s + r.accepted, 0)} · fixed by reviewer {job.results.reduce((s, r) => s + r.fixed_by_verifier, 0)} ·
              discarded {job.results.reduce((s, r) => s + r.discarded.length, 0)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PendingCard({ q, onAction, onEdit }) {
  return (
    <article className="card space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold">#{q.id}</span>
        <DifficultyChip value={q.difficulty} />
        <span className="muted">D{q.domain_id}: {q.domain_name}</span>
        <span className="muted">{q.question_type === "multiple" ? "Multiple response" : "Single answer"}</span>
        <code className="muted">{q.source_file}</code>
      </div>
      <p className="whitespace-pre-wrap">{q.text}</p>
      <ul className="space-y-1">
        {q.options.map((o) => (
          <li key={o.letter} className={`flex gap-2 rounded-md border px-3 py-1.5 text-sm ${q.correct.includes(o.letter) ? "border-good bg-good/10" : "border-slate-200 dark:border-[#2c2c2a]"}`}>
            <span className="font-semibold">{o.letter}.</span>
            <span className="flex-1">{o.text}</span>
            {q.correct.includes(o.letter) && <span className="text-xs font-semibold text-[#087a08] dark:text-[#5fd35f]">✓ Correct</span>}
          </li>
        ))}
      </ul>
      <details className="rounded-md bg-slate-50 p-3 dark:bg-[#222220]">
        <summary className="cursor-pointer text-sm font-medium">Explanation and reference</summary>
        <div className="mt-2"><Explanation text={q.explanation} /></div>
        {q.reference_url && <a className="mt-2 inline-block text-sm" href={q.reference_url} target="_blank" rel="noreferrer">{q.reference_url} ↗</a>}
      </details>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary py-1.5" onClick={() => onAction(q, "active")}>✓ Approve</button>
        <button className="btn-secondary py-1.5" onClick={() => onEdit(q)}>Edit</button>
        <button className="btn-ghost py-1.5 text-critical" onClick={() => onAction(q, "rejected")}>✕ Reject</button>
      </div>
    </article>
  );
}

export default function Review() {
  const [exams, setExams] = useState([]);
  const [health, setHealth] = useState(null);
  const [exam, setExam] = useState("");
  const [list, setList] = useState(null);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    const p = new URLSearchParams({ status: "pending", page_size: "50" });
    if (exam) p.set("exam", exam);
    api.get(`/api/questions?${p}`).then(setList).catch(setError);
    api.get("/api/exams").then((d) => setExams(d.exams)).catch(setError);
  }, [exam]);

  useEffect(() => {
    api.get("/api/health").then(setHealth).catch(setError);
  }, []);
  useEffect(load, [load]);

  async function act(q, status) {
    try {
      await api.post(`/api/questions/${q.id}/status`, { status });
      setList((l) => ({ ...l, total: l.total - 1, items: l.items.filter((x) => x.id !== q.id) }));
    } catch (e) {
      setError(e);
    }
  }

  async function approveAll() {
    if (!window.confirm(`Approve all ${list.items.length} questions shown?`)) return;
    for (const q of list.items) await act(q, "active");
    load();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Review &amp; generate</h1>
        <p className="text-sm muted">Generated questions stay out of tests until you approve them. Edits are written back to the CSV.</p>
      </div>
      <ErrorBox error={error} />
      <Generator exams={exams} health={health} onDone={load} />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Pending review {list && <span className="muted">({list.total})</span>}</h2>
          <div className="flex gap-2">
            <select className="input w-auto" value={exam} onChange={(e) => setExam(e.target.value)} aria-label="Exam filter">
              <option value="">All exams</option>
              {exams.map((e) => <option key={e.key} value={e.key}>{e.code}</option>)}
            </select>
            {list?.items.length > 0 && <button className="btn-secondary" onClick={approveAll}>Approve all shown</button>}
          </div>
        </div>
        {!list ? (
          <Spinner />
        ) : list.items.length === 0 ? (
          <p className="card text-sm muted">Nothing waiting for review.</p>
        ) : (
          list.items.map((q) => <PendingCard key={q.id} q={q} onAction={act} onEdit={setEditing} />)
        )}
      </section>

      {editing && (
        <QuestionEditor
          question={editing}
          domains={exams.find((e) => e.key === editing.exam)?.domains || []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}
