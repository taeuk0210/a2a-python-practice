import os
import sys
import logging
from dotenv import load_dotenv

import click
import httpx
import uvicorn
from uvicorn.logging import DefaultFormatter
from starlette.applications import Starlette
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryTaskStore,
    InMemoryPushNotificationConfigStore,
)

from currency_agent.agent import CurrencyAgent
from currency_agent.executor import CurrencyAgentExecutor
from app.utils import agent_to_agent_card

load_dotenv()

CURRENCY_AGENT_HOST = os.environ["CURRENCY_AGENT_HOST"]
CURRENCY_AGENT_PORT = os.environ["CURRENCY_AGENT_PORT"]
CURRENCY_AGENT_ENDPOINT = os.environ["CURRENCY_AGENT_ENDPOINT"]

handler = logging.StreamHandler()
handler.setFormatter(
    DefaultFormatter(fmt="%(levelprefix)s %(message)s", use_colors=True)
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)


@click.command()
@click.option("--host", "host", default=CURRENCY_AGENT_HOST)
@click.option("--port", "port", default=CURRENCY_AGENT_PORT)
def main(host, port):
    try:
        agent_card = agent_to_agent_card(CurrencyAgent)

        httpx_client = httpx.AsyncClient()

        push_config_store = InMemoryPushNotificationConfigStore()

        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client,
            config_store=push_config_store,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=CurrencyAgentExecutor(CurrencyAgent()),
            task_store=InMemoryTaskStore(),
            agent_card=agent_card,
            push_config_store=push_config_store,
            push_sender=push_sender,
        )

        routes = []
        routes.extend(create_agent_card_routes(agent_card=agent_card))
        routes.extend(
            create_jsonrpc_routes(
                request_handler=request_handler,
                rpc_url=CURRENCY_AGENT_ENDPOINT,
            )
        )
        app = Starlette(routes=routes)

        uvicorn.run(app, host=host, port=int(port))

    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
