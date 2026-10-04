"""Utilities for formatting and managing LangChain message state.

Provides functions for manipulating message lists used in LangChain workflows,
including managing system messages, fixing response formats, and extracting
specific message types from a message list. These utilities ensure consistent
message ordering and structure throughout the conversation workflow.

Note:
    All functions operate on `BaseMessage` objects from LangChain. The
    `manage_system_message` and `fix_web_search_format` functions modify
    message structure, which may affect subsequent processing.

Example:
    >>> from langchain_core.messages import SystemMessage, HumanMessage
    >>> messages = [HumanMessage("Hi"), SystemMessage("You are helpful")]
    >>> formatted = manage_system_message(messages)
    >>> system_msg = fetch_system_prompt_only(formatted)
"""

from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


def manage_system_message(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Reorganize messages to ensure a single system message appears first.

    Processes a message list to ensure proper ordering: extracts the latest
    (rightmost) `SystemMessage` and places it at the beginning, followed by
    all non-system messages in their original order. This ensures the system
    prompt takes precedence and appears before any conversation history.

    Args:
        messages: A list of LangChain message objects to reorganize.

    Returns:
        A reorganized message list with the latest `SystemMessage` first,
        followed by all other messages in their original order. If no system
        message exists, the original message order (minus any system messages)
        is returned.

    Example:
        >>> from langchain_core.messages import SystemMessage, HumanMessage
        >>> messages = [
        ...     HumanMessage("What is 2+2?"),
        ...     SystemMessage("You are a math tutor"),
        ... ]
        >>> result = manage_system_message(messages)
        >>> isinstance(result[0], SystemMessage)
        True
    """
    formatted_messages = []

    # Scan backwards through messages to find the latest system message
    for message in messages[::-1]:
        if isinstance(message, SystemMessage):
            formatted_messages.append(message)
            break

    # Append all non-system messages in their original order
    for message in messages:
        if isinstance(message, SystemMessage):
            continue
        formatted_messages.append(message)

    return formatted_messages


def fix_web_search_format(ai_response: AIMessage) -> AIMessage:
    """Normalize AI response format when web search is used.

    When ChatGPT uses web search, it returns a nested structure containing
    search results. This function extracts the text content from this nested
    format and returns a standard `AIMessage` with the content as a string.
    If the response is already a string (no web search), it is returned
    unchanged.

    Note:
        Currently does not support multi-tool calling. If the AI response
        contains multiple tool results, only the last result's text is
        extracted.

    Args:
        ai_response: An `AIMessage` from the AI that may have used web search.

    Returns:
        An `AIMessage` with string content. If the input was already a string,
        the same message is returned. If nested (from web search), the text
        is extracted and wrapped in a new `AIMessage`.

    Example:
        >>> from langchain_core.messages import AIMessage
        >>> nested_response = AIMessage(
        ...     content=[{"text": "Search result: 2+2=4"}]
        ... )
        >>> fixed = fix_web_search_format(nested_response)
        >>> isinstance(fixed.content, str)
        True
    """
    content = ai_response.content
    if isinstance(content, str):
        return ai_response

    # Extract text from the last item in the nested structure
    content = cast(list, content)[-1]["text"]
    fixed_response = AIMessage(content=content)
    return fixed_response


def fetch_system_prompt_only(prompt: list[BaseMessage], *, last: bool = False) -> SystemMessage:
    """Extract a single system message from a message list.

    Scans the provided message list and returns either the first or last
    `SystemMessage` found, depending on the `last` parameter.

    Args:
        prompt: A list of LangChain messages to search through.
        last: If `True`, returns the last `SystemMessage`. If `False`
            (default), returns the first one. Defaults to False.

    Returns:
        The matched `SystemMessage`.

    Raises:
        IndexError: If no `SystemMessage` is found in the list.

    Example:
        >>> from langchain_core.messages import SystemMessage, HumanMessage
        >>> messages = [
        ...     SystemMessage("Be concise"),
        ...     HumanMessage("Hi"),
        ... ]
        >>> sys_msg = fetch_system_prompt_only(messages)
        >>> sys_msg.content
        'Be concise'
    """
    system_messages = [p for p in prompt if isinstance(p, SystemMessage)]

    if last:
        return system_messages[-1]
    return system_messages[0]


def fetch_user_prompt_only(prompt: list[BaseMessage], *, last: bool = True) -> HumanMessage:
    """Extract a single human message from a message list.

    Scans the provided message list and returns either the first or last
    `HumanMessage` found, depending on the `last` parameter.

    Args:
        prompt: A list of LangChain messages to search through.
        last: If `True` (default), returns the last `HumanMessage`. If `False`,
            returns the first one. Defaults to True.

    Returns:
        The matched `HumanMessage`.

    Raises:
        IndexError: If no `HumanMessage` is found in the list.

    Example:
        >>> from langchain_core.messages import HumanMessage, AIMessage
        >>> messages = [
        ...     HumanMessage("What's the weather?"),
        ...     AIMessage("It's sunny"),
        ... ]
        >>> user_msg = fetch_user_prompt_only(messages)
        >>> user_msg.content
        "What's the weather?"
    """
    human_messages = [p for p in prompt if isinstance(p, HumanMessage)]

    if last:
        return human_messages[-1]
    return human_messages[0]
