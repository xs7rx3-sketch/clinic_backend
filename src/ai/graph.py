from typing import Optional

from langchain.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer
from utilities_ai.chains import LangGraph

from src.config import (
    MAIN_LLM_BASE_URL,
    MAIN_LLM_MODEL_NAME,
    MAIN_LLM_TEMPERATURE,
    SQL_LLM_BASE_URL,
    SQL_LLM_MODEL_NAME,
    SQL_LLM_TEMPERATURE,
)

from .enums import NodeName
from .nodes.react_nodes import ReactNodes
from .nodes.sql_nodes import SQLNodes
from .state_schema import AIInputSchema, AIOutputSchema, AIOverallSchema


class AIGraph(LangGraph):
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
        model_name = model_name or MAIN_LLM_MODEL_NAME
        temperature = temperature if temperature is not None else MAIN_LLM_TEMPERATURE
        base_url = base_url or MAIN_LLM_BASE_URL

        super().__init__(
            model=model,
            model_name=model_name,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
            **kwargs,
        )
        self._session_id: Optional[str] = None

        # SQL LLM with strict temperature 0.0 to prevent hallucinations
        try:
            sql_llm = self.llm.__class__(
                model_name=SQL_LLM_MODEL_NAME,
                temperature=SQL_LLM_TEMPERATURE,
                base_url=SQL_LLM_BASE_URL,
                api_key=api_key,
            )
        except Exception:
            sql_llm = self.llm

        # SQL Nodes contain specialized execution & prompts for each domain operation
        self.sql_nodes = SQLNodes(llm=sql_llm)

        # React Nodes acts as the central controller / router with MAIN_LLM (temperature 0.7)
        self.react_nodes = ReactNodes(llm=self.llm)

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._session_id = value
        self.react_nodes.session_id = value

    def _graph(self, checkpointer: Optional[Checkpointer]) -> CompiledStateGraph:
        graph_builder = StateGraph(AIOverallSchema, input_schema=AIInputSchema, output_schema=AIOutputSchema)

        graph_builder.add_node("react_node", self.react_nodes.react_node)


        graph_builder.add_node("get_values_node", self.sql_nodes.get_values_node)
        graph_builder.add_node("get_appointments_node", self.sql_nodes.get_appointments_node)
        graph_builder.add_node("recommend_doctor_node", self.sql_nodes.recommend_doctor_node)
        graph_builder.add_node("reserve_appointment_node", self.sql_nodes.reserve_appointment_node)
        graph_builder.add_node("modify_appointment_node", self.sql_nodes.modify_appointment_node)
        graph_builder.add_node("vip_displacement_node", self.sql_nodes.vip_displacement_node)

        graph_builder.add_edge(START, "react_node")


        graph_builder.add_conditional_edges(
            "react_node",
            self.react_nodes.route_action,
            {
                NodeName.GET_VALUES: "get_values_node",
                NodeName.GET_APPOINTMENTS: "get_appointments_node",
                NodeName.RECOMMEND_DOCTOR: "recommend_doctor_node",
                NodeName.RESERVE_APPOINTMENT: "reserve_appointment_node",
                NodeName.MODIFY_APPOINTMENT: "modify_appointment_node",
                NodeName.VIP_DISPLACEMENT: "vip_displacement_node",
                NodeName.END: END,
            },
        )


        graph_builder.add_edge("get_values_node", "react_node")
        graph_builder.add_edge("get_appointments_node", "react_node")
        graph_builder.add_edge("recommend_doctor_node", "react_node")
        graph_builder.add_edge("reserve_appointment_node", "react_node")
        graph_builder.add_edge("modify_appointment_node", "react_node")
        graph_builder.add_edge("vip_displacement_node", "react_node")

        graph = graph_builder.compile(checkpointer=checkpointer)
        return graph
