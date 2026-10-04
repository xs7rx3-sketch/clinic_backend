import json
from datetime import datetime
from typing import Any, Optional
from langchain_core.messages import AIMessage, HumanMessage
from utilities_ai.chains.helpers import fetch_system_prompt_only, manage_system_message

from src.ai.enums import NodeName
from src.ai.node_schemas import NodeDecision
from src.ai.prompts.react_prompts import react_normal_prompt, react_vip_prompt
from src.ai.state_schema import AIOverallSchema


class ReactNodes:
    """Central Controller and Router managing multi-turn dialog and specialized node delegation."""

    def __init__(self, *, llm: Any):
        self.llm = llm
        self.structured_llm = self.llm.with_structured_output(NodeDecision, method="function_calling")
        self._session_id: Optional[str] = None

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._session_id = value

    async def react_node(self, state: AIOverallSchema) -> dict[str, Any]:
        query = state.get("query", "")
        user_data = state.get("user_data", {})
        messages = list(state.get("messages", []))

        # Ensure user query is present in messages
        if not messages:
            messages.append(HumanMessage(content=query))

        # Format live system timestamp and authenticated patient context
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        patient_context = f"\n### CURRENT LIVE SYSTEM TIME:\n- Today: {now_str} (Asia/Dubai GST timezone)\n- Always resolve relative terms like 'today', 'tomorrow', 'next week', 'غداً', 'بعد قليل' relative to this current timestamp.\n"
        if user_data:
            patient_context += f"\n### AUTHENTICATED PATIENT CONTEXT:\n{json.dumps(user_data, ensure_ascii=False, indent=2)}\n"

        # Robust VIP detection
        is_vip = bool(
            user_data.get("is_vip") is True
            or str(user_data.get("is_vip", "")).lower() == "true"
            or str(user_data.get("patient_type", "")).upper() == "VIP"
            or any("[Output from vip_displacement_node" in str(getattr(m, "content", "")) for m in messages)
        )

        prompt = react_vip_prompt(query, patient_context=patient_context) if is_vip else react_normal_prompt(query, patient_context=patient_context)

        system_prompt = fetch_system_prompt_only(prompt)
        messages.append(system_prompt)
        messages = manage_system_message(messages)

        # Invoke model for routing decision
        decision: NodeDecision = await self.structured_llm.ainvoke(messages)

        if decision.next_node in (NodeName.END, "end"):
            answer = decision.response_to_user or ""
            messages.append(AIMessage(content=answer))
        else:
            answer = state.get("answer")
            messages.append(AIMessage(content=f"[Routing to node: {decision.next_node}]"))

        return {
            "messages": messages,
            "next_node": decision.next_node,
            "node_input": decision.node_input or {},
            "answer": answer,
        }

    async def route_action(self, state: AIOverallSchema) -> NodeName:
        return state.get("next_node", NodeName.END)  # type: ignore
