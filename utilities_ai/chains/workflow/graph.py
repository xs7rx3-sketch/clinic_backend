"""Foundation classes for building agentic workflows with LLM chains and graph-based state management.

This module provides base classes for constructing chains that integrate language models with
LangChain and LangGraph. It handles LLM configuration, model initialization, and graph
compilation with optional persistence via memory checkpointers.

The `Chain` class manages core LLM instantiation and configuration, while `LangGraph`
extends this to support stateful, multi-step workflows using LangGraph's state graph
abstraction. `LangChain` provides a simpler interface for non-graph-based chains.

Note:
    All classes require an API key for the LLM provider. This can be passed explicitly
    or retrieved from the `LLM_API_KEY` environment variable. If neither is provided,
    a `ConfigurationError` is raised.

Example:
    >>> from chains.workflow.graph import LangGraph
    >>> class MyWorkflow(LangGraph):
    ...     def _graph(self, checkpointer):
    ...         # Build your graph here
    ...         return compiled_graph
    >>> workflow = MyWorkflow()
    >>> await workflow.setup()
    >>> state = await workflow.get_state(thread_id="user_123")
"""

import os
from abc import abstractmethod
from pathlib import Path
from typing import Optional

from IPython.display import Image, display
from langchain.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from ..._logger import log as _log
from ...exceptions import ConfigurationError
from ...messages.exceptions import abstraction_exception, undefined_param
from ...messages.warnings import missing_env_var
from ..defaults import OPENAI_BASE_URL, OPENAI_MODEL_NAME, OPENAI_MODEL_TEMPERATURE
from ..exceptions import ChainConfigurationError, ChainTypeError
from ..helpers.time_operations import current_time_unix
from .memory import MemoryTypes, init_checkpointer


