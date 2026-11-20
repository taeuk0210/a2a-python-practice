from pydantic import BaseModel


class AppStreamResponse(BaseModel):
    is_task_complete: bool = False
    input_required: bool = False
    # Part 에 대응하는 타입이 있어야 함
    content: str = ""

    # Status 인지 Artifact 인지 구분하는 타입도 있어야 함
