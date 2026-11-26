import os
import json
import httpx
from enum import StrEnum
from typing import Optional, Any, AsyncIterable
from pydantic import BaseModel

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

# from app.types import *

from dotenv import load_dotenv

load_dotenv()


class AgentResponseStatus(StrEnum):
    WORKING = "WORKING"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class StreamAgentResponse(BaseModel):
    status: AgentResponseStatus
    content: Optional[Any] = None


@tool
async def get_exchange_rate(
    currency_from: str = "",
    currency_to: str = "",
    currency_date: str = "latest",
):
    """Use this to get exchange rate information.
    Args:
        currency_from: (Optional) The base currency to convert from (e.g., "USD"). Omit if not specified.
        currency_to: (Optional) The target currency to convert to (e.g., "KRW"). Omit if not specified.
        currency_date: The date for the exchange rate in "YYYY-MM-DD" format, or "latest" if the most recent rate is requested. Defaults to "latest".
    Returns:
        A dictionary containing the exchange rate data, or an error message if the request fails.
    """
    try:
        params = {}
        if currency_from:
            params["from"] = currency_from
        if currency_to:
            params["to"] = currency_to
        async with httpx.AsyncClient() as httpx_client:
            response = await httpx_client.get(
                f"https://api.frankfurter.dev/v1/{currency_date}", params=params
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        return {"error": f"HTTP request failed: {e}"}

    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}


memory = MemorySaver()


class CurrencyAgent:
    NAME = "Currency Agent"
    VERSION = "1.0.0"
    DESCRIPTION = "Helps with exchange rates for currencies."
    SUPPORTED_INTERFACES = [
        {
            "url": os.environ["CURRENCY_AGENT_URL"],
            "protocol_binding": "JSONRPC",
            "protocol_version": "2.0",
        }
    ]
    SUPPORTED_CONTENT_TYPES = ["text/plain"]
    CAPABILITIES = {
        "streaming": True,
        "push_notifications": True,
    }
    SKILLS = [
        {
            "id": "get_exchange_rate",
            "name": "Get Exchange Rate Tool",
            "description": "Use this to get current exchange rate.",
            "tags": ["currency"],
            "examples": ["What is exchange rate between USD and GBP?"],
        }
    ]
    SYSTEM_INSTRUCTION = """
You are a specialized exchange rate agent that supports all currency and exchange-rate-related tasks.

[Scope of Work]
- Simple currency conversions and looking up latest or historical exchange rates.
- Basic exchange rate data analysis, such as comparing rates across dates and calculating percentage changes (fluctuation rates).

[Tool Usage Rules]
- Never call the same tool more than once with identical arguments (`args`).
- If the required data has already been retrieved in the conversation history, do not call the tool again—reuse the existing result directly.
- Once you have all the data needed to answer the user's request, stop calling tools and immediately provide the final response.
""".strip()

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-3.8-flash")
        self.tools = [get_exchange_rate]
        self.graph = create_agent(
            model=self.model,
            tools=self.tools,
            checkpointer=memory,
            system_prompt=self.SYSTEM_INSTRUCTION,
            response_format=StreamAgentResponse,
        )

    async def astream(
        self, query: str, context_id: str
    ) -> AsyncIterable[StreamAgentResponse]:
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": context_id}, "recursion_limit": 10}

        try:
            # response tool call
            async for item in self.graph.astream(inputs, config, stream_mode="values"):
                message = item["messages"][-1]
                if isinstance(message, AIMessage) and message.tool_calls:
                    yield StreamAgentResponse(
                        status="WORKING",
                        content=json.dumps(message.tool_calls, ensure_ascii=False),
                    )
                elif isinstance(message, ToolMessage):
                    yield StreamAgentResponse(
                        status="WORKING",
                        content=json.dumps(message.content, ensure_ascii=False),
                    )

            # response final
            current_state = await self.graph.aget_state(config)
            response = current_state.values.get("structured_response")
            yield StreamAgentResponse(
                status=response.status,
                content=json.dumps(response.content, ensure_ascii=False),
            )

        except GraphRecursionError:
            yield StreamAgentResponse(
                status="FAILED", content="생성에 실패했어용~ 😂😂"
            )
