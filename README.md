# Superfit Calendar

Automated iCal subscriptions for [Superfit](https://superfit.club) fitness course schedules.

## Architecture

```
┌──────────────────────┐     daily 06:00 UTC
│   scrape.yml (GHA)   │ ──────────────────────► pdfs/ + manifest.json
│   scrape.py          │                          committed to main
└──────────────────────┘

┌──────────────────────┐     external schedule
│  Claude scheduled    │ ──────────────────────► calendar/events.json
│  task (reads PDFs,   │                          committed to main
│  writes events.json) │
└──────────────────────┘

┌──────────────────────┐     on push to main
│   publish.yml (GHA)  │     (calendar/events.json changed)
│   generate_ical.py   │ ──────────────────────► .ics files on GitHub Pages
└──────────────────────┘
```

1. **`scrape.py`** runs daily, downloads new course plan PDFs from the Superfit studio pages into `pdfs/friedrichshain/` and `pdfs/mitte/`, and updates `manifest.json`. Commits and pushes when anything changes.

2. **External scheduled task** (Claude agent) reads the PDFs, extracts course events, and writes `calendar/events.json` to the repo.

3. **`generate_ical.py`** reads `calendar/events.json` and produces one `.ics` file per course type in `calendar/`. Triggered automatically by `publish.yml` whenever `events.json` changes on `main`.

4. **GitHub Pages** serves the `calendar/` directory, making the `.ics` files publicly subscribable.

## `events.json` Schema

`calendar/events.json` is a JSON array of course event objects:

```json
[
  {
    "course": "Body Attack",
    "studio": "Friedrichshain",
    "address": "Frankfurter Allee 111, 10247 Berlin",
    "date": "2026-04-07",
    "start": "20:00",
    "end": "20:50"
  }
]
```

| Field     | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `course`  | string | Course name, e.g. `"Body Attack"`        |
| `studio`  | string | Studio location name                     |
| `address` | string | Full street address                      |
| `date`    | string | ISO 8601 date, `YYYY-MM-DD`              |
| `start`   | string | Start time `HH:MM` (Europe/Berlin)       |
| `end`     | string | End time `HH:MM` (Europe/Berlin)         |

## Calendar Subscription URLs

Once GitHub Pages is configured, `.ics` files are available at:

```
https://uniquefine.github.io/superfit-calendar/<course-slug>.ics
```

For example:

| Course       | URL                                                                                    |
|--------------|----------------------------------------------------------------------------------------|
| Body Attack  | `https://uniquefine.github.io/superfit-calendar/body-attack.ics`                      |
| Body Pump    | `https://uniquefine.github.io/superfit-calendar/body-pump.ics`                        |

Course slugs are the course name lowercased with spaces replaced by hyphens.

To subscribe, paste the URL into your calendar app:
- **Google Calendar:** Other calendars → + → From URL
- **Apple Calendar:** File → New Calendar Subscription
- **Outlook:** Add calendar → Subscribe from web

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `scrape.yml` | Daily 06:00 UTC or manual | Downloads new PDFs, commits changes |
| `publish.yml` | Push to `main` touching `calendar/events.json`, or manual | Generates `.ics` files, deploys to GitHub Pages |

### Manually triggering a workflow

1. Go to the repo on GitHub → **Actions** tab
2. Click the workflow name in the left sidebar
3. Click **Run workflow** → select branch → **Run workflow**

## Local Development

```bash
pip install -r requirements.txt

# Run the scraper (downloads PDFs, updates manifest.json)
python scrape.py

# Generate .ics files from calendar/events.json
python generate_ical.py
```

## GitHub Pages Setup

1. Go to repo **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Push a change to `calendar/events.json` on `main` (or trigger `publish.yml` manually)
4. The site will be live at `https://uniquefine.github.io/superfit-calendar/`
