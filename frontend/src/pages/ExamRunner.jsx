import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { ErrorBox, Explanation, Modal, Spinner, ThemeToggle, fmtClock } from "../ui.jsx";

const LETTERS = "ABCDEF";

function Timer({ remaining, warn }) {
  const low = remaining != null && remaining <= 5 * 60;
  const mid = remaining != null && remaining <= 15 * 60;
  return (
    <div
      className={`flex items-center gap-2 rounded-md px-3 py-1 font-mono text-sm tabular-nums ${
        low ? "bg-critical text-white" : mid ? "bg-warn text-black" : "bg-white/10"
      } ${warn ? "animate-pulse" : ""}`}
      aria-live="polite"
      title="Time remaining"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2 2M9 2h6" /></svg>
      {remaining == null ? "Untimed" : fmtClock(remaining)}
    </div>
  );
}

function Navigator({ answers, current, onJump }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs muted">
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm bg-brand-500" /> Answered</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border border-slate-400" /> Unanswered</span>
        <span className="flex items-center gap-1"><span className="text-warn">⚑</span> Flagged</span>
      </div>
      <div className="grid grid-cols-8 gap-1.5 sm:grid-cols-10">
        {answers.map((a, i) => {
          const answered = a.selected.length > 0;
          return (
            <button
              key={i}
              onClick={() => onJump(i)}
              className={`relative h-9 rounded text-sm font-medium transition ${
                answered ? "bg-brand-500 text-white" : "border border-slate-300 dark:border-[#4a4a46]"
              } ${i === current ? "ring-2 ring-offset-1 ring-ink-900 dark:ring-white dark:ring-offset-[#1a1a19]" : ""}`}
              aria-label={`Question ${i + 1}${answered ? ", answered" : ", unanswered"}${a.flagged ? ", flagged" : ""}`}
            >
              {i + 1}
              {a.flagged && <span className="absolute -right-1 -top-1.5 text-xs text-warn">⚑</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ReviewScreen({ answers, onJump, onSubmit, onBack, submitting }) {
  const [filter, setFilter] = useState("all");
  const unanswered = answers.filter((a) => !a.selected.length).length;
  const flagged = answers.filter((a) => a.flagged).length;
  const shown = answers
    .map((a, i) => ({ a, i }))
    .filter(({ a }) => filter === "all" || (filter === "flagged" ? a.flagged : !a.selected.length));
  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 sm:p-8">
      <h1 className="text-xl font-semibold">Review your answers</h1>
      <p className="text-sm">
        {answers.length - unanswered} of {answers.length} answered · {unanswered} unanswered · {flagged} flagged.{" "}
        {unanswered > 0 && <strong>Unanswered questions are scored as incorrect.</strong>}
      </p>
      <div className="flex flex-wrap gap-2">
        {[["all", "All"], ["flagged", `Flagged (${flagged})`], ["incomplete", `Incomplete (${unanswered})`]].map(([k, l]) => (
          <button key={k} className={filter === k ? "btn-primary py-1" : "btn-secondary py-1"} onClick={() => setFilter(k)}>
            {l}
          </button>
        ))}
      </div>
      <div className="card divide-y divide-slate-100 p-0 dark:divide-[#2c2c2a]">
        {shown.length === 0 && <p className="p-4 text-sm muted">Nothing here.</p>}
        {shown.map(({ a, i }) => (
          <button key={i} onClick={() => onJump(i)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-[#222220]">
            <span className="w-8 shrink-0 font-semibold">{i + 1}</span>
            <span className="line-clamp-1 flex-1">{a.question.text}</span>
            {a.flagged && <span className="text-warn" title="Flagged">⚑</span>}
            <span className={`w-24 shrink-0 text-right text-xs ${a.selected.length ? "muted" : "font-semibold text-critical"}`}>
              {a.selected.length ? `Answered ${a.selected.join(", ")}` : "Unanswered"}
            </span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap justify-between gap-2">
        <button className="btn-secondary" onClick={onBack}>Back to questions</button>
        <button className="btn-danger" onClick={onSubmit} disabled={submitting}>
          {submitting ? "Submitting…" : "End test and see results"}
        </button>
      </div>
    </div>
  );
}

export default function ExamRunner() {
  const { id } = useParams();
  const nav = useNavigate();
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [idx, setIdx] = useState(0);
  const [remaining, setRemaining] = useState(null);
  const [error, setError] = useState(null);
  const [showNav, setShowNav] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const deadline = useRef(null);
  const enteredAt = useRef(Date.now());
  const warned = useRef(new Set());
  const submittedRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const a = await api.get(`/api/attempts/${id}`);
      if (a.status === "submitted") {
        nav(`/results/${id}`, { replace: true });
        return;
      }
      setAttempt(a);
      setAnswers(a.answers);
      const firstOpen = a.answers.findIndex((x) => !x.selected.length);
      setIdx(firstOpen >= 0 ? firstOpen : 0);
      if (a.remaining_sec != null) {
        deadline.current = Date.now() + a.remaining_sec * 1000;
        setRemaining(a.remaining_sec);
        // Don't re-announce warnings already passed before a reload
        for (const m of a.timer_warnings_minutes) if (a.remaining_sec <= m * 60) warned.current.add(m);
      }
    } catch (e) {
      setError(e);
    }
  }, [id, nav]);

  useEffect(() => {
    load();
  }, [load]);

  const finish = useCallback(async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      await flushTime();
      await api.post(`/api/attempts/${id}/submit`);
    } catch {
      /* already submitted (e.g. auto-submitted server-side) */
    }
    nav(`/results/${id}`, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, nav]);

  // Countdown
  useEffect(() => {
    if (!attempt || attempt.remaining_sec == null) return;
    const t = setInterval(() => {
      const left = Math.max(0, (deadline.current - Date.now()) / 1000);
      setRemaining(left);
      for (const m of attempt.timer_warnings_minutes) {
        if (left <= m * 60 && !warned.current.has(m)) {
          warned.current.add(m);
          setToast(`${m} minutes remaining`);
          setTimeout(() => setToast(null), 6000);
        }
      }
      if (left <= 0) {
        clearInterval(t);
        setToast("Time is up. Submitting your test…");
        finish();
      }
    }, 500);
    return () => clearInterval(t);
  }, [attempt, finish]);

  const current = answers[idx];

  async function send(position, body) {
    try {
      const r = await api.put(`/api/attempts/${id}/answers/${position}`, body);
      setAnswers((prev) => prev.map((a, i) => (i === position ? { ...a, ...r.answer } : a)));
      return r;
    } catch (e) {
      if (e.status === 409 && /submitted/i.test(e.message)) {
        nav(`/results/${id}`, { replace: true });
      } else {
        setError(e);
      }
    }
  }

  function flushTime() {
    const spent = (Date.now() - enteredAt.current) / 1000;
    enteredAt.current = Date.now();
    if (!current || spent < 0.5) return Promise.resolve();
    return send(idx, { time_spent_delta: spent });
  }

  function go(next) {
    if (next < 0 || next >= answers.length) return;
    flushTime();
    setIdx(next);
    setShowNav(false);
    setReviewing(false);
    window.scrollTo(0, 0);
  }

  function choose(letter) {
    if (!current || current.revealed) return;
    const q = current.question;
    let sel;
    if (q.question_type === "multiple") {
      sel = current.selected.includes(letter) ? current.selected.filter((x) => x !== letter) : [...current.selected, letter].sort();
    } else {
      sel = [letter];
    }
    setAnswers((prev) => prev.map((a, i) => (i === idx ? { ...a, selected: sel } : a)));
    send(idx, { selected: sel });
  }

  function toggleFlag() {
    if (!current) return;
    const f = !current.flagged;
    setAnswers((prev) => prev.map((a, i) => (i === idx ? { ...a, flagged: f } : a)));
    send(idx, { flagged: f });
  }

  function check() {
    if (!current?.selected.length) return;
    send(idx, { selected: current.selected, reveal: true });
  }

  // Keyboard shortcuts: 1-6 select, N next, P previous, F flag
  useEffect(() => {
    function onKey(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
      if (confirm || reviewing) return;
      const k = e.key.toLowerCase();
      if (/^[1-6]$/.test(k)) {
        const i = Number(k) - 1;
        if (current && i < current.question.options.length) {
          e.preventDefault();
          choose(LETTERS[i]);
        }
      } else if (k === "n" || e.key === "ArrowRight") {
        idx === answers.length - 1 ? setReviewing(true) : go(idx + 1);
      } else if (k === "p" || e.key === "ArrowLeft") {
        go(idx - 1);
      } else if (k === "f") {
        toggleFlag();
      } else if (k === "enter" && attempt?.feedback === "immediate" && current && !current.revealed) {
        check();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (error && !attempt) return <div className="p-8"><ErrorBox error={error} /></div>;
  if (!attempt || !current) return <div className="p-8"><Spinner /></div>;

  const q = current.question;
  const multi = q.question_type === "multiple";
  const fb = current.feedback;
  const isLast = idx === answers.length - 1;
  const answeredCount = answers.filter((a) => a.selected.length).length;
  const tooMany = multi && current.selected.length > q.choose;

  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-[#121211]">
      {/* Top bar: testing-center style */}
      <header className="sticky top-0 z-20 bg-[#16233a] text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-2.5">
          <div className="text-sm font-semibold">{attempt.exam_code}</div>
          <div className="hidden text-sm text-white/70 sm:block">
            {attempt.mode === "full" ? "Exam simulation" : attempt.mode === "practice" ? "Practice" : attempt.mode === "drill" ? "Domain drill" : "Weak-area review"}
          </div>
          <div className="text-sm">
            Question <strong>{idx + 1}</strong> of {answers.length}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Timer remaining={remaining} warn={!!toast && remaining != null} />
            <button
              onClick={toggleFlag}
              className={`rounded-md px-3 py-1 text-sm transition ${current.flagged ? "bg-warn text-black" : "bg-white/10 hover:bg-white/20"}`}
              aria-pressed={current.flagged}
              title="Flag for review (F)"
            >
              ⚑ {current.flagged ? "Flagged" : "Flag"}
            </button>
            <ThemeToggle className="text-white hover:bg-white/10" />
          </div>
        </div>
        <div className="h-1 bg-white/10">
          <div className="h-1 bg-[#6da7ec] transition-all" style={{ width: `${(answeredCount / answers.length) * 100}%` }} />
        </div>
      </header>

      {toast && (
        <div role="status" className="fixed left-1/2 top-16 z-30 -translate-x-1/2 rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white shadow-lg dark:bg-white dark:text-ink-900">
          {toast}
        </div>
      )}

      {reviewing ? (
        <ReviewScreen
          answers={answers}
          onJump={go}
          onBack={() => setReviewing(false)}
          onSubmit={() => setConfirm(true)}
          submitting={submitting}
        />
      ) : (
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-8 sm:py-10">
          {error && <div className="mb-4"><ErrorBox error={error} /></div>}
          <p className="whitespace-pre-wrap text-[1.05rem] leading-relaxed">{q.text}</p>
          {multi && (
            <p className="mt-2 text-sm font-semibold text-brand-700 dark:text-[#86b6ef]">
              {q.choose_label}. {tooMany && <span className="text-critical">You have selected more than {q.choose}.</span>}
            </p>
          )}
          <fieldset className="mt-6 space-y-2.5" disabled={current.revealed}>
            <legend className="sr-only">Answer options</legend>
            {q.options.map((o, i) => {
              const checked = current.selected.includes(o.letter);
              const isCorrect = fb?.correct?.includes(o.letter);
              let tone = checked
                ? "border-brand-500 bg-brand-50 dark:bg-[#1c2a3d]"
                : "border-slate-200 hover:border-slate-400 dark:border-[#3a3a37] dark:hover:border-[#5a5a55]";
              if (fb) {
                if (isCorrect) tone = "border-good bg-good/10";
                else if (checked) tone = "border-critical bg-critical/10";
              }
              return (
                <label key={o.letter} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3.5 transition ${tone}`}>
                  <input
                    type={multi ? "checkbox" : "radio"}
                    name={`q-${idx}`}
                    className="mt-1 h-4 w-4 accent-brand-500"
                    checked={checked}
                    onChange={() => choose(o.letter)}
                  />
                  <span className="w-5 shrink-0 font-semibold">{o.letter}.</span>
                  <span className="flex-1">{o.text}</span>
                  <kbd className="hidden rounded border border-slate-300 px-1.5 text-xs muted sm:inline dark:border-[#4a4a46]">{i + 1}</kbd>
                  {fb && isCorrect && <span className="text-sm font-semibold text-[#087a08] dark:text-[#5fd35f]">✓ Correct</span>}
                </label>
              );
            })}
          </fieldset>

          {attempt.feedback === "immediate" && !current.revealed && (
            <div className="mt-5">
              <button className="btn-primary" disabled={!current.selected.length} onClick={check}>
                Check answer <span className="text-xs opacity-75">(Enter)</span>
              </button>
            </div>
          )}

          {fb && (
            <div className={`mt-6 rounded-lg border p-4 ${fb.is_correct ? "border-good/60 bg-good/5" : "border-critical/60 bg-critical/5"}`}>
              <div className="mb-2 font-semibold">
                {fb.is_correct ? "✓ Correct" : `✕ Incorrect. The answer is ${fb.correct.join(", ")}.`}
              </div>
              <Explanation text={fb.explanation} />
              {fb.reference_url && (
                <a className="mt-3 inline-block text-sm" href={fb.reference_url} target="_blank" rel="noreferrer">
                  AWS documentation ↗
                </a>
              )}
            </div>
          )}
        </main>
      )}

      {!reviewing && (
        <footer className="sticky bottom-0 border-t border-slate-200 bg-slate-50 dark:border-[#2c2c2a] dark:bg-[#1a1a19]">
          <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
            <button className="btn-secondary" onClick={() => go(idx - 1)} disabled={idx === 0} title="Previous (P)">
              ← Previous
            </button>
            <button className="btn-ghost" onClick={() => setShowNav(true)}>
              Navigator
            </button>
            <button
              className="btn-ghost"
              onClick={() => {
                flushTime();
                nav("/");
              }}
              title="Leave and come back later. A timed test keeps running."
            >
              Save &amp; exit
            </button>
            <div className="ml-auto flex gap-2">
              <button className="btn-secondary hidden sm:inline-flex" onClick={() => { flushTime(); setReviewing(true); }}>
                Review all
              </button>
              {isLast ? (
                <button className="btn-primary" onClick={() => { flushTime(); setReviewing(true); }}>
                  Finish →
                </button>
              ) : (
                <button className="btn-primary" onClick={() => go(idx + 1)} title="Next (N)">
                  Next →
                </button>
              )}
            </div>
          </div>
        </footer>
      )}

      <Modal open={showNav} onClose={() => setShowNav(false)} title="Question navigator" wide>
        <Navigator answers={answers} current={idx} onJump={go} />
        <div className="mt-4 flex justify-end">
          <button className="btn-secondary" onClick={() => { setShowNav(false); setReviewing(true); }}>
            Go to review screen
          </button>
        </div>
      </Modal>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="End the test?">
        <p className="text-sm">
          You answered {answeredCount} of {answers.length} questions.
          {answeredCount < answers.length && " Unanswered questions count as incorrect."} You can't change answers after this.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-secondary" onClick={() => setConfirm(false)}>Keep working</button>
          <button className="btn-danger" onClick={finish} disabled={submitting}>
            {submitting ? "Submitting…" : "End test"}
          </button>
        </div>
      </Modal>
    </div>
  );
}
