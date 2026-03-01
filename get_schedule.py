import collections
import collections.abc
collections.Mapping = collections.abc.Mapping

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIME_MAP = {
    "1-2": ("07:00", "08:35"),
    "3-4": ("08:50", "10:25"),
    "5-6": ("10:40", "12:15"),
    "7-8": ("12:30", "14:05"),
    "9-10": ("15:00", "16:35"),
    "11-12": ("16:50", "18:25"),
    "13-14": ("19:30", "20:15"),
}

MONTH_MAP = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}

semester = "lato"
group = "WEL24EL2S0"
filename = f"{group}_{semester}.ics"


def format_cell_text(cell):
    lines = [line.strip() for line in cell.get_text("\n").split("\n") if line.strip()]
    return "\\n".join(lines)


def format_ics_datetime(dt: datetime) -> str:
    # Lokalny czas bez Z, format RFC5545
    return dt.strftime("%Y%m%dT%H%M%S")


def parse_wat_schedule():
    url = f"https://plany.wel.wat.edu.pl/{semester}/{group}.htm"

    response = requests.get(url, verify=False, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table")

    events = []
    current_dates = []

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        first_cell_text = cells[0].get_text(strip=True).lower()

        # Wiersz z datami
        if any(
            day_name in first_cell_text
            for day_name in ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]
        ):
            current_dates = []
            for cell in cells[2:]:
                text = cell.get_text(strip=True)
                match = re.search(r"(\d{2})\s+([IVX]+)", text)
                if match:
                    day, month_roman = match.groups()
                    base_date = datetime(2026, MONTH_MAP[month_roman], int(day))
                    shifted_date = base_date + timedelta(days=7)
                    current_dates.append(shifted_date)
            continue

        # Wiersz z zajęciami
        if first_cell_text in TIME_MAP:
            start_t, end_t = TIME_MAP[first_cell_text]
            for i, cell in enumerate(cells[2:]):
                cell_content = format_cell_text(cell)
                if cell_content and i < len(current_dates):
                    date = current_dates[i]

                    start_dt = datetime.strptime(
                        date.strftime(f"%Y-%m-%d {start_t}:00"),
                        "%Y-%m-%d %H:%M:%S",
                    )
                    end_dt = datetime.strptime(
                        date.strftime(f"%Y-%m-%d {end_t}:00"),
                        "%Y-%m-%d %H:%M:%S",
                    )

                    uid = f"{date.strftime('%Y%m%d')}-{first_cell_text}-{i}@wat-schedule"

                    events.append(
                        {
                            "uid": uid,
                            "summary": cell_content,
                            "dtstart": format_ics_datetime(start_dt),
                            "dtend": format_ics_datetime(end_dt),
                        }
                    )

    # Ręczne złożenie pliku ICS – lokalny czas, bez Z, bez TZID
    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//F3zzyy//WAT Schedule//PL")

    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['uid']}")
        lines.append(f"SUMMARY:{ev['summary']}")
        lines.append(f"DTSTART:{ev['dtstart']}")
        lines.append(f"DTEND:{ev['dtend']}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

    print(f"✨ Generated {len(events)} events into {filename}.")
    print("✅ Times are written as LOCAL (no Z, no TZID).")


if __name__ == "__main__":
    parse_wat_schedule()
