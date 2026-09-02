import pytest
from jsonschema.protocols import Validator

from marklassian import markdown_to_adf
from marklassian.converter import _merge_adjacent_text_nodes
from marklassian.types import AdfNode


def test_jira_mentions_are_default_off() -> None:
    source = "[~accountId:opaque-id]"

    result = markdown_to_adf(source)

    assert result["content"][0]["content"] == [{"type": "text", "text": source}]


@pytest.mark.parametrize("jira_mentions", [False, True])
def test_jira_mentions_preserve_existing_unrelated_image_alt_behavior(
    jira_mentions: bool,
) -> None:
    result = markdown_to_adf(
        "![alt **bold** tail](image.png)",
        jira_mentions=jira_mentions,
    )

    assert result == {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "mediaSingle",
                "attrs": {"layout": "center"},
                "content": [
                    {
                        "type": "media",
                        "attrs": {
                            "type": "external",
                            "url": "image.png",
                            "alt": "alt ",
                        },
                    }
                ],
            }
        ],
    }


def test_jira_mentions_emit_id_only_adf_when_enabled(adf_validator: Validator) -> None:
    result = markdown_to_adf("[~accountId:opaque-id]", jira_mentions=True)

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "mention", "attrs": {"id": "opaque-id"}},
    ]


@pytest.mark.parametrize(
    "source",
    ["[~ACCOUNTID:opaque-id]", "[~AcCoUnTiD:opaque-id]"],
)
def test_jira_mention_prefix_is_ascii_case_insensitive(
    source: str,
    adf_validator: Validator,
) -> None:
    result = markdown_to_adf(source, jira_mentions=True)

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "mention", "attrs": {"id": "opaque-id"}},
    ]


@pytest.mark.parametrize(
    "source",
    ["[~accountİd:opaque-id]", "[~accountıd:opaque-id]"],
)
def test_jira_mention_unicode_lookalikes_remain_text(source: str) -> None:
    result = markdown_to_adf(source, jira_mentions=True)

    assert result["content"][0]["content"] == [{"type": "text", "text": source}]


def test_jira_mention_ids_are_preserved_opaquely(adf_validator: Validator) -> None:
    result = markdown_to_adf(
        "[~accountId:first:opaque-id][~ACCOUNTID:Second:opaque:id]"
        "[~accountId:pipe|opaque-id]",
        jira_mentions=True,
    )

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "mention", "attrs": {"id": "first:opaque-id"}},
        {"type": "mention", "attrs": {"id": "Second:opaque:id"}},
        {"type": "mention", "attrs": {"id": "pipe|opaque-id"}},
    ]


@pytest.mark.parametrize(
    "source",
    [
        "[~accountId:]",
        "[~accountId:contains space]",
        "[~accountId:contains\tspace]",
        r"[~accountId:contains\backslash]",
        "[~accountId:unclosed",
        "[~userId:opaque-id]",
        "@Display Name",
    ],
)
def test_malformed_jira_mentions_remain_text(source: str) -> None:
    result = markdown_to_adf(source, jira_mentions=True)

    assert result["content"][0]["content"] == [{"type": "text", "text": source}]


def test_repeated_boundary_terminated_malformed_jira_mentions_remain_text() -> None:
    source = "[~accountId:x z" * 64

    result = markdown_to_adf(source, jira_mentions=True)

    assert result["content"][0]["content"] == [{"type": "text", "text": source}]


def test_merge_adjacent_text_nodes_preserves_runs_and_first_node_mutation() -> None:
    first: AdfNode = {"type": "text", "text": "plain "}
    second: AdfNode = {"type": "text", "text": "text"}
    strong_first: AdfNode = {
        "type": "text",
        "text": "strong ",
        "marks": [{"type": "strong"}],
    }
    strong_second: AdfNode = {
        "type": "text",
        "text": "text",
        "marks": [{"type": "strong"}],
    }
    mention: AdfNode = {"type": "mention", "attrs": {"id": "id"}}
    tail: AdfNode = {"type": "text", "text": "tail"}

    result = _merge_adjacent_text_nodes([
        first,
        second,
        strong_first,
        strong_second,
        mention,
        tail,
    ])

    assert result == [
        {"type": "text", "text": "plain text"},
        {
            "type": "text",
            "text": "strong text",
            "marks": [{"type": "strong"}],
        },
        mention,
        tail,
    ]
    assert result[0] is first
    assert result[1] is strong_first


def test_jira_mentions_respect_escape_and_code_contexts(
    adf_validator: Validator,
) -> None:
    result = markdown_to_adf(
        "\\[~accountId:escaped]\n\n"
        "`[~accountId:inline-code]`\n\n"
        "```\n[~accountId:fenced-code]\n```",
        jira_mentions=True,
    )

    adf_validator.validate(result)
    assert result["content"] == [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "[~accountId:escaped]"}],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "[~accountId:inline-code]",
                    "marks": [{"type": "code"}],
                }
            ],
        },
        {
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": "[~accountId:fenced-code]"}],
        },
    ]


def test_jira_mentions_are_bare_inside_formatting(adf_validator: Validator) -> None:
    result = markdown_to_adf(
        "**before [~accountId:opaque-id] after**",
        jira_mentions=True,
    )

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "text", "text": "before ", "marks": [{"type": "strong"}]},
        {"type": "mention", "attrs": {"id": "opaque-id"}},
        {"type": "text", "text": " after", "marks": [{"type": "strong"}]},
    ]


def test_jira_mention_link_context_remains_non_mention(
    adf_validator: Validator,
) -> None:
    result = markdown_to_adf(
        "[label [~accountId:linked-id]](https://example.test)",
        jira_mentions=True,
    )

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {
            "type": "text",
            "text": "label [~accountId:linked-id]",
            "marks": [{"type": "link", "attrs": {"href": "https://example.test"}}],
        }
    ]


@pytest.mark.parametrize(
    ("source", "expected_alt"),
    [
        (
            "![**bold** before [~accountId:id] after](image.png)",
            "bold before [~accountId:id] after",
        ),
        (
            "![before **bold** [~accountId:id] after](image.png)",
            "before bold [~accountId:id] after",
        ),
        (
            "![before [~accountId:id] after **bold**](image.png)",
            "before [~accountId:id] after bold",
        ),
        (
            "![pre ***bold [~accountId:id] text*** post](image.png)",
            "pre bold [~accountId:id] text post",
        ),
    ],
)
def test_jira_mention_image_alt_preserves_complete_formatted_text(
    source: str,
    expected_alt: str,
    adf_validator: Validator,
) -> None:
    result = markdown_to_adf(source, jira_mentions=True)

    adf_validator.validate(result)
    assert result["content"][0]["content"][0]["attrs"]["alt"] == expected_alt
