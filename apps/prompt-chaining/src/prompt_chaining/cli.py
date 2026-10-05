"""Command-line entry point."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import typer
from langgraph.types import Command

from prompt_chaining.console import console, panel
from prompt_chaining.graph import ChainConfig, build_graph, initial_state

app = typer.Typer(
    add_completion=False,
    help="Turn a raw topic into a finished blog post through a chain of small prompts.",
)

DEFAULT_TOPIC = "Why Python developers should learn Rust"


@app.command()
def main(
    topic: Annotated[
        str, typer.Option("--topic", "-t", help="What the post is about.")
    ] = DEFAULT_TOPIC,
    language: Annotated[str, typer.Option(help="Language to write the post in.")] = "English",
    words: Annotated[int, typer.Option(help="Target words per section.")] = 200,
    sections: Annotated[int, typer.Option(help="How many sections to plan.")] = 5,
    review: Annotated[
        bool, typer.Option("--review/--no-review", help="Pause for human approval of the outline.")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write the finished post here.")
    ] = None,
) -> None:
    """Run the chain end to end."""
    graph = build_graph(
        ChainConfig(min_headings=sections, max_headings=sections, human_review=review)
    )
    state = initial_state(topic, language=language, words_per_section=words)
    run_config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 50}

    result = graph.invoke(state, config=run_config)

    # With `--review` the graph stops inside `review()` and hands control back here. Each
    # resume runs it forward until the next interrupt, or to the end.
    while interrupts := result.get("__interrupt__"):
        payload = interrupts[0].value
        console.print(f"\n[bold]{payload['question']}[/bold]")
        answer = typer.prompt(
            "Press Enter to approve, or type what to change", default="", show_default=False
        ).strip()
        resume = {"feedback": answer} if answer else {"approved": True}
        result = graph.invoke(Command(resume=resume), config=run_config)

    post = result.get("post", "")
    panel("Finished post", post)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(post + "\n", encoding="utf-8")
        console.print(f"[green]Written to[/green] {output}")


if __name__ == "__main__":
    app()
