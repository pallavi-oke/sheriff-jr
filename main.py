"""
Sheriff Jr. — CLI entry point.

Subcommands:
  check  — review a single ad / keyword / landing page
  batch  — review every row in a CSV file

Examples:
  python main.py check --ad "Buy cheap Xanax online — lowest prices guaranteed!"
  python main.py check --keyword "payday loans" --landing-page https://example.com
  python main.py batch --input examples/sample_ads.csv --output results.csv
  python main.py batch --input examples/sample_ads.csv --output results.csv --limit 3
"""

import csv
import json
import sys
from typing import Dict

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from agent import review

console = Console()

VERDICT_STYLES: Dict[str, tuple] = {
    "likely_violation": ("red", "LIKELY VIOLATION"),
    "at_risk": ("yellow", "AT RISK"),
    "clean": ("green", "CLEAN"),
}


# ---------------------------------------------------------------------------
# Shared rendering helper
# ---------------------------------------------------------------------------

def _render_report(result: dict) -> None:
    verdict = result.get("overall_verdict", "unknown")
    summary = result.get("summary", "")
    issues = result.get("issues", [])

    color, label = VERDICT_STYLES.get(verdict, ("white", verdict.upper()))

    console.print(
        Panel(
            f"[bold {color}]{label}[/bold {color}]\n{summary}",
            title="[bold]Sheriff Jr. Compliance Report[/bold]",
            border_style=color,
        )
    )

    if not issues:
        console.print(f"\n[{color}]No policy issues detected.[/{color}]\n")
        return

    table = Table(
        title=f"{len(issues)} issue(s) found",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold white",
    )
    table.add_column("Policy", style="cyan", no_wrap=True, min_width=20)
    table.add_column("Offending Text", style="white", min_width=20)
    table.add_column("Sev.", justify="center", min_width=5)
    table.add_column("Explanation", style="white", min_width=30)
    table.add_column("Suggested Rewrite", style="green", min_width=30)

    severity_colors = {"high": "red", "medium": "yellow", "low": "blue"}

    for issue in issues:
        sev = issue.get("severity", "low")
        sev_color = severity_colors.get(sev, "white")
        table.add_row(
            issue.get("policy", ""),
            issue.get("offending_text", ""),
            f"[{sev_color}]{sev.upper()}[/{sev_color}]",
            issue.get("explanation", ""),
            issue.get("suggested_rewrite", ""),
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Sheriff Jr. — ad compliance reviewer for Google Ads and Microsoft Advertising."""


# ---------------------------------------------------------------------------
# check subcommand  (was the top-level command)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--ad", default=None, help="Ad headline and/or body text.")
@click.option("--keyword", default=None, help="Search keyword being bid on.")
@click.option("--landing-page", default=None, help="URL of the destination page.")
@click.option(
    "--json-out",
    is_flag=True,
    default=False,
    help="Print raw JSON to stdout instead of the formatted report.",
)
def check(ad, keyword, landing_page, json_out):
    """Review a single ad, keyword, or landing page."""
    if not any([ad, keyword, landing_page]):
        console.print(
            "[red]Error:[/red] Provide at least one of --ad, --keyword, or --landing-page."
        )
        sys.exit(1)

    console.print("[dim]Running compliance review…[/dim]\n")

    try:
        result = review(ad=ad, keyword=keyword, landing_page=landing_page)
    except Exception as exc:
        console.print(f"\n[red bold]Error:[/red bold] {exc}")
        sys.exit(1)

    if json_out:
        print(json.dumps(result, indent=2))
    else:
        _render_report(result)


# ---------------------------------------------------------------------------
# batch subcommand
# ---------------------------------------------------------------------------

OUTPUT_FIELDNAMES = [
    "ad", "keyword", "landing_page",
    "verdict", "summary", "issue_count", "issues_json", "error",
]


@cli.command()
@click.option(
    "--input", "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="CSV file with columns: ad, keyword, landing_page.",
)
@click.option(
    "--output", "output_path",
    required=True,
    type=click.Path(dir_okay=False),
    help="Path to write the results CSV.",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Process only the first N rows (useful for testing).",
)
def batch(input_path, output_path, limit):
    """Review every row in a CSV file and write results to another CSV."""

    # Read all input rows upfront so we know the total for the progress bar.
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if limit is not None:
        rows = rows[:limit]

    total = len(rows)
    if total == 0:
        console.print("[yellow]Input CSV is empty — nothing to process.[/yellow]")
        sys.exit(0)

    console.print(f"[dim]Batch review: {total} row(s) from [bold]{input_path}[/bold][/dim]\n")

    counts = {"clean": 0, "at_risk": 0, "likely_violation": 0, "error": 0}

    with open(output_path, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Reviewing…", total=total)

            for i, row in enumerate(rows, start=1):
                ad_val = row.get("ad", "").strip() or None
                kw_val = row.get("keyword", "").strip() or None
                lp_val = row.get("landing_page", "").strip() or None

                # Update description with a truncated preview of the current ad.
                preview = (ad_val or kw_val or lp_val or "row")[:50]
                progress.update(task, description=f"[{i}/{total}] {preview}")

                out_row = {
                    "ad": ad_val or "",
                    "keyword": kw_val or "",
                    "landing_page": lp_val or "",
                    "verdict": "",
                    "summary": "",
                    "issue_count": "",
                    "issues_json": "",
                    "error": "",
                }

                if not any([ad_val, kw_val, lp_val]):
                    out_row["error"] = "Row has no ad, keyword, or landing_page — skipped."
                    counts["error"] += 1
                else:
                    try:
                        result = review(ad=ad_val, keyword=kw_val, landing_page=lp_val)
                        verdict = result.get("overall_verdict", "unknown")
                        out_row["verdict"] = verdict
                        out_row["summary"] = result.get("summary", "")
                        issues = result.get("issues", [])
                        out_row["issue_count"] = str(len(issues))
                        out_row["issues_json"] = json.dumps(issues)
                        counts[verdict] = counts.get(verdict, 0) + 1
                    except Exception as exc:
                        out_row["error"] = str(exc)
                        counts["error"] += 1

                writer.writerow(out_row)
                out_fh.flush()  # write incrementally so partial results survive a crash
                progress.advance(task)

    # Final summary panel.
    color_map = {"clean": "green", "at_risk": "yellow", "likely_violation": "red"}
    parts = [f"Processed [bold]{total}[/bold] ad(s):"]
    for verdict in ("clean", "at_risk", "likely_violation"):
        n = counts[verdict]
        c = color_map[verdict]
        label = VERDICT_STYLES[verdict][1]
        parts.append(f"  [{c}]{n} {label}[/{c}]")
    if counts["error"]:
        parts.append(f"  [dim]{counts['error']} ERROR(s)[/dim]")
    parts.append(f"\nResults written to [bold]{output_path}[/bold]")

    console.print(
        Panel(
            "\n".join(parts),
            title="[bold]Batch Complete[/bold]",
            border_style="blue",
        )
    )


if __name__ == "__main__":
    cli()
