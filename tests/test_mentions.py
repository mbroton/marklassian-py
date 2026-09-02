import pytest
from jsonschema.protocols import Validator

from marklassian import markdown_to_adf


def test_jira_mentions_are_default_off() -> None:
    source = "[~accountId:opaque-id]"

    result = markdown_to_adf(source)

    assert result["content"][0]["content"] == [{"type": "text", "text": source}]


def test_jira_mentions_default_off_preserves_existing_image_alt_behavior() -> None:
    result = markdown_to_adf("![alt **bold** tail](image.png)")

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


def test_jira_mention_prefix_is_case_insensitive(adf_validator: Validator) -> None:
    result = markdown_to_adf("[~ACCOUNTID:opaque-id]", jira_mentions=True)

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "mention", "attrs": {"id": "opaque-id"}},
    ]


def test_jira_mention_ids_are_preserved_opaquely(adf_validator: Validator) -> None:
    result = markdown_to_adf(
        "[~accountId:first:opaque-id][~ACCOUNTID:Second:opaque:id]",
        jira_mentions=True,
    )

    adf_validator.validate(result)
    assert result["content"][0]["content"] == [
        {"type": "mention", "attrs": {"id": "first:opaque-id"}},
        {"type": "mention", "attrs": {"id": "Second:opaque:id"}},
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


def test_jira_mention_link_and_image_contexts_remain_non_mentions(
    adf_validator: Validator,
) -> None:
    result = markdown_to_adf(
        "[label [~accountId:linked-id]](https://example.test)\n\n"
        "![alt [~accountId:image-id]](https://example.test/image.png)",
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
    assert result["content"][1]["content"][0]["attrs"]["alt"] == "alt "
