"""Structured shapes passed between links in the chain.

The outline is the contract between step 1 and step 2. Making it a typed object rather
than a blob of prose is what lets step 1's output be *checked* before step 2 spends
tokens writing against it -- the whole reason to split the prompts in the first place.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Heading(BaseModel):
    """One section of the planned post."""

    title: str = Field(description="The section heading, as it will appear in the post.")
    summary: str = Field(description="One sentence stating the main point of this section.")


class Outline(BaseModel):
    """The plan for the whole post."""

    headings: list[Heading] = Field(description="The main sections, in reading order.")


class WrittenSection(BaseModel):
    """A section after step 2 has written it."""

    title: str
    body: str
