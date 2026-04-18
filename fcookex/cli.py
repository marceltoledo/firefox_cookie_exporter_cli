"""CLI entry-point for fcookex."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from InquirerPy import inquirer
from rich import print as rprint
from rich.table import Table

from . import exporter, finder, reader
from .finder import ProfileNotFoundError

app = typer.Typer(add_completion=False, help="Export Firefox cookies to Netscape format.")

_MASKED = "***"
_EXPORT_DIR = Path("export")


def _validate_output_name(name: str) -> str:
    """Reject names that contain path separators or traversal sequences."""
    if "/" in name or "\\" in name or ".." in name:
        raise typer.BadParameter(
            f"--output must be a bare filename with no path components, got: {name!r}"
        )
    return name


def _mask_cookies(cookies: list[reader.Cookie]) -> list[reader.Cookie]:
    """Return a copy of *cookies* with values replaced by ``***``."""
    from dataclasses import replace

    return [replace(c, value=_MASKED) for c in cookies]


def _resolve_real(
    selected_masked: list[reader.Cookie],
    all_masked: list[reader.Cookie],
    all_real: list[reader.Cookie],
) -> list[reader.Cookie]:
    """Map display-layer masked cookies back to their real counterparts by index."""
    index_map = {id(m): real for m, real in zip(all_masked, all_real)}
    return [index_map[id(m)] for m in selected_masked]


def _render_table(cookies: list[reader.Cookie]) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Host", style="dim")
    table.add_column("Name")
    table.add_column("Value")
    for c in cookies:
        table.add_row(c.host, c.name, c.value)
    rprint(table)


@app.command()
def main(
    search: Annotated[str, typer.Option("--search", "-s", help="Filter by host, name, or value.")],
    profile: Annotated[
        Optional[str],
        typer.Option("--profile", "-p", help="Firefox profile name. Defaults to the default profile."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output filename (no path). Extension .txt is added if absent."),
    ] = None,
    append: Annotated[bool, typer.Option("--append", "-a", help="Append to existing file instead of overwriting.")] = False,
    show_values: Annotated[bool, typer.Option("--show-values", help="Reveal cookie values in the selection list.")] = False,
) -> None:
    # --- Validate --output before doing any work ---
    if output is not None:
        _validate_output_name(output)

    # --- Value visibility warning / confirmation ---
    if show_values:
        confirmed = typer.confirm(
            "Warning: cookie values will be visible in your terminal. Continue?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit()
    else:
        rprint("[yellow]Cookie values are masked. Pass --show-values to reveal them.[/yellow]")

    # --- Locate and copy the cookie database ---
    try:
        db_path = finder.get_profile_db(profile)
    except ProfileNotFoundError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    tmp_db = finder.copy_to_temp(db_path)

    try:
        # --- Search ---
        cookies = reader.search_cookies(tmp_db, search)
    finally:
        tmp_db.unlink(missing_ok=True)

    if not cookies:
        rprint(f"[yellow]No cookies found matching {search!r}.[/yellow]")
        raise typer.Exit()

    # --- Build display list (masked or plain) ---
    masked_cookies = _mask_cookies(cookies)
    display_cookies = masked_cookies if not show_values else cookies

    choices = [
        {
            "name": f"{c.host:<45} {c.name:<35} {c.value}",
            "value": c,
        }
        for c in display_cookies
    ]

    selected_display: list[reader.Cookie] = inquirer.checkbox(
        message=f"Select cookies to export ({len(cookies)} found). Space = toggle, Enter = confirm:",
        choices=choices,
        instruction="(space: toggle, enter: confirm)",
    ).execute()

    if not selected_display:
        rprint("[yellow]No cookies selected. Nothing exported.[/yellow]")
        raise typer.Exit()

    # --- Recover real values from selected display cookies ---
    if show_values:
        selected_real = selected_display
    else:
        selected_real = _resolve_real(selected_display, masked_cookies, cookies)

    # --- Export ---
    out_path = exporter.export(
        selected_real,
        output_dir=_EXPORT_DIR,
        output_name=output,
        append=append,
    )

    mode_label = "Appended" if append and out_path.exists() else "Exported"
    rprint(
        f"[green]{mode_label} {len(selected_real)} cookie(s)[/green] → [bold]{out_path}[/bold]"
    )


if __name__ == "__main__":
    app()
