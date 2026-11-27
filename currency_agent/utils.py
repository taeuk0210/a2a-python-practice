from typing import Any

from a2a.types import AgentCard


def agent_to_agent_card(agent: Any) -> AgentCard:
    return AgentCard(
        name=agent.NAME,
        version=agent.VERSION,
        description=agent.DESCRIPTION,
        supported_interfaces=agent.SUPPORTED_INTERFACES,
        default_input_modes=agent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=agent.SUPPORTED_CONTENT_TYPES,
        capabilities=agent.CAPABILITIES,
        skills=agent.SKILLS,
    )
