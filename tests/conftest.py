import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from marklassian.types import AdfDocument

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def normalize_adf_for_testing(adf: AdfDocument | dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = copy.deepcopy(cast(dict[str, Any], adf))
    task_list_counter = 0
    task_item_counter = 0

    def traverse(node: dict[str, Any]) -> None:
        nonlocal task_list_counter, task_item_counter

        if node.get("type") == "taskList" and node.get("attrs", {}).get("localId"):
            suffix = f"-{task_list_counter}" if task_list_counter > 0 else ""
            node["attrs"]["localId"] = f"test-task-list-id{suffix}"
            task_list_counter += 1

        if node.get("type") == "taskItem" and node.get("attrs", {}).get("localId"):
            task_item_counter += 1
            node["attrs"]["localId"] = f"test-task-item-id-{task_item_counter}"

        for child in node.get("content", []):
            traverse(child)

    for node in normalized.get("content", []):
        traverse(node)

    return normalized


def load_fixture(name: str) -> dict[str, Any]:
    fixture_path = FIXTURES_DIR / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def basics_adf() -> dict[str, Any]:
    return load_fixture("basics")


@pytest.fixture
def code_blocks_adf() -> dict[str, Any]:
    return load_fixture("code-blocks")


@pytest.fixture
def inline_code_marks_adf() -> dict[str, Any]:
    return load_fixture("inline-code-marks")


@pytest.fixture
def nested_list_adf() -> dict[str, Any]:
    return load_fixture("nested-list")


@pytest.fixture
def special_chars_adf() -> dict[str, Any]:
    return load_fixture("special-chars")


@pytest.fixture
def table_adf() -> dict[str, Any]:
    return load_fixture("table")


@pytest.fixture
def text_edge_cases_adf() -> dict[str, Any]:
    return load_fixture("text-edge-cases")


@pytest.fixture
def task_list_adf() -> dict[str, Any]:
    return load_fixture("gfm-task-list")


@pytest.fixture
def nested_task_list_adf() -> dict[str, Any]:
    return load_fixture("gfm-nested-task-list")
