from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, InternalError


class CurrencyAgentExecutor(AgentExecutor):
    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        if not context.current_task:
            await event_queue.enqueue_event(
                Task(
                    id=context.task_id,
                    context_id=context.context_id,
                    status={"state": TaskState.TASK_STATE_SUBMITTED},
                    history=[context.message],
                )
            )

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        try:
            async for res in self.agent.astream(
                query=context.get_user_input(), context_id=context.context_id
            ):
                if res.status == "WORKING":
                    await updater.update_status(
                        TaskState.TASK_STATE_WORKING,
                        updater.new_agent_message([Part(text=res.content)]),
                    )
                    continue

                elif res.status == "INPUT_REQUIRED":
                    await updater.update_status(
                        TaskState.TASK_STATE_INPUT_REQUIRED,
                        updater.new_agent_message([Part(text=res.content)]),
                    )

                elif res.status == "FAILED":
                    await updater.update_status(
                        TaskState.TASK_STATE_FAILED,
                        updater.new_agent_message([Part(text=res.content)]),
                    )

                else:
                    await updater.add_artifact([Part(text=res.content)])
                    await updater.complete()

                break

        except Exception as e:
            raise InternalError() from e
        return

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            updater = TaskUpdater(
                event_queue=event_queue,
                task_id=context.task_id,
                context_id=context.context_id,
            )
            await updater.cancel()

        except Exception as e:
            raise InternalError() from e
