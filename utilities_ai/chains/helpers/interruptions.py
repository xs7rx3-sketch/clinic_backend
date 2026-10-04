"""Event handlers for LangChain streaming interruptions.

Provides utilities for detecting and extracting interrupt events that occur
during LangChain streaming operations. Interrupts can originate from tool
errors or streaming chunks containing interrupt markers.

Note:
    This module is designed to work with LangChain's `StreamEvent` objects
    from `langchain_core.runnables.schema`. Interrupt event formats are
    implementation-specific and may change with LangChain versions.

Example:
    >>> from langchain_core.runnables.schema import StreamEvent
    >>> event = {...}  # StreamEvent from LangChain
    >>> if is_interrupt_event(event):
    ...     message = get_interruption_message(event)
    ...     print(f"Interrupt: {message}")
"""

from langchain_core.runnables.schema import StreamEvent


def is_interrupt_event(event: StreamEvent) -> bool:
    """Check if a stream event represents an interrupt.

    Detects whether a `StreamEvent` contains an interrupt by examining its
    string representation for the "Interrupt(value=" marker. This is a simple
    heuristic check suitable for identifying interrupt events during streaming
    operations.

    Args:
        event: A LangChain `StreamEvent` object to check.

    Returns:
        `True` if the event is an interrupt event, `False` otherwise.

    Example:
        >>> event = {"event": "on_chain_end", "data": {}}
        >>> is_interrupt_event(event)
        False
    """
    if "Interrupt(value=" in str(event):
        return True
    return False


def get_interruption_message(event: StreamEvent) -> str:
    """Extract the message from an interrupt stream event.

    Retrieves the interrupt message from a `StreamEvent`. The extraction
    path depends on the event type: `on_tool_error` events store the message
    in `error.args[0][0].value`, while chunk events store it in the interrupt
    marker at `chunk[1]["__interrupt__"][0].value`.

    Args:
        event: A LangChain `StreamEvent` object containing an interrupt.

    Returns:
        The interrupt message as a string extracted from the event.

    Raises:
        KeyError: If the expected event structure or required keys are not found.
        IndexError: If the message data is not at the expected location.
        AttributeError: If the event does not have the required attributes.

    Note:
        This function assumes the event has been validated with
        `is_interrupt_event()` first. Calling this on a non-interrupt event
        may raise an exception or return unexpected results.

    Example:
        >>> event = {
        ...     "event": "on_tool_error",
        ...     "data": {"error": Exception("Tool failed")}
        ... }
        >>> message = get_interruption_message(event)
        >>> isinstance(message, str)
        True
    """
    if event.get("event") == "on_tool_error":
        return event["data"]["error"].args[0][0].value  # type: ignore
    return event["data"]["chunk"][1]["__interrupt__"][0].value  # type: ignore
