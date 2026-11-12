from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, create_client, ClientConfig
from a2a.types import SendMessageRequest, Role


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0) as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url="http://localhost:9999",
        )

        agent_card = await resolver.get_agent_card()

        client = await create_client(
            agent=agent_card,
            client_config=ClientConfig(httpx_client=httpx_client),
        )

        request = SendMessageRequest(
            message={
                "role": Role.ROLE_USER,
                "parts": [{"text": "how much is 10 USD in INR?"}],
                "message_id": uuid4().hex,
            }
        )
        async for chunk in client.send_message(request):
            print(chunk)
            # if chunk.HasField("status_update"):
            #     if chunk.status_update.status.message.parts:
            #         print(chunk.status_update.status.message.parts[0].text)
            # if chunk.HasField("artifact_update"):
            #     if chunk.artifact_update.artifact.parts:
            #         print(chunk.artifact_update.artifact.parts[0].text)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
