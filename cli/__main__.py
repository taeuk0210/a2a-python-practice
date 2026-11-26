import asyncio
import httpx
from uuid import uuid4
from a2a.client import A2ACardResolver, create_client, ClientConfig
from a2a.types import AgentCard, SendMessageRequest, Role


async def get_agent_card(base_url: str):
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
    return agent_card


async def send_message(agent_card: AgentCard, context_id: str):
    user_input = input("[USER ]: ")

    async with httpx.AsyncClient(timeout=60.0) as httpx_client:
        client = await create_client(
            agent_card, client_config=ClientConfig(httpx_client=httpx_client)
        )

        request = SendMessageRequest(
            message={
                "context_id": context_id,
                "message_id": uuid4().hex,
                "role": Role.ROLE_USER,
                "parts": [{"text": user_input}],
            }
        )
        async for chunk in client.send_message(request):
            if chunk.HasField("status_update") and chunk.status_update.status.HasField(
                "message"
            ):
                print(f"[AGENT]: {chunk.status_update.status.message.parts[-1].text}")
            if chunk.HasField("artifact_update"):
                print(f"[AGENT]: {chunk.artifact_update.artifact.parts[-1].text}")


async def main():
    print("[INPUT] input base url for agent connection. ex) http://localhost:9991")

    agent_card = await get_agent_card(base_url=input(">> "))

    print("[CHECK] check your agent.")
    print(f" name: {agent_card.name}")
    print(f" description: {agent_card.description}")
    print(f" skills: {', '.join([s.name for s in agent_card.skills])}")

    context_id = uuid4().hex
    while True:
        await send_message(agent_card=agent_card, context_id=context_id)

    return


if __name__ == "__main__":
    asyncio.run(main())
