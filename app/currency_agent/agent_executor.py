import logging

from a2a.server.tasks import TaskUpdater
from a2a.server.events import EventQueue
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.types import Part, Task, TaskState, TaskNotFoundError, InternalError

from app.currency_agent.agent import CurrencyAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CurrencyAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CurrencyAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await event_queue.enqueue_event(
                Task(
                    id=context.task_id,
                    context_id=context.context_id,
                    status={"state": TaskState.TASK_STATE_SUBMITTED},
                    history=[context.message],
                )
            )
            logger.info(
                f"Task is updated. taskId={context.task_id} | TASK_STATE_SUBMITTED"
            )

        query = context.get_user_input()
        try:
            async for item in self.agent.astream(query, context.context_id):
                is_task_complete = item["is_task_complete"]
                require_user_input = item["require_user_input"]

                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.TASK_STATE_WORKING,
                        message=updater.new_agent_message([Part(text=item["content"])]),
                    )
                    logger.info(
                        f"Task is updated. taskId={context.task_id} | TASK_STATE_WORKING"
                    )

                elif require_user_input:
                    await updater.update_status(
                        TaskState.TASK_STATE_INPUT_REQUIRED,
                        message=updater.new_agent_message([Part(text=item["content"])]),
                    )
                    logger.info(
                        f"Task is updated. taskId={context.task_id} | TASK_STATE_INPUT_REQUIRED"
                    )
                    break

                else:
                    await updater.add_artifact(
                        [Part(text=item["content"])], last_chunk=True
                    )
                    logger.info(f"Artifact is updated. taskId={context.task_id}")

                    await updater.complete()
                    logger.info(f"Task is completed. taskId={context.task_id}")
                    break

        except Exception as e:
            logger.error(f"An error occurred while streaming the response: {e}")
            raise InternalError() from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            raise TaskNotFoundError()

        try:
            await updater.cancel()
            logger.info(
                f"Task is updated. taskId={context.task_id} | TASK_STATE_CANCELED"
            )

        except Exception as e:
            logger.error(f"An error occurred while canceling: {e}")
            raise InternalError() from e
