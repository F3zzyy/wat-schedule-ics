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

EXCLUDE_TAGS = ["XWF", "XFiz1", "SSW"]


def format_cell_text(cell):
    lines = [line.strip() for line in cell.get_text("\n").split("\n") if line.strip()]
    return "\\n".join(lines)


def format_ics_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def parse_cell_details(text):
    lines = [l.strip() for l in text.split("\\n") if l.strip()]
    if not lines:
        return "", "", "", ""

    summary = lines[0]
    room = ""
    teacher = ""
    other_lines = []

    for l in lines[1:]:
        # sala – np. "s. 204", "s. L-4"
        if not room and re.search(r"\bs\.\s*\S+", l, re.IGNORECASE):
            room = l
            continue
        # prowadzący – dr, mgr, prof
        if not teacher and re.search(r"\b(dr|mgr|prof)\b", l, re.IGNORECASE):
            teacher = l
            continue
        other_lines.append(l)

    notes = "\\n".join(other_lines)
    return summary, room, teacher, notes


def parse_wat_schedule():
    url = f"https://plany.wel.wat.edu.pl/{semester}/{group}.htm"
    resp = requests.get(url, verify=False, timeout=10)
    # Plansoft zwykle w Windows-1250
    resp.encoding = resp.encoding or "windows-1250"
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")

    events = []

    current_dates = []          # lista datetime dla kolumn lekcyjnych
    lesson_col_indices = []     # indeksy komórek w wierszu z datami odpowiadające kolumnom lekcyjnym

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        first_text = cells[0].get_text(" ", strip=True).lower()

        # 1) Wiersz z datami – wykryj wszystkie komórki z "dzień + rzymski miesiąc"
        if any(day in first_text for day in ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]):
            current_dates = []
            lesson_col_indices = []

            for idx, cell in enumerate(cells):
                text = cell.get_text(" ", strip=True)
                m = re.search(r"(\d{1,2})\s+([IVX]+)", text)
                if not m:
                    continue
                day, month_roman = m.groups()
                month = MONTH_MAP.get(month_roman)
                if not month:
                    continue

                base_date = datetime(2026, month, int(day))
                # Twój shift o tydzień – zostawiam
                shifted_date = base_date + timedelta(days=7)

                current_dates.append(shifted_date)
                lesson_col_indices.append(idx)

            continue

        # 2) Wiersz z godzinami
        # Normalizujemy "1 – 2", "1-2", "1 –2" itd.
        time_match = re.match(r"(\d+)\s*[-–]\s*(\d+)", first_text)
        if not time_match:
            continue

        time_key = f"{time_match.group(1)}-{time_match.group(2)}"
        if time_key not in TIME_MAP or not current_dates:
            continue

        start_t, end_t = TIME_MAP[time_key]

        # przechodzimy po tych kolumnach, które wcześniej zidentyfikowaliśmy jako kolumny lekcyjne
        for date_idx, cell_idx in enumerate(lesson_col_indices):
            if cell_idx >= len(cells):
                continue

            cell = cells[cell_idx]
            cell_content = format_cell_text(cell)

            if not cell_content:
                continue
            if any(tag in cell_content for tag in EXCLUDE_TAGS):
                continue

            date = current_dates[date_idx]

            start_dt = datetime.strptime(
                date.strftime(f"%Y-%m-%d {start_t}:00"),
                "%Y-%m-%d %H:%M:%S",
            )
            end_dt = datetime.strptime(
                date.strftime(f"%Y-%m-%d {end_t}:00"),
                "%Y-%m-%d %H:%M:%S",
            )

            uid = f"{date.strftime('%Y%m%d')}-{time_key}-{date_idx}@wat-schedule"

            summary, room, teacher, notes = parse_cell_details(cell_content)

            desc_parts = []
            if notes:
                desc_parts.append(notes)
            if teacher:
                desc_parts.append(f"Prowadzący: {teacher}")
            description = "\\n".join(desc_parts)

            events.append(
                {
                    "uid": uid,
                    "summary": summary or cell_content,
                    "location": room,
                    "description": description,
                    "dtstart": format_ics_datetime(start_dt),
                    "dtend": format_ics_datetime(end_dt),
                }
            )

    # składanie ICS
    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//F3zzyy//WAT Schedule//PL")

    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['uid']}")
        if ev.get("summary"):
            lines.append(f"SUMMARY:{ev['summary']}")
        if ev.get("location"):
            lines.append(f"LOCATION:{ev['location']}")
        if ev.get("description"):
            desc = ev["description"].replace("\r\n", "\\n").replace("\n", "\\n")
            lines.append(f"DESCRIPTION:{desc}")
        lines.append(f"DTSTART:{ev['dtstart']}")
        lines.append(f"DTEND:{ev['dtend']}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

    print(f"✨ Generated {len(events)} events into {filename}.")


if __name__ == "__main__":
    parse_wat_schedule()
