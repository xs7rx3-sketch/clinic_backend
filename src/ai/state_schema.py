from typing import Any, Optional, TypedDict
from langchain_core.messages import BaseMessage

from src.ai.enums import NodeName


class AIInputSchema(TypedDict, total=False):
    query: str
    user_data: dict[str, Any]
    messages: list[BaseMessage]


class AIOverallSchema(TypedDict, total=False):
    query: str
    user_data: dict[str, Any]
    messages: list[BaseMessage]
    next_node: NodeName
    node_input: dict[str, Any]
    node_output: Optional[dict[str, Any]]
    answer: Optional[str]


class AIOutputSchema(TypedDict, total=False):
    answer: str
    messages: list[BaseMessage]