class Chain:
    """Base class for LLM chains with configurable model initialization.

    Handles instantiation of language models with support for custom model classes,
    temperature tuning, and endpoint configuration. The LLM instance is stored
    as `self.llm` and ready for use immediately after initialization.

    Attributes:
        model: The language model class to instantiate (e.g., `ChatOpenAI`).
        model_name: The name or identifier of the model (e.g., "gpt-4").
        temperature: Sampling temperature controlling response randomness.
        base_url: Base URL for the LLM API endpoint.
        llm: Instantiated language model ready for inference.
    """

    def __init__(
        self,
        model: Optional[type[BaseChatModel]] = None,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """Initialize a Chain with language model configuration.

        Args:
            model: Language model class to instantiate. Defaults to `ChatOpenAI`.
            model_name: The model identifier to use (e.g., "gpt-4-turbo").
                Defaults to `OPENAI_MODEL_NAME`.
            temperature: Sampling temperature between 0.0 and 2.0, controlling
                response randomness. Defaults to `OPENAI_MODEL_TEMPERATURE`.
            base_url: Base URL for the LLM API endpoint. Defaults to
                `OPENAI_BASE_URL`.
            api_key: API key for the language model provider. If not provided,
                retrieved from the `LLM_API_KEY` environment variable.
            **kwargs: Additional keyword arguments passed to the model class.

        Raises:
            ConfigurationError: If no `api_key` is provided and the `LLM_API_KEY`
                environment variable is not set.

        Example:
            >>> chain = Chain(model_name="gpt-4", temperature=0.7)
            >>> response = chain.llm.invoke("Hello")
        """
        self.model = model if model is not None else ChatOpenAI
        self.model_name = model_name if model_name is not None else OPENAI_MODEL_NAME
        self.temperature = temperature if temperature is not None else OPENAI_MODEL_TEMPERATURE
        self.base_url = base_url if base_url is not None else OPENAI_BASE_URL

        if not api_key:
            api_key = os.environ.get("LLM_API_KEY")
            if not api_key:
                raise ConfigurationError(undefined_param.format(name="LLM API key", param="LLM_API_KEY"))
        else:
            _log.warning(missing_env_var.format(name="LLM API key"))

        self.llm = self.model(model=self.model_name, api_key=api_key, temperature=temperature, base_url=base_url, **kwargs)  # type: ignore


class LangGraph(Chain):
    """Stateful, multi-step workflow orchestration using LangGraph state graphs.

    Extends `Chain` to support complex, multi-step agentic workflows with graph-based
    state management. Graphs can be persisted across thread IDs using optional
    checkpointers (in-memory or PostgreSQL), enabling multi-turn conversations and
    stateful agent interactions.

    Subclasses must implement `_graph()` to define the workflow topology and
    return a compiled state graph. The graph is compiled and stored in `llm_graph`
    upon calling `setup()`.

    Attributes:
        llm_graph: The compiled LangGraph state graph. Set to `None` until `setup()`
            is called.

    Example:
        >>> class MyAgent(LangGraph):
        ...     def _graph(self, checkpointer):
        ...         graph_builder = StateGraph(State)
        ...         # Add nodes and edges here
        ...         return graph_builder.compile(checkpointer=checkpointer)
        >>> agent = MyAgent()
        >>> await agent.setup()
        >>> state = await agent.get_state("thread_123")
    """

    def __init__(
        self,
        model: Optional[type[BaseChatModel]] = None,
        *,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """Initialize a LangGraph workflow with language model configuration.

        Args:
            model: Language model class to instantiate. Defaults to `ChatOpenAI`.
            model_name: The model identifier to use (e.g., "gpt-4-turbo").
                Defaults to `OPENAI_MODEL_NAME`.
            temperature: Sampling temperature between 0.0 and 2.0, controlling
                response randomness. Defaults to `OPENAI_MODEL_TEMPERATURE`.
            base_url: Base URL for the LLM API endpoint. Defaults to
                `OPENAI_BASE_URL`.
            api_key: API key for the language model provider. If not provided,
                retrieved from the `LLM_API_KEY` environment variable.
            **kwargs: Additional keyword arguments passed to the language model.

        Raises:
            ConfigurationError: If no `api_key` is provided and the `LLM_API_KEY`
                environment variable is not set.
        """
        super().__init__(model=model, model_name=model_name, temperature=temperature, base_url=base_url, api_key=api_key, **kwargs)
        self.llm_graph: Optional[CompiledStateGraph] = None

    def draw_graph_flowchart(self, graph: Optional[CompiledStateGraph] = None, *, prefix: str = "graph") -> None:
        """Generate and display a Mermaid flowchart diagram of the graph structure.

        Renders a visual representation of the graph topology using Mermaid syntax
        and displays it as a PNG image. The image is saved to the current working
        directory with a timestamped filename.

        Args:
            graph: The compiled state graph to visualize. If not provided, uses
                `self.llm_graph`. Defaults to `None`.
            prefix: Filename prefix for the saved PNG. Defaults to "graph".

        Raises:
            ChainConfigurationError: If no graph is provided and `self.llm_graph`
                has not been initialized via `setup()`.
            ChainTypeError: If the provided `graph` is not a compiled state graph.

        Example:
            >>> workflow = MyAgent()
            >>> await workflow.setup()
            >>> workflow.draw_graph_flowchart()
        """
        if not graph:
            if self.llm_graph is None:
                raise ChainConfigurationError(
                    "You must setup the graph using `setup()` before calling `draw_graph_flowchart()` method, or provide a compiled graph manually to the method."
                )
            graph = self.llm_graph

        if not isinstance(graph, CompiledStateGraph):
            raise ChainTypeError("`graph` parameter was given an invalid data type.\nA compiled graph must be provided.")

        file_name = f"{prefix}_{current_time_unix()}.png"
        file_path = os.path.join(Path.cwd(), file_name)
        display(Image(graph.get_graph().draw_mermaid_png(output_file_path=file_path)))  # type: ignore

    async def get_state(self, thread_id: str) -> dict:
        """Retrieve the current state of a workflow execution thread.

        Fetches the latest checkpoint state for a given thread ID, enabling
        inspection of workflow progress, current values, and multi-turn context.

        Args:
            thread_id: The unique identifier for the workflow execution thread.

        Returns:
            A dictionary containing the current state values of the workflow.

        Raises:
            ChainConfigurationError: If `self.llm_graph` has not been initialized
                via `setup()`.

        Example:
            >>> state = await workflow.get_state("user_123")
            >>> print(state["messages"])
        """
        if self.llm_graph is None:
            raise ChainConfigurationError("You must setup the graph using `setup()` before calling `get_state()` method.")

        state = await self.llm_graph.aget_state({"configurable": {"thread_id": thread_id}})  # type: ignore
        return state.values

    async def setup(self, *, memory: MemoryTypes = None, postgres_uri: Optional[str] = None) -> None:
        """Compile and initialize the graph with optional persistence via checkpointers.

        This method constructs the final compiled state graph by calling `_graph()`
        and initializes the persistence layer (checkpointer). Must be called before
        accessing or executing the graph through `self.llm_graph`.

        Args:
            memory: Name of the memory checkpointer to use (e.g., "in_memory",
                "postgres"). If `None`, no persistence is configured. Defaults to `None`.
            postgres_uri: PostgreSQL connection string for persistent state storage.
                Only used if `memory` is set to "postgres". Defaults to `None`.

        Example:
            >>> workflow = MyAgent()
            >>> await workflow.setup(memory="in_memory")
            >>> # Now workflow.llm_graph is ready to use
        """
        checkpointer = await init_checkpointer(memory, postgres_uri=postgres_uri)
        self.llm_graph = self._graph(checkpointer=checkpointer)

    @abstractmethod
    def _graph(self, checkpointer: Optional[Checkpointer]) -> CompiledStateGraph:
        """Build and return the compiled state graph for this workflow.

        Subclasses must implement this method to define the graph topology, including
        nodes, edges, and entry/exit points. The checkpointer is optionally configured
        for state persistence across thread executions.

        Args:
            checkpointer: Optional persistence layer for checkpoint storage.
                If `None`, the graph will have no state persistence.

        Returns:
            A compiled LangGraph state graph ready for execution.

        Raises:
            NotImplementedError: Always, as this is an abstract method that subclasses
                must override.

        Example:
            >>> def _graph(self, checkpointer):
            ...     graph = StateGraph(State)
            ...     graph.add_node("process", self.process_node)
            ...     graph.add_edge("__start__", "process")
            ...     return graph.compile(checkpointer=checkpointer)
        """
        raise NotImplementedError(abstraction_exception)


class LangChain(Chain):
    """Simple, stateless LLM chain without graph-based state management.

    Inherits from `Chain` to provide basic language model integration without
    the complexity of graph-based workflows. Suitable for straightforward
    single-turn or simple multi-turn interactions without persistent state.
    """

    pass
