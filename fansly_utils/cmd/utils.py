import json
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "contains",
    "extract_ids",
    "find_by",
    "load_backup",
    "merge_lists",
    "save_backup",
]


def save_backup(file_path: "Path", data: dict) -> None:
    data["accounts"].sort(key=lambda o: o["id"])
    data["deleted"].sort()
    data["following"].sort()
    data["lists"].sort(key=lambda o: o["label"])
    data["payments"].sort(key=lambda o: o["transactionId"])

    for items in data["lists"]:
        items["items"].sort()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4, sort_keys=True)


def load_backup(file_path: "Path") -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# https://stackoverflow.com/questions/38346013
def contains(data: list[str], item: str) -> bool:
    low = 0
    high = len(data) - 1
    while low <= high:
        mid = (low + high) // 2
        if data[mid] == item:
            return True
        if item < data[mid]:
            high = mid - 1
        else:
            low = mid + 1
    return False


# https://stackoverflow.com/questions/9542738
def find_by(iterable: Iterable[dict], *, key: str, value: str) -> dict | None:
    return next(filter(lambda o: o[key] == value, iterable), None)


def merge_lists(lhs: list[str], rhs: list[str]) -> list[str]:
    return list(set(lhs) | set(rhs))


def extract_ids(iterable: Iterable[dict], *, key: str = "id") -> list[str]:
    return [o[key] for o in iterable]
