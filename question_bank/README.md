# Question bank

CloudCert Lab reads questions from CSV files in this folder. Put each file in the subfolder for its exam:

```
question_bank/
├── TEMPLATE.csv        ← 5 example rows (not imported; copy it to start a new file)
├── clf-c02/            ← AWS Certified Cloud Practitioner
├── saa-c03/            ← AWS Certified Solutions Architect – Associate
└── sap-c02/            ← AWS Certified Solutions Architect – Professional
    └── generated/      ← created by the AI generator (status = pending until you approve)
```

While the app is running, new or changed CSV files are imported automatically within a couple of seconds.
You can also click **Import now** on the Question bank page, or run:

```bash
make import                              # everything in question_bank/
cd backend && ../.venv/bin/python -m app.cli import ../my-file.csv   # one file
```

Files are imported recursively, so you can organise them in subfolders. Files whose names start with
`TEMPLATE`, `.` or `~$` (Excel lock files) are ignored.

## Columns

| Column | Required | Notes |
|---|---|---|
| `exam` | yes | `CLF-C02`, `SAA-C03`, or `SAP-C02` (case-insensitive). Must match the folder. |
| `domain` | yes | The domain name (e.g. `Design Resilient Architectures`) **or** its number (`2`, `Domain 2`). |
| `difficulty` | yes | `Easy`, `Medium`, `Hard`, or `Tough`. |
| `question_type` | yes | `single` or `multiple` (multiple-response). |
| `question` | yes | The question text. For multiple-response, end with "(Choose TWO.)" or "(Choose THREE.)". |
| `option_a` … `option_f` | A–C required | 3 to 6 options, filled from A without gaps. |
| `correct` | yes | One letter for single (`B`), two or more for multiple (`A,D`; `A D` and `AD` also work). |
| `explanation` | yes | Why the answer is right (ideally why the others are wrong). Line breaks are kept. |
| `services` | no | AWS service tags separated by semicolons: `Amazon S3;AWS Lambda`. Used by service drills. |
| `reference_url` | no | Link to the relevant AWS documentation page (`http://` or `https://`). |
| `status` | no | `active` (default), `pending`, or `rejected`. Only `active` questions appear in tests. |

Domains per exam (from `config/exams.yaml`):

- **CLF-C02**: 1 Cloud Concepts · 2 Security and Compliance · 3 Cloud Technology and Services · 4 Billing, Pricing, and Support
- **SAA-C03**: 1 Design Secure Architectures · 2 Design Resilient Architectures · 3 Design High-Performing Architectures · 4 Design Cost-Optimized Architectures
- **SAP-C02**: 1 Design Solutions for Organizational Complexity · 2 Design for New Solutions · 3 Continuous Improvement for Existing Solutions · 4 Accelerate Workload Migration and Modernization

## Validation and the import report

Every row is checked. A row is skipped, and listed in the import report with its row number and the
reason, if it has any of these problems:

- a required field is empty
- the exam is unknown, or doesn't match the folder the file is in
- the domain isn't one of that exam's domains
- the difficulty or question type isn't one of the allowed values
- fewer than 3 options, a gap in the options (e.g. C empty but D filled), or two identical options
- a correct letter that isn't among the options, the wrong number of correct letters for the
  question type, or a multiple-response question where every option is correct
- a `reference_url` that isn't a web link, or an unknown `status`
- the same question appears twice in one file

Row numbers match what a spreadsheet shows (the header is row 1). If a required column is missing from
the header, the whole file is rejected and the report says which columns are missing.

## Duplicates and updates

Questions are identified by their **normalized text**: lowercase, punctuation removed, whitespace
collapsed, per exam. So:

- Re-saving a file with a changed explanation, answer, difficulty, etc. **updates** the existing
  question. It isn't duplicated, and your history for it is kept.
- The same question in two files is stored once (the last file imported wins).
- Rewording a question's text makes it a new question. The old version is removed, or "retired" if it
  already appears in your test history.
- Rows deleted from a file are removed (or retired) the next time that file is imported.

Edits made in the app (Review screen or Question bank page) are written back to the question's CSV row,
so the files remain the source of truth. Columns other than the ones above are not preserved by edits.

## Encoding

Save files as CSV UTF-8 (Excel: *File → Save As → CSV UTF-8*). Quote any field that contains commas;
spreadsheet apps do this automatically.
