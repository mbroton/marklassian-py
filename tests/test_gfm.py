from typing import Any, cast

from marklassian import markdown_to_adf

from conftest import normalize_adf_for_testing


def test_gfm_task_lists(task_list_adf: dict[str, Any]) -> None:
    markdown = """- [ ] Foo bar
- [ ] Baz yo"""

    adf = markdown_to_adf(markdown)
    normalized_adf = normalize_adf_for_testing(adf)
    assert normalized_adf == task_list_adf


def test_nested_gfm_task_lists_with_checked_and_unchecked(
    nested_task_list_adf: dict[str, Any],
) -> None:
    markdown = """- [x] Completed task
- [ ] Incomplete task
  - [x] Nested completed
  - [ ] Nested incomplete"""

    adf = markdown_to_adf(markdown)
    normalized_adf = normalize_adf_for_testing(adf)
    assert normalized_adf == nested_task_list_adf


def test_task_lists_with_formatting() -> None:
    markdown = """- [x] **Bold** task
- [ ] *Italic* task with [link](https://example.com)
- [ ] `Code` task"""

    result = cast(dict[str, Any], markdown_to_adf(markdown))
    normalized_adf = normalize_adf_for_testing(result)

    assert normalized_adf["content"][0]["type"] == "taskList"
    assert len(normalized_adf["content"][0]["content"]) == 3

    first_item = normalized_adf["content"][0]["content"][0]
    assert first_item["attrs"]["state"] == "DONE"
    assert first_item["content"][0]["marks"][0]["type"] == "strong"

    second_item = normalized_adf["content"][0]["content"][1]
    assert second_item["attrs"]["state"] == "TODO"
    has_em = any(
        any(mark.get("type") == "em" for mark in node.get("marks", []))
        for node in second_item["content"]
    )
    assert has_em

    has_link = any(
        any(mark.get("type") == "link" for mark in node.get("marks", []))
        for node in second_item["content"]
    )
    assert has_link

    third_item = normalized_adf["content"][0]["content"][2]
    assert third_item["attrs"]["state"] == "TODO"
    has_code = any(
        any(mark.get("type") == "code" for mark in node.get("marks", []))
        for node in third_item["content"]
    )
    assert has_code


def test_mixed_regular_and_task_list_items() -> None:
    markdown = """- Regular item
- [ ] Task item
- Another regular item"""

    result = cast(dict[str, Any], markdown_to_adf(markdown))

    first_content = result["content"][0]
    assert first_content["type"] == "bulletList"
    assert len(first_content["content"]) == 3

    for item in first_content["content"]:
        assert item["type"] == "listItem"
