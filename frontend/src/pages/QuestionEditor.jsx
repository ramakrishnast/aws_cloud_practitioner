import { useState } from "react";
import { api } from "../api.js";
import { DIFFICULTIES, ErrorBox, Modal, title } from "../ui.jsx";

const LETTERS = "ABCDEF";

export default function QuestionEditor({ question, domains, onClose, onSaved }) {
  const [f, setF] = useState(() => ({
    text: question.text,
    question_type: question.question_type,
    domain_id: question.domain_id,
    difficulty: question.difficulty,
    options: [...question.options.map((o) => o.text), ...Array(6 - question.options.length).fill("")],
    correct: question.correct,
    explanation: question.explanation,
    services: (question.services || []).join("; "),
    reference_url: question.reference_url || "",
    status: question.status,
  }));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  function toggleCorrect(l) {
    if (f.question_type === "single") set("correct", [l]);
    else set("correct", f.correct.includes(l) ? f.correct.filter((x) => x !== l) : [...f.correct, l].sort());
  }

  async function save() {
    setBusy(true);
    setError(null);
    let opts = [...f.options];
    while (opts.length && !opts[opts.length - 1].trim()) opts.pop();
    try {
      const r = await api.put(`/api/questions/${question.id}`, {
        ...f,
        domain_id: Number(f.domain_id),
        options: opts,
        services: f.services.split(";").map((s) => s.trim()).filter(Boolean),
      });
      onSaved?.(r.question, r.warning);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={`Edit question #${question.id}`} wide>
      <div className="space-y-4">
        <ErrorBox error={error} />
        <div>
          <label className="label" htmlFor="qe-text">Question</label>
          <textarea id="qe-text" className="input min-h-[110px]" value={f.text} onChange={(e) => set("text", e.target.value)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          <div>
            <label className="label">Type</label>
            <select className="input" value={f.question_type} onChange={(e) => { set("question_type", e.target.value); set("correct", f.correct.slice(0, 1)); }}>
              <option value="single">Single answer</option>
              <option value="multiple">Multiple response</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">Domain</label>
            <select className="input" value={f.domain_id} onChange={(e) => set("domain_id", e.target.value)}>
              {domains.map((d) => <option key={d.id} value={d.id}>{d.id}. {d.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Difficulty</label>
            <select className="input" value={f.difficulty} onChange={(e) => set("difficulty", e.target.value)}>
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{title(d)}</option>)}
            </select>
          </div>
        </div>
        <div className="space-y-2">
          <span className="label">Options (tick the correct answer{f.question_type === "multiple" ? "s" : ""})</span>
          {f.options.map((o, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type={f.question_type === "multiple" ? "checkbox" : "radio"}
                checked={f.correct.includes(LETTERS[i])}
                onChange={() => toggleCorrect(LETTERS[i])}
                aria-label={`Option ${LETTERS[i]} is correct`}
                className="h-4 w-4 accent-brand-500"
              />
              <span className="w-5 font-semibold">{LETTERS[i]}</span>
              <input className="input" value={o} placeholder={i >= 4 ? "(optional)" : ""} onChange={(e) => set("options", f.options.map((x, j) => (j === i ? e.target.value : x)))} />
            </div>
          ))}
        </div>
        <div>
          <label className="label" htmlFor="qe-exp">Explanation</label>
          <textarea id="qe-exp" className="input min-h-[140px]" value={f.explanation} onChange={(e) => set("explanation", e.target.value)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">AWS services (semicolon-separated)</label>
            <input className="input" value={f.services} onChange={(e) => set("services", e.target.value)} />
          </div>
          <div>
            <label className="label">Reference URL</label>
            <input className="input" value={f.reference_url} onChange={(e) => set("reference_url", e.target.value)} />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <select className="input w-auto" value={f.status} onChange={(e) => set("status", e.target.value)} aria-label="Status">
            <option value="active">Active (used in tests)</option>
            <option value="pending">Pending review</option>
            <option value="rejected">Rejected</option>
          </select>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </div>
        <p className="text-xs muted">Saving also updates the question's row in its CSV file ({question.source_file || "no file"}).</p>
      </div>
    </Modal>
  );
}
