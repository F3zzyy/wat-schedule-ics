import collections
import collections.abc
collections.Mapping = collections.abc.Mapping

import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIME_MAP = {
    "1-2": ("08:00", "09:35"),
    "3-4": ("09:50", "11:25"),
    "5-6": ("11:40", "13:15"),
    "7-8": ("13:30", "15:05"),
    "9-10": ("16:00", "17:35"),
    "11-12": ("17:50", "19:25"),
    "13-14": ("20:30", "21:15"),
}

MONTH_MAP = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}

# ---- CONFIG (you change this only when semester changes) ----
semester = "lato"          # later you will switch this to "zima"
group = "WEL24EL2S0"
filename = f"{group}_{semester}.ics"
# -------------------------------------------------------------


def format_cell_text(cell):
    """
    Preserves original line breaks and exact spacing.
    Ensures labels, rooms, and names stay on separate lines.
    """
    lines = [line.strip() for line in cell.get_text("\n").split("\n") if line.strip()]
    return "\n".join(lines)


def parse_wat_schedule():
    url = f"https://plany.wel.wat.edu.pl/{semester}/{group}.htm"

    response = requests.get(url, verify=False, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table")

    c = Calendar()
    current_dates = []

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # 1. Date Header Row: Extract dates and shift them +7 days
        first_cell_text = cells[0].get_text(strip=True).lower()
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

        # 2. Lecture Row: Apply multi-line formatting
        if first_cell_text in TIME_MAP:
            start_t, end_t = TIME_MAP[first_cell_text]
            for i, cell in enumerate(cells[2:]):
                cell_content = format_cell_text(cell)
                if cell_content and i < len(current_dates):
                    e = Event()
                    e.name = cell_content
                    e.begin = current_dates[i].strftime(f"%Y-%m-%d {start_t}:00")
                    e.end = current_dates[i].strftime(f"%Y-%m-%d {end_t}:00")
                    c.events.add(e)

    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(c.serialize_iter())

    print(f"✨ Generated {len(c.events)} events into {filename}.")
    print("📅 Dates shifted by 1 week. First lectures now start on 02.03.")


if __name__ == "__main__":
    parse_wat_schedule()

