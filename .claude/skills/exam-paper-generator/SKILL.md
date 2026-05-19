---
name: exam-paper-generator
description: create printable exam paper pdfs from a supplied question set, with separate student paper and answer key. use when the user asks to generate, typeset, format, paginate, or export a test/exam/quiz/workbook pdf from questions, especially when questions and answers must be separated and each question block must stay intact across page breaks instead of being split at the bottom of a page.
---

# Exam Paper Generator

Use this skill to generate two PDF files from a question set:

1. a student-facing exam paper without answers
2. a separate answer key PDF

The bundled script `scripts/generate_exam_pdf.py` uses ReportLab and keeps each question as an unbroken layout block whenever the full question fits on a page. If there is not enough space at the bottom of the current page, that question automatically moves to the next page. Only questions taller than a full page may split.

## Workflow

1. Collect or infer the exam metadata: title, subject, grade/class, duration, total points, and instructions.
2. Convert the user's questions into the JSON schema in `references/input-schema.md`.
3. Run the generator script:

```bash
python scripts/generate_exam_pdf.py input.json --out-dir /mnt/data/exam_output
```

4. Return both generated files:
   - `exam.pdf`
   - `answers.pdf`
5. For important deliverables, render or inspect the PDFs after generation to verify that text is not clipped and question blocks are not split unexpectedly.

## Input handling rules

- If the user provides Markdown, Word-like text, CSV-style rows, or pasted questions, normalize them into the JSON schema before running the script.
- Put answer content only in each question's `answer` field. Do not include answers in the student-facing `prompt`, `options`, or `subquestions` unless the user explicitly wants worked examples on the exam paper.
- Preserve question order unless the user asks to shuffle.
- If total points are not provided, omit the total rather than inventing it. If per-question points are absent, leave `points` blank.
- For Chinese exam content, keep punctuation and numbering natural; do not translate.

## Pagination requirements

- Treat the full question block as atomic: stem, options, subquestions, diagrams noted as text, blank answer space, and point value.
- Ensure the script uses keep-together layout behavior so a question that would only partially fit at the page bottom is moved to the next page.
- Insert section headings normally, but do not let a section heading appear alone at the bottom of a page if the next question cannot fit.
- Permit a split only when a single question is longer than one full page.

## Default layout choices

Use these defaults unless the user asks otherwise:

- A4 paper size
- Chinese-capable font auto-detection when available
- portrait orientation
- numbered questions
- question blocks with modest spacing
- optional answer space after each student question when `answer_space_lines` is set
- answer key containing question number plus answer/explanation

## Quality checklist

Before returning files, confirm:

- The student paper does not reveal answers.
- The answer key includes every provided answer.
- Question numbering is continuous and matches between PDFs.
- No normal-length question is split across pages.
- Text is not clipped, overlapped, or rendered as missing glyph boxes.
