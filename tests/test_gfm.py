from typing import Any, cast

import pytest
from conftest import normalize_adf_for_testing
from jsonschema.protocols import Validator

from marklassian import markdown_to_adf


def _mention_ids(node: dict[str, Any]) -> list[str]:
    mention_ids = []
    if node.get("type") == "mention":
        mention_ids.append(node["attrs"]["id"])
    for child in node.get("content", []):
        mention_ids.extend(_mention_ids(child))
    return mention_ids


def test_jira_mentions_work_in_gfm_non_list_block_contexts(
    adf_validator: Validator,
) -> None:
    result = cast(
        dict[str, Any],
        markdown_to_adf(
            "# [~accountId:heading]\n\n"
            "> [~accountId:blockquote]\n\n"
            "| Mention |\n"
            "| --- |\n"
            "| [~accountId:table] |",
            jira_mentions=True,
        ),
    )

    adf_validator.validate(result)
    assert _mention_ids(result) == ["heading", "blockquote", "table"]


def test_jira_mentions_work_in_tight_gfm_lists(adf_validator: Validator) -> None:
    result = cast(
        dict[str, Any],
        markdown_to_adf(
            "- [~accountId:tight-first]\n- [~accountId:tight-second]",
            jira_mentions=True,
        ),
    )

    adf_validator.validate(result)
    assert result["content"][0]["type"] == "bulletList"
    assert _mention_ids(result) == ["tight-first", "tight-second"]


def test_jira_mentions_work_in_loose_gfm_lists(adf_validator: Validator) -> None:
    result = cast(
        dict[str, Any],
        markdown_to_adf(
            "- [~accountId:loose-first]\n\n- [~accountId:loose-second]",
            jira_mentions=True,
        ),
    )

    adf_validator.validate(result)
    assert result["content"][0]["type"] == "bulletList"
    assert _mention_ids(result) == ["loose-first", "loose-second"]


def test_jira_mentions_work_in_native_gfm_task_lists(
    adf_validator: Validator,
) -> None:
    result = cast(
        dict[str, Any],
        markdown_to_adf("- [ ] [~accountId:task]", jira_mentions=True),
    )

    adf_validator.validate(result)
    assert result["content"][0]["type"] == "taskList"
    assert _mention_ids(result) == ["task"]


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


def test_task_lists_with_formatting(adf_validator: Validator) -> None:
    markdown = """- [x] **Bold** task
- [ ] *Italic* task with [link](https://example.com)
- [ ] `Code` task"""

    result = cast(dict[str, Any], markdown_to_adf(markdown))
    adf_validator.validate(result)
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


def test_mixed_regular_and_task_list_items(adf_validator: Validator) -> None:
    markdown = """- Regular item
- [ ] Task item
- Another regular item"""

    result = cast(dict[str, Any], markdown_to_adf(markdown))
    adf_validator.validate(result)

    first_content = result["content"][0]
    assert first_content["type"] == "bulletList"
    assert len(first_content["content"]) == 3

    for item in first_content["content"]:
        assert item["type"] == "listItem"


def test_nested_regular_list_in_task_uses_visible_checkbox_fallback(
    adf_validator: Validator,
) -> None:
    result = cast(dict[str, Any], markdown_to_adf("- [ ] Parent\n  - Child"))

    adf_validator.validate(result)
    outer_list = result["content"][0]
    assert outer_list["type"] == "bulletList"
    item_content = outer_list["content"][0]["content"]
    assert item_content[0]["content"] == [{"type": "text", "text": "[ ] Parent"}]
    assert item_content[1]["type"] == "bulletList"


def test_task_with_two_paragraphs_uses_block_task_item(
    adf_validator: Validator,
) -> None:
    markdown = "- [x] First paragraph\n\n  Second paragraph"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    task_item = result["content"][0]["content"][0]
    assert task_item["type"] == "blockTaskItem"
    assert task_item["attrs"]["state"] == "DONE"
    assert [node["content"][0]["text"] for node in task_item["content"]] == [
        "First paragraph",
        "Second paragraph",
    ]


def test_code_block_in_task_uses_visible_checkbox_fallback(
    adf_validator: Validator,
) -> None:
    markdown = "- [ ] Task\n\n  ```python\n  pass\n  ```"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    outer_list = result["content"][0]
    assert outer_list["type"] == "bulletList"
    item_content = outer_list["content"][0]["content"]
    assert item_content[0]["content"] == [{"type": "text", "text": "[ ] Task"}]
    assert item_content[1] == {
        "type": "codeBlock",
        "attrs": {"language": "python"},
        "content": [{"type": "text", "text": "pass"}],
    }


@pytest.mark.parametrize(
    ("markdown_block", "expected_text"),
    [
        ("> quote", "> quote"),
        ("# Heading", "# Heading"),
        ("---", "---"),
    ],
)
def test_unsupported_task_blocks_use_visible_text_fallback(
    markdown_block: str,
    expected_text: str,
    adf_validator: Validator,
) -> None:
    markdown = f"- [ ] Task\n\n  {markdown_block}"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    item_content = result["content"][0]["content"][0]["content"]
    assert item_content[1]["content"] == [{"type": "text", "text": expected_text}]


@pytest.mark.parametrize(
    ("markdown", "quoted_block_type"),
    [
        ("- [ ] Task\n\n  > - quoted child", "bulletList"),
        ("- [ ] Task\n\n  > ```\n  > quoted code\n  > ```", "codeBlock"),
    ],
)
def test_quoted_task_blocks_keep_visible_quote_marker(
    markdown: str,
    quoted_block_type: str,
    adf_validator: Validator,
) -> None:
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    item_content = result["content"][0]["content"][0]["content"]
    assert [node["type"] for node in item_content[1:]] == [
        "paragraph",
        quoted_block_type,
    ]
    assert item_content[1]["content"] == [{"type": "text", "text": ">"}]


@pytest.mark.parametrize("task_marker", ["", "[ ] "])
def test_images_in_list_items_are_preserved(
    task_marker: str,
    adf_validator: Validator,
) -> None:
    markdown = f"- {task_marker}Item\n\n  ![diagram](https://example.test/a.png)"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    item_content = result["content"][0]["content"][0]["content"]
    media = next(node for node in item_content if node["type"] == "mediaSingle")
    assert media["content"][0]["attrs"]["url"] == "https://example.test/a.png"


def test_task_fallback_preserves_nested_task_order(adf_validator: Validator) -> None:
    markdown = "- [ ] Before\n\n  - [ ] Child\n\n  After"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    item_content = result["content"][0]["content"][0]["content"]
    assert [node["type"] for node in item_content] == [
        "paragraph",
        "taskList",
        "paragraph",
    ]
    assert item_content[0]["content"][0]["text"] == "[ ] Before"
    assert item_content[2]["content"][0]["text"] == "After"


def test_mixed_nested_list_preserves_task_marker(adf_validator: Validator) -> None:
    markdown = "- [ ] Parent\n  - [x] Child task\n  - Regular child"
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    nested_list = result["content"][0]["content"][0]["content"][1]
    first_nested_item = nested_list["content"][0]
    assert first_nested_item["content"][0]["content"][0]["text"] == "[x] Child task"


def test_nested_ordered_task_fallback_preserves_order(adf_validator: Validator) -> None:
    markdown = """- Parent

  3. [ ] Task

     ```
     body
     ```"""
    result = cast(dict[str, Any], markdown_to_adf(markdown))

    adf_validator.validate(result)
    nested_list = result["content"][0]["content"][0]["content"][1]
    assert nested_list["type"] == "orderedList"
    assert nested_list["attrs"]["order"] == 3
