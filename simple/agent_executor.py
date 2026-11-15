import logging

from a2a.server.tasks import TaskUpdater
from a2a.server.events import EventQueue
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.types import Part, Task, TaskState, TaskNotFoundError, InternalError

from simple.agent import CurrencyAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CurrencyAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = CurrencyAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = Task(
                id=context.task_id,
                context_id=context.context_id,
                status={
                    "state": TaskState.TASK_STATE_SUBMITTED,
                    "message": context.message,
                },
            )
            await event_queue.enqueue_event(task)
            logger.info(f"Task is enqueued. taskId={task.id}")

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            async for item in self.agent.stream(query, task.context_id):
                is_task_complete = item["is_task_complete"]
                require_user_input = item["require_user_input"]
                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.TASK_STATE_WORKING,
                        message=updater.new_agent_message([Part(text=item["content"])]),
                    )
                    logger.info(
                        f"Task is updated. taskId={task.id} | TASK_STATE_WORKING"
                    )

                elif require_user_input:
                    await updater.update_status(
                        TaskState.TASK_STATE_INPUT_REQUIRED,
                        message=updater.new_agent_message([Part(text=item["content"])]),
                    )
                    logger.info(
                        f"Task is updated. taskId={task.id} | TASK_STATE_INPUT_REQUIRED"
                    )
                    break

                else:
                    await updater.add_artifact([Part(text=item["content"])])
                    logger.info(f"Artifact is updated. taskId={task.id}")
                    await updater.complete()
                    logger.info(f"Task is completed. taskId={task.id}")
                    break

        except Exception as e:
            logger.error(f"An error occurred while streaming the response: {e}")
            raise InternalError() from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            raise TaskNotFoundError()

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            await updater.update_status(TaskState.TASK_STATE_CANCELED)
            logger.info(f"Task is updated. taskId={task.id} | TASK_STATE_WORKING")

        except Exception as e:
            logger.error(f"An error occurred cancel: {e}")
            raise InternalError() from e
