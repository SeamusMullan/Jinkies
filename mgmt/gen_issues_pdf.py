#!/usr/bin/env python3
"""Generate a PDF table of all Jinkies GitHub issues sorted by priority."""

import json
import subprocess
from fpdf import FPDF

# Fetch issues from GitHub
result = subprocess.run(
    ["gh", "issue", "list", "--repo", "SeamusMullan/Jinkies", "--state", "open",
     "--limit", "100", "--json", "number,title,labels"],
    capture_output=True, text=True, check=True
)
issues = json.loads(result.stdout)

def sanitize(text):
    """Replace Unicode chars that core PDF fonts can't handle."""
    return (text
        .replace("\u2014", " - ")   # em dash
        .replace("\u2013", "-")     # en dash
        .replace("\u2018", "'")     # left single quote
        .replace("\u2019", "'")     # right single quote
        .replace("\u201c", '"')     # left double quote
        .replace("\u201d", '"')     # right double quote
        .replace("\u2026", "...")   # ellipsis
        .replace("\u2192", "->")   # arrow
    )

# Extract priority and label info
rows = []
for issue in issues:
    labels = [l["name"] for l in issue.get("labels", [])]
    priority = next((l for l in labels if l.startswith("P")), "none")
    other_labels = ", ".join(l for l in labels if not l.startswith("P"))
    rows.append({
        "priority": priority,
        "number": issue["number"],
        "title": sanitize(issue["title"]),
        "labels": other_labels,
    })

# Sort by priority then number
priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "none": 4}
rows.sort(key=lambda r: (priority_order.get(r["priority"], 99), r["number"]))


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Jinkies - Open Issues", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, f"{len(rows)} issues sorted by priority", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


pdf = PDF(orientation="L", format="A4")
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# Column widths (landscape A4 ~= 277mm usable)
col_w = {"priority": 18, "number": 14, "title": 175, "labels": 70}
header_labels = {"priority": "Priority", "number": "#", "title": "Title", "labels": "Labels"}

def draw_header():
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for key in ["priority", "number", "title", "labels"]:
        pdf.cell(col_w[key], 7, header_labels[key], border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

# Priority colors
priority_colors = {
    "P0": (220, 53, 69),
    "P1": (255, 140, 0),
    "P2": (255, 193, 7),
    "P3": (108, 117, 125),
    "none": (200, 200, 200),
}

draw_header()

for i, row in enumerate(rows):
    # Check if we need a new page
    if pdf.get_y() > 180:
        pdf.add_page()
        draw_header()

    bg = (245, 245, 245) if i % 2 == 0 else (255, 255, 255)
    pdf.set_fill_color(*bg)
    pdf.set_font("Helvetica", "B", 8)

    # Priority cell with color badge
    pc = priority_colors.get(row["priority"], (200, 200, 200))
    pdf.set_fill_color(*pc)
    pdf.set_text_color(255, 255, 255) if row["priority"] in ("P0", "P1", "P3") else pdf.set_text_color(0, 0, 0)
    pdf.cell(col_w["priority"], 6, row["priority"], border=1, fill=True, align="C")
    pdf.set_text_color(0, 0, 0)

    # Number
    pdf.set_fill_color(*bg)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(col_w["number"], 6, str(row["number"]), border=1, fill=True, align="C")

    # Title - truncate if needed
    title = row["title"]
    pdf.set_font("Helvetica", "", 7.5)
    if pdf.get_string_width(title) > col_w["title"] - 2:
        while pdf.get_string_width(title + "...") > col_w["title"] - 2 and len(title) > 10:
            title = title[:-1]
        title += "..."
    pdf.cell(col_w["title"], 6, title, border=1, fill=True)

    # Labels
    pdf.set_font("Helvetica", "I", 7)
    labels_text = row["labels"]
    if pdf.get_string_width(labels_text) > col_w["labels"] - 2:
        while pdf.get_string_width(labels_text + "...") > col_w["labels"] - 2 and len(labels_text) > 5:
            labels_text = labels_text[:-1]
        labels_text += "..."
    pdf.cell(col_w["labels"], 6, labels_text, border=1, fill=True)
    pdf.ln()

# Summary section
pdf.ln(6)
pdf.set_font("Helvetica", "B", 10)
pdf.cell(0, 7, "Summary", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 9)

from collections import Counter
pc = Counter(r["priority"] for r in rows)
for p in ["P0", "P1", "P2", "P3", "none"]:
    if pc[p]:
        color = priority_colors.get(p, (0,0,0))
        pdf.set_fill_color(*color)
        pdf.cell(10, 5, "", border=1, fill=True)
        pdf.set_fill_color(255, 255, 255)
        pdf.cell(60, 5, f"  {p}: {pc[p]} issues", new_x="LMARGIN", new_y="NEXT")

import os
outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jinkies-issues.pdf")
pdf.output(outpath)
print(f"PDF saved to {outpath}")
