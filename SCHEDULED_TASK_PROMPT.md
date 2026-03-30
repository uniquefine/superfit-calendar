# Scheduled Claude Task Prompt: PDF Analysis & events.json Generation

---

### Setup

The repository is already cloned at the working directory. Configure git:

```bash
git config user.name "claude-scheduler[bot]"
git config user.email "claude-scheduler[bot]@users.noreply.github.com"
git checkout claude/pdf-to-events-json-t0h9Z  # or the designated branch
```

---

### Inputs

```bash
find pdfs/ -name "*.pdf" | sort
```

PDFs follow naming conventions:
- `TT_<STUDIO>_<DD.MM.YY>.pdf` — **Teamtraining** schedule (short 10–20 min functional circuit sessions: Bauch, Rücken, Po, Stretch, TRX, Circuit, etc.), valid from the date in the filename
- `KP_<STUDIO>_<DD.MM.YY>.pdf` — **Kursplan** (group fitness: Les Mills + Superfit branded 45–80 min classes), valid from the date in the filename
- `Osterkursplan_<STUDIO>_<YEAR>...pdf` — **Easter special schedule**, covering specific calendar dates printed inside the PDF (Karfreitag, Ostersamstag, Ostersonntag, Ostermontag)

**Important — filename vs. PDF header:** Always read the `GÜLTIG AB <date>` header inside the PDF as the authoritative valid-from date. Filenames occasionally diverge from headers; the header wins.

`manifest.json` records `first_seen` date for each PDF (useful only as a lower bound; the `GÜLTIG AB` date is primary).

Studios:
- `friedrichshain` → `"Friedrichshain"`, address `"Frankfurter Allee 111, 10247 Berlin"`
- `mitte` → `"Mitte"`, address `"Grunerstraße 20, 10179 Berlin"`

---

### Pre-extracted OCR Text

For every PDF in the repo, a plain-text OCR extract is committed alongside it at:

```
ocr/<studio>/<pdf_stem>.txt
```

For example:
```
ocr/mitte/6992d8f06c3b4f6940e12243_KP_MI_16.02.26.txt
ocr/friedrichshain/6983663e7295b6e68676a545_TT_FH_01.02.26.txt
```

**Use these files as your primary source.** A good extract contains recognisable course names (e.g. `BODYPUMP`, `BODYATTACK`, `ZUMBA FITNESS`, `BAUCH`, `TRX`), time slots (`09:00 - 09:50`), and day headers (`MONTAG`, `DIENSTAG`, …). The regular Kursplan and Teamtraining PDFs extract reliably at 300 DPI with PSM 11.

**Only fall back to visual PDF rendering** (see below) if:
- The `.txt` file is missing or empty
- Fewer than 50 words were extracted
- No recognisable course names or time patterns appear in the text

---

### PDF Reading Strategy (fallback)

**The PDFs are graphical — course names are rendered inside coloured image blocks, not as selectable text.** Use this approach only if the pre-extracted OCR text (above) is missing or appears garbled.

Use PyMuPDF (`pip install pymupdf`) to render each page as a high-resolution PNG, then read the image visually:

```python
import fitz, os
doc = fitz.open(path)
pix = doc[0].get_pixmap(matrix=fitz.Matrix(3.5, 3.5))
pix.save("/tmp/page.png")
```

Read each day-column as a separate cropped image for legibility. The grid layout:
- Row 0 (top): studio name, schedule type, `GÜLTIG AB <date>`
- Row 1: day headers — `MONTAG DIENSTAG MITTWOCH DONNERSTAG FREITAG SAMSTAG SONNTAG`
- Body: coloured blocks per cell, each showing `<brand label> / <COURSE NAME> / <HH:MM – HH:MM>`

**Easter PDFs** use a different layout: 4 named columns (`KARFREITAG DD.MM.YY`, `OSTERSAMSTAG`, `OSTERSONNTAG`, `OSTERMONTAG`) with specific calendar dates in the headers.

---

### Schedule Priority & Date Ranges

When multiple PDFs exist for the same studio/type, the one with the **later valid-from date** takes effect from that date onward.

**Easter special schedules take precedence over the regular Kursplan** for the four Easter dates. Apply the following rule per studio:

| Studio | Easter KP | Easter TT |
|--------|-----------|-----------|
| Friedrichshain | FH Osterkursplan replaces KP **and** TT | No TT (Easter plan is the full schedule) |
| Mitte | MI Osterkursplan replaces KP | Regular TT continues per the active TT plan |

TT and KP schedules are **additive** on non-Easter days — both contribute events for the same studio on the same date.

Some Mitte TT slots are labelled `WOMEN` or `FUNCTIONAL`, indicating a dedicated equipment area. Include these normally; no special handling needed.

---

### Your Task

Today's date is provided at runtime. Generate all events falling within the next **4 weeks** from today (inclusive).

For each event output:

```json
{
  "course": "Body Attack",
  "studio": "Friedrichshain",
  "address": "Frankfurter Allee 111, 10247 Berlin",
  "date": "2026-04-07",
  "start": "20:00",
  "end": "20:50"
}
```

**Course name normalisation:**
- Les Mills classes: `Body Attack`, `Body Balance`, `Body Combat`, `Body Jam`, `Body Pump`, `Body Pump Heavy`, `Body Vive`, `LMiStep`, `Shapes`, `Dance`
- Superfit classes (title case): `Yoga`, `Yoga Express`, `Pilates`, `Zumba Fitness`, `Rücken`, `Bauch`, `Bauch Express`, `Po`, `Beine & Po`, `Stretch`, `Circuit`, `TRX`, `Faszientraining`, `Mobility`, `Fullbody Workout`, `Functional`
- Easter Express variants: append ` Express` as shown in the PDF (e.g. `Body Pump Express`, `Pilates Express`)
- Do **not** prefix class names with `Teamtraining` or `LesMills`

---

### Output

Write `calendar/events.json`: a JSON array sorted by `date`, then `start`, then `studio`. Valid JSON, no trailing commas.

Then:

```bash
git add calendar/events.json
git commit -m "chore: update events.json for week of <today's date>"
git push -u origin <branch>
```

Even if identical to the existing file, commit and push — the timestamp confirms the task ran.

---

### Error Handling

- PDF unreadable → warn and skip; do not abort
- No events extracted at all → do not overwrite `calendar/events.json`; exit without committing
- Ambiguous course name → best inference; note it in the commit message
