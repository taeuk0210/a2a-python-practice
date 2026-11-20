from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, InternalError

from app.agents.stream_agent import StreamAgent
from app.types import *


class StreamAgentExecutor(AgentExecutor):
    def __init__(self, agent: StreamAgent):
        super().__init__()
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
                if not res.is_task_complete and not res.input_required:
                    await updater.update_status(
                        TaskState.TASK_STATE_WORKING,
                        updater.new_agent_message([Part(text=res.content)]),
                    )
                elif res.input_required:
                    await updater.update_status(
                        TaskState.TASK_STATE_INPUT_REQUIRED,
                        updater.new_agent_message([Part(text=res.content)]),
                    )
                    break
                else:
                    await updater.add_artifact(
                        updater.new_agent_message([Part(text=res.content)]),
                    )
                    await updater.complete()
                    break

        except Exception as e:
            raise InternalError() from e
        return

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        return
