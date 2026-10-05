"""Tests that exercise the chain's plumbing without calling a model.

The nodes that matter for correctness here -- the outline gate and the routing -- are
plain Python, so they can be tested offline. That is a large part of why they are plain
Python.
"""

from __future__ import annotations

from prompt_chaining.graph import ChainConfig, build_graph, initial_state
from prompt_chaining.models import Heading, Outline


def _outline(n: int) -> Outline:
    return Outline(
        headings=[Heading(title=f"Heading {i}", summary=f"Point {i}.") for i in range(n)]
    )


def test_initial_state_has_every_key_the_graph_reads() -> None:
    state = initial_state("Rust for Python devs")
    assert state["topic"] == "Rust for Python devs"
    assert state["cursor"] == 0
    assert state["sections"] == []


def test_graph_compiles_and_wires_every_node() -> None:
    graph = build_graph(ChainConfig())
    assert set(graph.get_graph().nodes) >= {
        "plan",
        "check_outline",
        "review",
        "write_section",
        "assemble",
        "polish",
    }


def test_check_outline_accepts_a_well_formed_outline() -> None:
    check = build_graph(ChainConfig(min_headings=4, max_headings=5)).nodes["check_outline"]
    state = initial_state("t") | {"outline": _outline(4)}
    assert check.invoke(state)["validation_error"] is None


def test_check_outline_rejects_the_wrong_number_of_headings() -> None:
    check = build_graph(ChainConfig(min_headings=4, max_headings=5)).nodes["check_outline"]
    state = initial_state("t") | {"outline": _outline(2)}
    assert "got 2" in check.invoke(state)["validation_error"]


def test_check_outline_rejects_duplicate_titles() -> None:
    check = build_graph(ChainConfig(min_headings=1, max_headings=5)).nodes["check_outline"]
    outline = Outline(
        headings=[Heading(title="Same", summary="a."), Heading(title="same", summary="b.")]
    )
    state = initial_state("t") | {"outline": outline}
    assert check.invoke(state)["validation_error"] == "two headings have the same title"


def test_assemble_joins_sections_into_markdown() -> None:
    from prompt_chaining.models import WrittenSection

    assemble = build_graph(ChainConfig()).nodes["assemble"]
    state = initial_state("t") | {
        "sections": [
            WrittenSection(title="One", body="First body."),
            WrittenSection(title="Two", body="Second body."),
        ]
    }
    draft = assemble.invoke(state)["draft"]
    assert draft == "## One\n\nFirst body.\n\n## Two\n\nSecond body."


def test_message_text_is_read_from_dot_text_not_str_content() -> None:
    """Guards the bug that shipped a Python repr into the finished post.

    Gemini returns `content` as a list of blocks where OpenAI-shaped providers return a
    plain string. `str(message.content)` stringifies that list; `.text` concatenates the
    text blocks and is right for both shapes.
    """
    from langchain_core.messages import AIMessage

    blocks = AIMessage(content=[{"type": "text", "text": "one "}, {"type": "text", "text": "two"}])
    assert blocks.text == "one two"
    assert str(blocks.content) != blocks.text

    assert AIMessage(content="plain").text == "plain"
