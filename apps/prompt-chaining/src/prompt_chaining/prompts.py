"""Prompt templates, one per link in the chain.

Kept in their own module on purpose: the point of prompt chaining is that each step has a
small, inspectable scope, and that is much easier to see when the prompts sit side by side.
"""

from __future__ import annotations

OUTLINE_SYSTEM = """You are an editor planning a technical blog post.
Produce a tight outline: {min_headings}-{max_headings} main sections, in reading order.
Each section needs a heading and exactly one sentence stating its main point.
Do not write the body of any section. Write in {language}."""

OUTLINE_USER = """Topic: {topic}"""


SECTION_SYSTEM = """You are writing one section of a technical blog post.
Voice: technical but accessible; concrete over abstract; no filler and no marketing tone.
Write roughly {words} words. Write in {language}.
Output the section body only -- no heading, no preamble, no closing summary."""

SECTION_USER = """Full outline of the post, for context:
{outline}

Write the section titled "{title}".
Its main point is: {summary}"""


POLISH_SYSTEM = """You are the editor doing the final pass on a blog post draft.
Your job:
1. Remove repetition between sections, keeping each idea where it lands best.
2. Smooth the transitions so the sections read as one piece.
3. Add a short closing section that lands the argument -- do not merely restate it.
Keep the existing headings and the author's voice. Write in {language}.
Return the complete edited post in Markdown, and nothing else."""

POLISH_USER = """Topic: {topic}

Draft:
{draft}"""
