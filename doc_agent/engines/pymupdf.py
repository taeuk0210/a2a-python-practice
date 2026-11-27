from collections import deque

import pymupdf
import numpy as np


def _get_page_indices(blocks: list[dict]) -> list[int]:
    return sorted(set(b["page_index"] for b in blocks))


def _get_block_types(blocks: list[dict]) -> list[str]:
    return sorted(set(b["block_type"] for b in blocks))


def _sort(blocks: list[dict]):
    return sorted(blocks, key=lambda b: (b["page_index"], b["bbox"][1], b["bbox"][0]))


def _clip_bbox(bbox: list[float], page_bbox: list[float]) -> list[float]:
    if bbox is None:
        return None

    x0, y0, x1, y1 = bbox
    x_min, y_min, x_max, y_max = page_bbox
    return [
        np.clip(x0, x_min, x_max),
        np.clip(y0, y_min, y_max),
        np.clip(x1, x_min, x_max),
        np.clip(y1, y_min, y_max),
    ]


def _merge(
    blocks: list[dict],
) -> dict:
    blocks = _sort(blocks)

    bbox = [
        min([b["bbox"][0] for b in blocks]),
        min([b["bbox"][1] for b in blocks]),
        max([b["bbox"][2] for b in blocks]),
        max([b["bbox"][3] for b in blocks]),
    ]

    block = {
        "page_index": blocks[0]["page_index"],
        "block_type": blocks[0]["block_type"],
        "bbox": bbox,
    }

    text = "\n".join(b["text"] for b in blocks if b.get("text"))
    if text:
        block["text"] = text

    return block


def extract_blocks(
    pdf_input_path: str,
    page_indices: list[int] = [],
):
    extracted = []
    with pymupdf.open(pdf_input_path) as doc:
        if not page_indices:
            page_indices = list(range(doc.page_count))

        for page_index in page_indices:
            if page_index >= doc.page_count:
                continue

            page = doc[page_index]

            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    text = " ".join(
                        s["text"].strip()
                        for s in line.get("spans", [])
                        if s.get("text")
                    ).strip()
                    if not text:
                        continue

                    extracted.append(
                        {
                            "page_index": page_index,
                            "block_type": "TEXT",
                            "bbox": _clip_bbox(line.get("bbox", None), page.rect),
                            "text": text,
                        }
                    )

            for info in page.get_image_info():
                extracted.append(
                    {
                        "page_index": page_index,
                        "block_type": "IMAGE",
                        "bbox": _clip_bbox(info.get("bbox", None), page.rect),
                    }
                )

            for drawing in page.get_drawings():
                xs = []
                ys = []

                for item in drawing.get("items", []):
                    if item[0] == "l":
                        xs.extend([item[1].x, item[2].x])
                        ys.extend([item[1].y, item[2].y])
                    elif item[0] == "re":
                        xs.extend([item[1].x0, item[1].x1])
                        ys.extend([item[1].y0, item[1].y1])
                    elif item[0] == "qu":
                        xs.extend([item[1].x0, item[1].x1])
                        ys.extend([item[1].y0, item[1].y1])
                    elif item[0] == "c":
                        xs.extend([item[1].x, item[2].x, item[3].x, item[4].x])
                        ys.extend([item[1].y, item[2].y, item[3].y, item[4].y])

                extracted.append(
                    {
                        "page_index": page_index,
                        "block_type": "IMAGE",
                        "bbox": _clip_bbox(
                            [min(xs), min(ys), max(xs), max(ys)], page.rect
                        ),
                    }
                )

    return _sort(extracted)


