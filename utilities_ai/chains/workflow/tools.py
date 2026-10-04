"""Tools for workflow graph interaction and user communication.

This module provides LangChain-based tools for workflow graphs to request
additional information from users when input is incomplete or insufficient.
Tools are registered with the workflow graph and invoked during execution
via tool-use instructions from the language model.

Note:
    State management for tool invocation may require modifications in future
    versions to support more complex workflow patterns.

Example:
    >>> from utilities_ai.chains.workflow.tools import request_missing_info
    >>> messages = request_missing_info("Please provide your email address.")
"""

from enum import Enum

from langchain.tools import tool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import interrupt


class ToolsNames(Enum):
    """Enumeration of available tool names for workflow graphs.

    Attributes:
        MISSING_INPUT_INFO: Tool name for requesting missing information from users.
    """

    MISSING_INPUT_INFO = "request_missing_info"


@tool(
    ToolsNames.MISSING_INPUT_INFO.value,
    description="Request more information from the user in case their input is missing important information or is simply not enough.",
)
def request_missing_info(information_request: str) -> list[BaseMessage]:
    """Request additional information from the user via an interrupt.

    Pauses workflow execution and prompts the user for more information when
    the language model detects gaps or insufficient details in the provided input.
    The function suspends execution using LangGraph's interrupt mechanism,
    allowing the user to respond before resuming the workflow.

    Args:
        information_request: The message to display to the user requesting
            additional information.

    Returns:
        A list of two `BaseMessage` objects: the assistant's information request
        (`AIMessage`) followed by the user's response (`HumanMessage`).

    Example:
        >>> messages = request_missing_info("Please provide more details about your project.")
        >>> assert len(messages) == 2
        >>> assert isinstance(messages[0], AIMessage)
        >>> assert isinstance(messages[1], HumanMessage)
    """

    # TODO: Might have to modify how state management is done here.
    information_response = interrupt(information_request)
    final_response = [AIMessage(content=information_request), HumanMessage(content=information_response)]
    return final_response
