"""Console output helpers, so the run narrates itself as it goes."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

console = Console()


def step(number: int, title: str, *, model: str | None = None) -> None:
    """Print a step banner. Showing the model makes per-step routing visible."""
    suffix = f"  [dim]({model})[/dim]" if model else ""
    console.print(Rule(f"[bold cyan]Step {number}[/bold cyan] — {title}{suffix}"))


def panel(title: str, body: str, *, markdown: bool = True) -> None:
    """Print a titled panel of model output."""
    content = Markdown(body) if markdown else body
    console.print(Panel(content, title=title, border_style="cyan", padding=(1, 2)))
