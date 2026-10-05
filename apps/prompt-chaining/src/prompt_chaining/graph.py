"""The chain itself: a linear LangGraph where each node is one prompt.

    plan ──▶ check ──▶ (review) ──▶ write_section ──┐
             │  ▲                        ▲          │
             │  └────── retry ───────────┘          │ more sections
             ▼                                      ▼
          warn/continue                          assemble ──▶ polish ──▶ END

Two things are worth noticing while reading it:

* `check_outline` and `assemble_draft` are plain Python. Not every node in a chain is an
  LLM call, and the cheapest way to keep a chain on the rails is to check the previous
  step's output before paying for the next one.
* Every step runs on the same model, but at a different temperature -- 0.4 for the
  outline, 0.7 for prose, 0.3 for the edit. Splitting the prompts is what makes even that
  much per-step control possible; swapping in a different *model* per step is the same
  idea taken further, and needs the gateway in the `bifrost-gateway` app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from prompt_chaining.console import console, panel, step
from prompt_chaining.llm import chat_model
from prompt_chaining.models import Heading, Outline, WrittenSection
from prompt_chaining.prompts import (
    OUTLINE_SYSTEM,
    OUTLINE_USER,
    POLISH_SYSTEM,
    POLISH_USER,
    SECTION_SYSTEM,
    SECTION_USER,
)
from prompt_chaining.settings import get_settings


class BlogState(TypedDict, total=False):
    """What flows along the edges.

    Every field a node writes is declared here; LangGraph merges each node's returned
    dict into the state, so a node only returns the keys it actually changed.
    """

    topic: str
    language: str
    words_per_section: int

    outline: Outline | None
    plan_attempts: int
    validation_error: str | None

    cursor: int
    sections: list[WrittenSection]

    draft: str
    post: str


@dataclass(frozen=True)
class ChainConfig:
    """Knobs the graph is built with, rather than passed on every invocation."""

    min_headings: int = 4
    max_headings: int = 5
    max_plan_attempts: int = 2
    human_review: bool = False


def _render_outline(outline: Outline) -> str:
    return "\n".join(f"{i}. {h.title} — {h.summary}" for i, h in enumerate(outline.headings, 1))


def build_graph(config: ChainConfig | None = None):
    """Compile the chain. Returns a LangGraph `CompiledStateGraph`."""
    cfg = config or ChainConfig()
    # Settings are read inside the nodes, not here. `Settings` requires GEMINI_API_KEY, and
    # building the graph must not: the tests compile it and drive the non-LLM nodes with no
    # credential at all, which is what keeps CI offline.

    # --- Step 1: outline -----------------------------------------------------------
    def plan(state: BlogState) -> BlogState:
        settings = get_settings()
        attempt = state.get("plan_attempts", 0) + 1
        step(1, "Outline", model=settings.model)

        messages = [
            (
                "system",
                OUTLINE_SYSTEM.format(
                    min_headings=cfg.min_headings,
                    max_headings=cfg.max_headings,
                    language=state["language"],
                ),
            ),
            ("user", OUTLINE_USER.format(topic=state["topic"])),
        ]
        # A retry is not a fresh attempt at the same prompt: the model is told what was
        # wrong with the last outline, which is the difference between a retry that
        # converges and one that loops.
        if error := state.get("validation_error"):
            messages.append(
                ("user", f"Your previous outline was rejected: {error}\nProduce a corrected one.")
            )

        # `with_structured_output` is typed as returning a dict-or-model union; the
        # Pydantic schema pins it to an `Outline` at run time.
        model = chat_model(temperature=settings.temperature_plan).with_structured_output(Outline)
        outline = cast(Outline, model.invoke(messages))

        panel("Outline", _render_outline(outline))
        return {"outline": outline, "plan_attempts": attempt, "validation_error": None}

    # --- Gate: check the outline before spending tokens on prose --------------------
    def check_outline(state: BlogState) -> BlogState:
        outline = state.get("outline")
        error: str | None = None

        if outline is None or not outline.headings:
            error = "the outline is empty"
        elif not cfg.min_headings <= len(outline.headings) <= cfg.max_headings:
            error = (
                f"expected {cfg.min_headings}-{cfg.max_headings} headings, "
                f"got {len(outline.headings)}"
            )
        elif any(not h.title.strip() or not h.summary.strip() for h in outline.headings):
            error = "every heading needs both a title and a one-sentence summary"
        else:
            titles = [h.title.strip().casefold() for h in outline.headings]
            if len(set(titles)) != len(titles):
                error = "two headings have the same title"

        return {"validation_error": error}

    def route_after_check(state: BlogState) -> Literal["plan", "review", "write_section"]:
        error = state.get("validation_error")
        if error and state.get("plan_attempts", 0) < cfg.max_plan_attempts:
            console.print(f"[yellow]Outline rejected:[/yellow] {error} — retrying step 1.")
            return "plan"
        if error:
            # Out of retries. Warn and carry on rather than throwing away the run: the
            # reader still gets a post, and the log says exactly which step went wrong.
            console.print(
                f"[yellow]Outline still imperfect after {cfg.max_plan_attempts} attempts "
                f"({error}) — continuing anyway.[/yellow]"
            )
        return "review" if cfg.human_review else "write_section"

    # --- Optional human gate --------------------------------------------------------
    def review(state: BlogState) -> BlogState:
        """Pause the graph and hand the outline to a person.

        This is the mid-chain checkpoint that a single mega-prompt cannot offer: catching
        a wrong direction here costs one cheap call, catching it after the full draft
        costs the whole run.
        """
        outline = state["outline"]
        assert outline is not None
        decision = interrupt(
            {
                "question": "Approve this outline?",
                "outline": [h.model_dump() for h in outline.headings],
            }
        )
        if isinstance(decision, dict) and (note := decision.get("feedback")):
            console.print("[yellow]Outline sent back with feedback.[/yellow]")
            return {"validation_error": f"a human reviewer said: {note}"}
        return {"validation_error": None}

    def route_after_review(state: BlogState) -> Literal["plan", "write_section"]:
        return "plan" if state.get("validation_error") else "write_section"

    # --- Step 2: write each section, one call at a time ------------------------------
    def write_section(state: BlogState) -> BlogState:
        settings = get_settings()
        outline = state["outline"]
        assert outline is not None
        cursor = state.get("cursor", 0)
        heading = outline.headings[cursor]

        step(
            2,
            f"Section {cursor + 1}/{len(outline.headings)} — {heading.title}",
            model=settings.model,
        )

        model = chat_model(temperature=settings.temperature_write)
        response = model.invoke(
            [
                (
                    "system",
                    SECTION_SYSTEM.format(
                        words=state["words_per_section"], language=state["language"]
                    ),
                ),
                (
                    "user",
                    SECTION_USER.format(
                        outline=_render_outline(outline),
                        title=heading.title,
                        summary=heading.summary,
                    ),
                ),
            ]
        )
        # `.text`, not `str(.content)`. Gemini returns content as a list of blocks
        # (`[{"type": "text", "text": ...}]`) where OpenAI-shaped providers return a plain
        # string, so stringifying `.content` silently produced a Python repr of the list.
        # `.text` concatenates the text blocks and is correct for both shapes.
        body = response.text.strip()
        panel(heading.title, body)

        return {
            "sections": [
                *state.get("sections", []),
                WrittenSection(title=heading.title, body=body),
            ],
            "cursor": cursor + 1,
        }

    def route_after_section(state: BlogState) -> Literal["write_section", "assemble"]:
        outline = state["outline"]
        assert outline is not None
        return "write_section" if state.get("cursor", 0) < len(outline.headings) else "assemble"

    # --- Assemble: no model call, just string handling -------------------------------
    def assemble(state: BlogState) -> BlogState:
        parts = [f"## {s.title}\n\n{s.body}" for s in state.get("sections", [])]
        return {"draft": "\n\n".join(parts)}

    # --- Step 3: review the whole draft ----------------------------------------------
    def polish(state: BlogState) -> BlogState:
        settings = get_settings()
        step(3, "Review & polish", model=settings.model)
        model = chat_model(temperature=settings.temperature_polish)
        response = model.invoke(
            [
                ("system", POLISH_SYSTEM.format(language=state["language"])),
                ("user", POLISH_USER.format(topic=state["topic"], draft=state["draft"])),
            ]
        )
        # `.text` for the same reason as in write_section.
        return {"post": response.text.strip()}

    graph = StateGraph(BlogState)
    graph.add_node("plan", plan)
    graph.add_node("check_outline", check_outline)
    graph.add_node("review", review)
    graph.add_node("write_section", write_section)
    graph.add_node("assemble", assemble)
    graph.add_node("polish", polish)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "check_outline")
    graph.add_conditional_edges("check_outline", route_after_check)
    graph.add_conditional_edges("review", route_after_review)
    graph.add_conditional_edges("write_section", route_after_section)
    graph.add_edge("assemble", "polish")
    graph.add_edge("polish", END)

    # A checkpointer is what makes `interrupt()` resumable, so it is only needed when the
    # human gate is switched on.
    #
    # The serializer is given an explicit allowlist because the checkpoint holds an
    # `Outline`. LangGraph's default is permissive -- it will deserialize any type it
    # finds and warns that a future version will refuse to -- so naming the three models
    # here both silences that and narrows deserialization to them plus LangGraph's own
    # safe set (builtins, langchain messages, langgraph types).
    checkpointer = (
        InMemorySaver(
            serde=JsonPlusSerializer(allowed_msgpack_modules=[Outline, Heading, WrittenSection])
        )
        if cfg.human_review
        else None
    )
    return graph.compile(checkpointer=checkpointer)


def initial_state(
    topic: str, *, language: str = "English", words_per_section: int = 200
) -> BlogState:
    """Seed state for a run."""
    return {
        "topic": topic,
        "language": language,
        "words_per_section": words_per_section,
        "outline": None,
        "plan_attempts": 0,
        "validation_error": None,
        "cursor": 0,
        "sections": [],
        "draft": "",
        "post": "",
    }
