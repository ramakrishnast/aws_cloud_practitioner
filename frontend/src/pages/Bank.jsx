import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { DIFFICULTIES, DifficultyChip, ErrorBox, Spinner, fmtDate, title } from "../ui.jsx";
import QuestionEditor from "./QuestionEditor.jsx";

function ReportCard({ r }) {
  const [open, setOpen] = useState(r.errors.length > 0 && r.errors.length < 8);
  const bad = r.fatal || r.skipped > 0;
  return (
    <div className={`rounded-lg border p-3 text-sm ${bad ? "border-amber-300 dark:border-amber-800" : "border-slate-200 dark:border-[#2c2c2a]"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <code className="text-xs">{r.path}</code>
        <span className="text-xs muted">{fmtDate(r.created_at)} · {r.trigger}</span>
      </div>
      {r.fatal ? (
        <p className="mt-1 font-medium text-critical">File not imported: {r.fatal}</p>
      ) : (
        <p className="mt-1">
          {r.total_rows} rows · <strong>{r.inserted}</strong> new · <strong>{r.updated}</strong> updated · {r.unchanged} unchanged ·{" "}
          <span className={r.skipped ? "font-semibold text-critical" : ""}>{r.skipped} skipped</span>
        </p>
      )}
      {r.errors.length > 0 && (
        <div className="mt-2">
          <button className="text-xs underline" onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} details ({r.errors.length})
          </button>
          {open && (
            <ul className="mt-1 max-h-64 space-y-0.5 overflow-y-auto text-xs">
              {r.errors.map((e, i) => (
                <li key={i}>
                  <strong>{e.row ? `Row ${e.row}` : "Note"}:</strong> {e.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default function Bank() {
  const [exams, setExams] = useState([]);
  const [reports, setReports] = useState(null);
  const [lastImport, setLastImport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ exam: "clf-c02", status: "active", domain_id: "", difficulty: "", q: "", page: 1 });
  const [list, setList] = useState(null);
  const [editing, setEditing] = useState(null);
  const [uploadExam, setUploadExam] = useState("clf-c02");
  const [notice, setNotice] = useState(null);

  const loadReports = () => api.get("/api/import/reports").then(setReports).catch(setError);
  const loadList = useCallback(() => {
    const p = new URLSearchParams(Object.entries(filters).filter(([, v]) => v !== ""));
    api.get(`/api/questions?${p}`).then(setList).catch(setError);
  }, [filters]);

  useEffect(() => {
    api.get("/api/exams").then((d) => setExams(d.exams)).catch(setError);
    loadReports();
  }, []);
  useEffect(loadList, [loadList]);

  async function importNow(force = false) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post("/api/import", { force });
      setLastImport(r);
      loadReports();
      loadList();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function upload(ev) {
    ev.preventDefault();
    const file = ev.target.file.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("exam", uploadExam);
    fd.append("file", file);
    setBusy(true);
    try {
      const r = await api.post("/api/import/upload", fd);
      setNotice(`Saved to question_bank/${r.saved_to}`);
      setLastImport({ reports: r.report ? [r.report] : [], unchanged_files: [] });
      ev.target.reset();
      loadReports();
      loadList();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const exam = exams.find((e) => e.key === filters.exam);
  const setFilter = (k, v) => setFilters((p) => ({ ...p, [k]: v, page: k === "page" ? v : 1 }));
  const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Question bank</h1>
        <p className="text-sm muted">
          Drop CSV files into <code>question_bank/clf-c02/</code>, <code>saa-c03/</code>, or <code>sap-c02/</code>. New and changed files
          are imported automatically. See <code>question_bank/README.md</code> for the format.
        </p>
      </div>
      <ErrorBox error={error} />
      {notice && <p className="text-sm text-[#087a08] dark:text-[#5fd35f]">{notice}</p>}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card space-y-3">
          <h2 className="font-semibold">Import</h2>
          <button className="btn-primary w-full" onClick={() => importNow(false)} disabled={busy}>{busy ? "Importing…" : "Import now"}</button>
          <button className="btn-secondary w-full" onClick={() => importNow(true)} disabled={busy}>Re-import everything</button>
          <p className="text-xs muted">CLI: <code>make import</code> or <code>python -m app.cli import</code></p>
        </div>
        <form className="card space-y-3 md:col-span-2" onSubmit={upload}>
          <h2 className="font-semibold">Upload a CSV</h2>
          <div className="flex flex-wrap gap-2">
            <select className="input w-auto" value={uploadExam} onChange={(e) => setUploadExam(e.target.value)} aria-label="Exam">
              {exams.map((e) => <option key={e.key} value={e.key}>{e.code}</option>)}
            </select>
            <input name="file" type="file" accept=".csv,text/csv" className="input flex-1" />
            <button className="btn-secondary" disabled={busy}>Upload &amp; import</button>
          </div>
          <p className="text-xs muted">The file is copied into the exam's folder, so it stays in your bank.</p>
        </form>
      </div>

      {lastImport && (
        <div className="card space-y-2">
          <h2 className="font-semibold">Import report</h2>
          {lastImport.reports.length === 0 ? (
            <p className="text-sm muted">No new or changed files ({lastImport.unchanged_files.length} unchanged).</p>
          ) : (
            lastImport.reports.map((r) => <ReportCard key={r.id} r={r} />)
          )}
        </div>
      )}

      <section className="card space-y-4">
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <span className="label">Exam</span>
            <select className="input" value={filters.exam} onChange={(e) => setFilter("exam", e.target.value)}>
              {exams.map((e) => <option key={e.key} value={e.key}>{e.code}</option>)}
            </select>
          </div>
          <div>
            <span className="label">Status</span>
            <select className="input" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
              <option value="">Any</option>
              <option value="active">Active</option>
              <option value="pending">Pending review</option>
              <option value="rejected">Rejected</option>
              <option value="retired">Retired</option>
            </select>
          </div>
          <div>
            <span className="label">Domain</span>
            <select className="input" value={filters.domain_id} onChange={(e) => setFilter("domain_id", e.target.value)}>
              <option value="">All</option>
              {exam?.domains.map((d) => <option key={d.id} value={d.id}>{d.id}. {d.name}</option>)}
            </select>
          </div>
          <div>
            <span className="label">Difficulty</span>
            <select className="input" value={filters.difficulty} onChange={(e) => setFilter("difficulty", e.target.value)}>
              <option value="">All</option>
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{title(d)}</option>)}
            </select>
          </div>
          <div className="min-w-[200px] flex-1">
            <span className="label">Search</span>
            <input className="input" value={filters.q} placeholder="Search text…" onChange={(e) => setFilter("q", e.target.value)} />
          </div>
        </div>
        {!list ? (
          <Spinner />
        ) : (
          <>
            <p className="text-sm muted">{list.total} question{list.total === 1 ? "" : "s"}</p>
            <ul className="divide-y divide-slate-100 dark:divide-[#2c2c2a]">
              {list.items.map((q) => (
                <li key={q.id} className="flex items-start gap-3 py-2.5">
                  <div className="flex-1">
                    <p className="line-clamp-2 text-sm">{q.text}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs muted">
                      <DifficultyChip value={q.difficulty} />
                      <span>D{q.domain_id}</span>
                      <span>{q.question_type === "multiple" ? "Multiple response" : "Single answer"}</span>
                      <span>{q.services.join(", ")}</span>
                      <code>{q.source_file}</code>
                    </div>
                  </div>
                  <button className="btn-ghost py-1 text-xs" onClick={() => setEditing(q)}>Edit</button>
                </li>
              ))}
            </ul>
            {pages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <button className="btn-secondary py-1" disabled={filters.page <= 1} onClick={() => setFilter("page", filters.page - 1)}>Previous</button>
                <span className="text-sm muted">Page {filters.page} of {pages}</span>
                <button className="btn-secondary py-1" disabled={filters.page >= pages} onClick={() => setFilter("page", filters.page + 1)}>Next</button>
              </div>
            )}
          </>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">Recent imports</h2>
        {!reports ? <Spinner /> : reports.length === 0 ? <p className="text-sm muted">None yet.</p> : reports.slice(0, 15).map((r) => <ReportCard key={r.id} r={r} />)}
      </section>

      {editing && (
        <QuestionEditor
          question={editing}
          domains={exam?.domains || []}
          onClose={() => setEditing(null)}
          onSaved={(_q, warning) => {
            setEditing(null);
            setNotice(warning || "Saved.");
            loadList();
          }}
        />
      )}
    </div>
  );
}
