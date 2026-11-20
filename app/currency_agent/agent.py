from typing import Any, Literal
from collections.abc import AsyncIterable

import httpx
from pydantic import BaseModel

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()


@tool
async def get_exchange_rate(
    currency_from: str = "USD",
    currency_to: str = "EUR",
    currency_date: str = "latest",
):
    """Use this to get current exchange rate.

    Args:
        currency_from: The currency to convert from (e.g., "USD").
        currency_to: The currency to convert to (e.g., "EUR").
        currency_date: The date for the exchange rate or "latest". Defaults to "latest".

    Returns:
        A dictionary containing the exchange rate data, or an error message if
        the request fails.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.frankfurter.dev/v1/{currency_date}",
                params={"from": currency_from, "to": currency_to},
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        return {"error": f"API request failed: {e}"}

    except ValueError:
        return {"error": "Invalid JSON response from API."}


class ResponseFormat(BaseModel):
    """Respond to the user in this format.

    Set response status to INPUT_REQUIRED if the user needs to provide more information to complete the request.
    Set response status to ERROR if there is an error while processing the request.
    Set response status to COMPLETED if the request is complete.
    """

    status: Literal["INPUT_REQUIRED", "COMPLETED", "ERROR"] = "INPUT_REQUIRED"
    message: str


class CurrencyAgent:
    """CurrencyAgent - a specialized assistant for currency convesions."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
    SYSTEM_INSTRUCTION = (
        "You are a specialized assistant for currency conversions. "
        "Your sole purpose is to use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "
        "If the user asks about anything other than currency conversion or exchange rates, "
        "politely state that you cannot help with that topic and can only assist with currency-related queries. "
        "Do not attempt to answer unrelated questions or use tools for other purposes."
    )

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-3.8-flash")
        self.tools = [get_exchange_rate]
        self.graph = create_agent(
            model=self.model,
            tools=self.tools,
            checkpointer=memory,
            system_prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )

    async def astream(self, query, context_id) -> AsyncIterable[dict[str, Any]]:
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": context_id}}

        async for item in self.graph.astream(inputs, config, stream_mode="values"):
            message = item["messages"][-1]
            if isinstance(message, AIMessage) and message.tool_calls:
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Looking up the exchange rates...",
                }
            elif isinstance(message, ToolMessage):
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Processing the exchange rates..",
                }

        yield await self.get_agent_response(config)

    async def get_agent_response(self, config):
        current_state = await self.graph.aget_state(config)
        structured_response = current_state.values.get("structured_response")

        if structured_response and isinstance(structured_response, ResponseFormat):
            return {
                "is_task_complete": structured_response.status == "COMPLETED",
                "require_user_input": structured_response.status
                in ["INPUT_REQUIRED", "ERROR"],
                "content": structured_response.message,
            }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "Unable to generate a forecast at the moment. Please try again.",
        }
