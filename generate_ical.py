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

    for course_name, course_events in sorted(by_course.items()):
        filename = f"{slugify(course_name)}.ics"
        dest = OUTPUT_DIR / filename
        cal = build_calendar(course_name, course_events)
        dest.write_bytes(cal.to_ical())
        print(f"Wrote {dest}  ({len(course_events)} event(s))")

    return 0


if __name__ == "__main__":
    sys.exit(main())
