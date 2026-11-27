from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from doc_agent.engines.pymupdf import extract_blocks, merge_blocks, filter_blocks
from doc_agent.utils import json_dump, json_load


@tool
def pdf_to_json(
    page_indices: list[int],
    config: RunnableConfig,
) -> None:
    """Use this tool for converting pdf to json.
    Args:
        page_indices: (Optional) Specific parsing page index list. default set [].
    Returns:
        None
    """
    pdf_input_path = config["configurable"]["pdf_input_path"]
    json_output_path = config["configurable"]["json_output_path"]

    blocks = extract_blocks(pdf_input_path, page_indices)

    blocks = merge_blocks(blocks, threshold=10.0)  # TODO to args

    blocks = filter_blocks(blocks, eps=5.0)  # TODO to args

    json_dump(json_output_path, blocks)

    return
