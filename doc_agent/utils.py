import os
import json


def json_dump(jsonpath: str, data: dict):
    os.makedirs(os.path.dirname(jsonpath), exist_ok=True)
    with open(jsonpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def json_load(jsonpath: str) -> dict | list:
    with open(jsonpath, "r", encoding="utf-8") as f:
        return json.load(f)
