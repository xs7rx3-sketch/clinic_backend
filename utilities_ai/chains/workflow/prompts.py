"""Utilities for structuring prompts into LangChain message formats.

This module provides functions for converting text prompts into properly
formatted LangChain message objects. It supports both basic prompt structuring
with optional system messages, and specialized schema-based prompting for
converting unstructured content into structured formats.

All prompts are automatically dedented and stripped of leading/trailing
whitespace before conversion to message objects.

Example:
    >>> from prompts import structure_prompt
    >>> messages = structure_prompt("What is AI?", "You are an expert.")
    >>> len(messages)
    2
    >>> messages[0].content
    'You are an expert.'
"""

from textwrap import dedent
from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


def structure_prompt(user_prompt: str, system_prompt: Optional[str] = None) -> list[BaseMessage]:
    """Structure a user prompt and optional system prompt into LangChain messages.

    Converts raw prompt strings into a list of LangChain message objects.
    Automatically dedents and strips whitespace from both prompts to handle
    multi-line string formatting cleanly.

    Args:
            user_prompt: The primary user message content.
            system_prompt: An optional system message that guides model behavior.
                    Defaults to None.

    Returns:
            A list of `BaseMessage` objects. If a system prompt is provided, the
            list contains a `SystemMessage` followed by a `HumanMessage`. Otherwise,
            only a `HumanMessage` is returned.

    Example:
            >>> messages = structure_prompt("Hello", "Be helpful.")
            >>> len(messages)
            2
            >>> type(messages[0]).__name__
            'SystemMessage'
            >>> type(messages[1]).__name__
            'HumanMessage'
    """
    prompt = []

    if system_prompt:
        prompt.append(SystemMessage(content=dedent(system_prompt).strip()))

    prompt.append(HumanMessage(content=dedent(user_prompt).strip()))
    return prompt


def structured_schema_prompt(unstructured_content: str, *, custom: Optional[str] = None) -> list[BaseMessage]:
    """Create a schema-based prompt for structuring unstructured content.

    Generates a system prompt that instructs a model to convert unstructured
    text into a structured format while preserving data integrity. The system
    prompt defines clear operational and behavioral guidelines, with support
    for appending custom instructions.

    Args:
            unstructured_content: The raw, unstructured text to be converted.
            custom: Optional additional instructions to append to the default system
                    prompt. Typically used to specify the target schema or format.
                    Defaults to None.

    Returns:
            A list of `BaseMessage` objects containing a `SystemMessage` with
            schema-conversion instructions and a `HumanMessage` with the content
            to structure.

    Example:
            >>> messages = structured_schema_prompt(
            ...     "John is 30 and lives in NYC",
            ...     custom="Convert to JSON format with 'name', 'age', 'city' keys."
            ... )
            >>> len(messages)
            2
    """
    system_prompt = f"""
    You are a helpful assistant whose only responsibility is converting a certain text to a structured output. Follow these guidelines
    strictly:

    **Operational Guidelines:**
      1. Understand the structured schema very well.
      2. Convert the user-provided content to perfectly abide-by the provided structured schema.

    **Behavioural Guidelines:**
      - Make sure you do not alter the integrity of the data when you structure the data into the provided structure schema. This is very
      important!
    """

    if custom is not None:
        system_prompt += custom

    return structure_prompt(unstructured_content, system_prompt)