def merge_blocks(
    blocks: list[dict],
    threshold: float = 5.0,
):
    page_indices = _get_page_indices(blocks)
    block_types = _get_block_types(blocks)

    merged = []
    for page_index in page_indices:
        page_blocks = [b for b in blocks if b["page_index"] == page_index]
        for block_type in block_types:
            blks = [b for b in page_blocks if b["block_type"] == block_type]

            n = len(blks)
            if n <= 1:
                merged.extend(blks)
                continue

            bboxes = np.array(
                [
                    [
                        b["bbox"][0],
                        b["bbox"][1],
                        b["bbox"][2],
                        b["bbox"][3],
                    ]
                    for b in blks
                ]
            )
            x0 = bboxes[:, 0].reshape(-1, 1)
            y0 = bboxes[:, 1].reshape(-1, 1)
            x1 = bboxes[:, 2].reshape(-1, 1)
            y1 = bboxes[:, 3].reshape(-1, 1)
            dx = np.maximum(0, np.maximum(x0 - x1.T, x0.T - x1))
            dy = np.maximum(0, np.maximum(y0 - y1.T, y0.T - y1))
            mask = (dx <= threshold) & (dy <= threshold)

            visited = np.zeros(n, dtype=bool)
            groups = []
            for i in range(n):
                if visited[i]:
                    continue

                queue = deque([i])
                visited[i] = True
                next_indices: list[int] = []
                current_group: list[list[int]] = []

                while queue:
                    i = queue.popleft()
                    current_group.append(i)
                    next_indices = np.where(mask[i, :] | mask[:, i])[0]

                    for idx in next_indices:
                        if not visited[idx]:
                            visited[idx] = True
                            queue.append(idx)

                if current_group:
                    groups.append(current_group)

            for group in groups:
                merged.append(_merge(blocks=[blks[i] for i in group]))

    return _sort(merged)


def filter_blocks(
    blocks: list[dict],
    eps: float = 5.0,
    image_min_area: float = 10.0,
):
    page_indices = _get_page_indices(blocks)
    block_types = _get_block_types(blocks)

    filtered = []

    # area-overlap
    for page_index in page_indices:
        page_blocks = [b for b in blocks if b["page_index"] == page_index]
        for block_type in block_types:
            blks = [b for b in page_blocks if b["block_type"] == block_type]

            n = len(blks)
            if n <= 1:
                filtered.extend(blks)
                continue

            bboxes = np.array(
                [
                    [
                        b["bbox"][0],
                        b["bbox"][1],
                        b["bbox"][2],
                        b["bbox"][3],
                    ]
                    for b in blks
                ]
            )
            b1 = bboxes[:, np.newaxis, :]
            b2 = bboxes[np.newaxis, :, :]

            contains_x = (b1[..., 0] - eps <= b2[..., 0]) & (
                b1[..., 2] + eps >= b2[..., 2]
            )
            contains_y = (b1[..., 1] - eps <= b2[..., 1]) & (
                b1[..., 3] + eps >= b2[..., 3]
            )
            mask = contains_x & contains_y
            np.fill_diagonal(mask, False)

            same_box = (
                (np.abs(b1[..., 0] - b2[..., 0]) <= eps)
                & (np.abs(b1[..., 1] - b2[..., 1]) <= eps)
                & (np.abs(b1[..., 2] - b2[..., 2]) <= eps)
                & (np.abs(b1[..., 3] - b2[..., 3]) <= eps)
            )
            upper_triangle = np.triu(np.ones_like(mask, dtype=bool), k=1)
            mask = np.where(same_box, mask & upper_triangle, mask)
            remove_indices = np.any(mask, axis=0)
            filtered.extend(
                [blks[i] for i in range(len(blks)) if i not in remove_indices]
            )

    # area-overlap
    remove_indices = []
    for i in range(len(filtered)):
        block = filtered[i]
        if block["block_type"] == "IMAGE":
            x0, y0, x1, y1 = block["bbox"]
            area = (x1 - x0) * (y1 - y0)
            if area <= image_min_area:
                remove_indices.append(i)

    filtered = [filtered[i] for i in range(len(filtered)) if i not in remove_indices]
    return _sort(filtered)
