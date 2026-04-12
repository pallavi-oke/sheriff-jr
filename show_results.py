"""
Usage:
  python show_results.py
  python show_results.py path/to/results.csv
"""

import csv
import sys

from rich.console import Console
from rich.table import Table
from rich import box

VERDICT_COLORS = {
    "clean": "green",
    "at_risk": "yellow",
    "likely_violation": "red",
}

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "results.csv"

    try:
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except FileNotFoundError:
        Console().print(f"[red]File not found:[/red] {path}")
        sys.exit(1)

    console = Console()

    table = Table(
        title=f"Sheriff Jr. — {path}",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold white",
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Ad", min_width=20, max_width=60)
    table.add_column("Verdict", min_width=18, no_wrap=True)
    table.add_column("Summary", min_width=40)
    table.add_column("Issues", justify="center", width=7)

    for i, row in enumerate(rows, start=1):
        ad = row.get("ad", "")
        if len(ad) > 60:
            ad = ad[:57] + "..."

        verdict = row.get("verdict", "")
        color = VERDICT_COLORS.get(verdict, "white")
        verdict_cell = f"[{color}]{verdict}[/{color}]"

        summary = row.get("summary", "")
        issue_count = row.get("issue_count", "")
        error = row.get("error", "")
        if error:
            summary = f"[dim red]{error}[/dim red]"
            issue_count = "[dim]—[/dim]"

        table.add_row(str(i), ad, verdict_cell, summary, issue_count)

    console.print(table)
    console.print(f"[dim]{len(rows)} row(s)[/dim]")


if __name__ == "__main__":
    main()
