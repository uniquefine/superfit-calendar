"""
Reads calendar/events.json and writes one .ics file per unique course type
into the calendar/ directory.

Usage:
    python generate_ical.py
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vDatetime, vText

EVENTS_PATH = Path("calendar/events.json")
OUTPUT_DIR = Path("calendar")
BERLIN = ZoneInfo("Europe/Berlin")
UID_DOMAIN = "superfit-calendar"


def slugify(text: str) -> str:
    """Lowercase, replace spaces/special chars with hyphens."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text


def make_uid(course: str, studio: str, date: str, start: str) -> str:
    parts = [slugify(course), slugify(studio), date, start.replace(":", "")]
    return f"{'-'.join(parts)}@{UID_DOMAIN}"


def parse_berlin_dt(date: str, time: str) -> datetime:
    """Parse date + HH:MM into a timezone-aware datetime in Europe/Berlin."""
    return datetime.fromisoformat(f"{date}T{time}:00").replace(tzinfo=BERLIN)


def build_calendar(course_name: str, events: list[dict]) -> Calendar:
    cal = Calendar()
    cal.add("PRODID", f"-//superfit-calendar//{slugify(course_name)}//EN")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("X-WR-CALNAME", vText(course_name))
    cal.add("X-WR-TIMEZONE", vText("Europe/Berlin"))

    now_utc = datetime.now(tz=timezone.utc)

    for ev in events:
        vevent = Event()
        vevent.add("SUMMARY", vText(ev["course"]))
        vevent.add("DTSTART", vDatetime(parse_berlin_dt(ev["date"], ev["start"])))
        vevent.add("DTEND",   vDatetime(parse_berlin_dt(ev["date"], ev["end"])))
        vevent.add("LOCATION", vText(f"{ev['studio']}, {ev['address']}"))
        vevent.add("UID", vText(make_uid(ev["course"], ev["studio"], ev["date"], ev["start"])))
        vevent.add("DTSTAMP", vDatetime(now_utc))
        cal.add_component(vevent)

    return cal


def write_index(output_dir: Path, courses: list[tuple[str, str, int]]) -> None:
    """Write index.html listing all generated .ics files.

    courses: list of (course_name, filename, event_count)
    """
    rows = "\n".join(
        f"""        <li>
          <span class="course-name">{name}</span>
          <a class="btn" href="{filename}" download>Download .ics</a>
          <a class="btn btn-secondary" href="{filename}">Subscribe</a>
          <span class="count">{count} event{"s" if count != 1 else ""}</span>
        </li>"""
        for name, filename, count in courses
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Superfit Calendar</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 640px;
      margin: 48px auto;
      padding: 0 24px;
      color: #111;
      background: #fff;
    }}
    h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
    p.subtitle {{ color: #555; margin-top: 0; margin-bottom: 32px; }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid #eee;
    }}
    li:last-child {{ border-bottom: none; }}
    .course-name {{ flex: 1; font-weight: 500; }}
    .btn {{
      display: inline-block;
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 0.85rem;
      text-decoration: none;
      background: #111;
      color: #fff;
      white-space: nowrap;
    }}
    .btn-secondary {{
      background: #fff;
      color: #111;
      border: 1px solid #ccc;
    }}
    .count {{ font-size: 0.8rem; color: #888; white-space: nowrap; }}
    footer {{ margin-top: 40px; font-size: 0.8rem; color: #aaa; }}
  </style>
</head>
<body>
  <h1>Superfit Calendar</h1>
  <p class="subtitle">Subscribe to course schedules for Superfit Berlin studios.</p>
  <ul>
{rows}
  </ul>
  <footer>Updated automatically · <a href="https://github.com/uniquefine/superfit-calendar">GitHub</a></footer>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {output_dir / 'index.html'}  ({len(courses)} calendar(s))")


def main() -> int:
    if not EVENTS_PATH.exists():
        print(f"ERROR: {EVENTS_PATH} not found", file=sys.stderr)
        return 1

    events: list[dict] = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    if not events:
        print("No events found — nothing to generate.")
        return 0

    by_course: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        by_course[ev["course"]].append(ev)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    index_entries: list[tuple[str, str, int]] = []
    for course_name, course_events in sorted(by_course.items()):
        filename = f"{slugify(course_name)}.ics"
        dest = OUTPUT_DIR / filename
        cal = build_calendar(course_name, course_events)
        dest.write_bytes(cal.to_ical())
        print(f"Wrote {dest}  ({len(course_events)} event(s))")
        index_entries.append((course_name, filename, len(course_events)))

    write_index(OUTPUT_DIR, index_entries)

    return 0


if __name__ == "__main__":
    sys.exit(main())
