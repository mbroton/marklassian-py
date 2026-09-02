import copy
import uuid
from re import Match
from typing import Any

import mistune
from mistune.plugins import PluginRef

from .types import AdfDocument, AdfMark, AdfNode

_JIRA_MENTION_PATTERN = r"\[~(?i:accountid):(?P<id>[^\s\\\]\r\n]+)\]"


def _parse_jira_mention(
    _: mistune.InlineParser,
    match: Match[str],
    state: mistune.InlineState,
) -> int:
    if state.in_link or state.in_image:
        state.append_token({"type": "text", "raw": match.group(0)})
    else:
        state.append_token(
            {
                "type": "jira_mention",
                "attrs": {"id": match.group("id")},
            }
        )
    return match.end()


def _jira_mentions(md: mistune.Markdown) -> None:
    md.inline.register(
        "jira_mention",
        _JIRA_MENTION_PATTERN,
        _parse_jira_mention,
        before="link",
    )


def _generate_local_id() -> str:
    return str(uuid.uuid4())


def _get_safe_text(token: dict[str, Any]) -> str:
    children = token.get("children")
    if children and len(children) == 1:
        return _get_safe_text(children[0])

    if children:
        texts = [_get_safe_text(child) for child in children]
        return "".join(texts)

    raw = token.get("raw", "")
    if isinstance(raw, str):
        text = raw.rstrip("\n")
        return text.replace("\n", " ")
    return ""


def _add_mark(marks: list[AdfMark], mark: AdfMark) -> list[AdfMark]:
    if any(existing["type"] == mark["type"] for existing in marks):
        return marks
    return [*marks, mark]


def _create_text_node(text: str, marks: list[AdfMark]) -> AdfNode:
    node: AdfNode = {"type": "text", "text": text}
    if marks:
        node["marks"] = copy.deepcopy(marks)
    return node


def _create_media_node(token: dict[str, Any]) -> AdfNode:
    attrs = token.get("attrs", {})
    children = token.get("children", [])
    alt_text = ""
    if children and children[0].get("type") == "text":
        alt_text = children[0].get("raw", "")
    return {
        "type": "mediaSingle",
        "attrs": {"layout": "center"},
        "content": [
            {
                "type": "media",
                "attrs": {
                    "type": "external",
                    "url": attrs.get("url", ""),
                    "alt": alt_text,
                },
            }
        ],
    }


def _merge_adjacent_text_nodes(nodes: list[AdfNode]) -> list[AdfNode]:
    if not nodes:
        return []

    result: list[AdfNode] = []
    for node in nodes:
        if node.get("type") != "text":
            result.append(node)
            continue

        if not result:
            result.append(node)
            continue

        prev = result[-1]
        if prev.get("type") != "text":
            result.append(node)
            continue

        prev_marks = prev.get("marks", [])
        curr_marks = node.get("marks", [])
        if prev_marks != curr_marks:
            result.append(node)
            continue

        prev["text"] = prev.get("text", "") + node.get("text", "")

    return result


def _inline_to_adf(
    tokens: list[dict[str, Any]] | None,
    marks: list[AdfMark] | None = None,
) -> list[AdfNode]:
    if not tokens:
        return []

    if marks is None:
        marks = []

    result: list[AdfNode] = []

    for token in tokens:
        token_type = token.get("type", "")

        if token_type == "text":
            children = token.get("children")
            if children:
                result.extend(_inline_to_adf(children, marks))
            else:
                text = _get_safe_text(token)
                if text:
                    result.append(_create_text_node(text, marks))

        elif token_type == "emphasis":
            result.extend(
                _inline_to_adf(
                    token.get("children", []),
                    _add_mark(marks, {"type": "em"}),
                )
            )

        elif token_type == "strong":
            result.extend(
                _inline_to_adf(
                    token.get("children", []),
                    _add_mark(marks, {"type": "strong"}),
                )
            )

        elif token_type == "strikethrough":
            result.extend(
                _inline_to_adf(
                    token.get("children", []),
                    _add_mark(marks, {"type": "strike"}),
                )
            )

        elif token_type == "link":
            link_mark: AdfMark = {
                "type": "link",
                "attrs": {"href": token.get("attrs", {}).get("url", "")},
            }
            result.extend(
                _inline_to_adf(
                    token.get("children", []),
                    _add_mark(marks, link_mark),
                )
            )

        elif token_type == "codespan":
            text = _get_safe_text(token)
            if text:
                code_marks = [mark for mark in marks if mark["type"] == "link"]
                code_marks = _add_mark(code_marks, {"type": "code"})
                result.append(_create_text_node(text, code_marks))

        elif token_type == "image":
            alt_text = _get_safe_text(token)
            if alt_text:
                result.append(_create_text_node(alt_text, marks))

        elif token_type == "jira_mention":
            result.append(
                {
                    "type": "mention",
                    "attrs": {"id": token["attrs"]["id"]},
                }
            )

        elif token_type == "linebreak":
            result.append({"type": "hardBreak"})

        elif token_type == "softbreak":
            result.append(_create_text_node(" ", marks))

        elif token_type == "block_text":
            result.extend(_inline_to_adf(token.get("children", []), marks))

    filtered = [node for node in result if not (node.get("type") == "text" and not node.get("text"))]
    return _merge_adjacent_text_nodes(filtered)


def _strip_trailing_softbreaks(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    while tokens and tokens[-1].get("type") == "softbreak":
        tokens = tokens[:-1]
    return tokens


def _process_paragraph(tokens: list[dict[str, Any]] | None) -> list[AdfNode]:
    if not tokens:
        return []

    if len(tokens) == 1 and tokens[0].get("type") == "image":
        return [_create_media_node(tokens[0])]

    output_nodes: list[AdfNode] = []
    current_paragraph_tokens: list[dict[str, Any]] = []

    for token in tokens:
        if token.get("type") == "image":
            if current_paragraph_tokens:
                trimmed = _strip_trailing_softbreaks(current_paragraph_tokens)
                if trimmed:
                    output_nodes.append({
                        "type": "paragraph",
                        "content": _inline_to_adf(trimmed),
                    })
                current_paragraph_tokens = []
            output_nodes.append(_create_media_node(token))
        else:
            current_paragraph_tokens.append(token)

    if current_paragraph_tokens:
        output_nodes.append({
            "type": "paragraph",
            "content": _inline_to_adf(current_paragraph_tokens),
        })

    return output_nodes


def _is_task_list(items: list[dict[str, Any]]) -> bool:
    if not items:
        return False
    return all(item.get("type") == "task_list_item" for item in items)


_INLINE_TOKEN_TYPES = {
    "text",
    "emphasis",
    "strong",
    "strikethrough",
    "link",
    "jira_mention",
    "codespan",
    "block_text",
}


def _contains_image(token: dict[str, Any]) -> bool:
    if token.get("type") == "image":
        return True
    return any(_contains_image(child) for child in token.get("children", []))


def _task_item_requires_list_fallback(item: dict[str, Any]) -> bool:
    nested_task_list_seen = False

    for token in item.get("children", []):
        token_type = token.get("type", "")
        if token_type == "blank_line":
            continue

        if token_type in _INLINE_TOKEN_TYPES or token_type == "paragraph":
            if nested_task_list_seen or _contains_image(token):
                return True
            continue

        if token_type == "list":
            items = token.get("children", [])
            if _is_task_list(items) and not _task_list_requires_list_fallback(items):
                nested_task_list_seen = True
                continue

        return True

    return False


def _task_list_requires_list_fallback(items: list[dict[str, Any]]) -> bool:
    return any(_task_item_requires_list_fallback(item) for item in items)


def _process_task_item(item: dict[str, Any]) -> list[AdfNode]:
    paragraphs: list[list[AdfNode]] = []
    nested_task_lists: list[AdfNode] = []
    current_paragraph_tokens: list[dict[str, Any]] = []

    def flush_current_paragraph() -> None:
        nonlocal current_paragraph_tokens
        if current_paragraph_tokens:
            paragraphs.append(_inline_to_adf(current_paragraph_tokens))
            current_paragraph_tokens = []

    for token in item.get("children", []):
        token_type = token.get("type", "")

        if token_type in _INLINE_TOKEN_TYPES:
            current_paragraph_tokens.append(token)
        elif token_type == "paragraph":
            flush_current_paragraph()
            paragraphs.append(_inline_to_adf(token.get("children", [])))
        elif token_type == "blank_line":
            flush_current_paragraph()
        elif token_type == "list":
            flush_current_paragraph()
            nested_task_lists.append(_create_task_list(token.get("children", [])))

    flush_current_paragraph()

    checked = item.get("attrs", {}).get("checked", False)
    attrs = {
        "localId": _generate_local_id(),
        "state": "DONE" if checked else "TODO",
    }

    if len(paragraphs) > 1:
        block_paragraphs: list[AdfNode] = []
        for content in paragraphs:
            paragraph: AdfNode = {"type": "paragraph"}
            if content:
                paragraph["content"] = content
            block_paragraphs.append(paragraph)

        task_item: AdfNode = {
            "type": "blockTaskItem",
            "attrs": attrs,
            "content": block_paragraphs,
        }
    else:
        task_item = {
            "type": "taskItem",
            "attrs": attrs,
            "content": paragraphs[0] if paragraphs else [],
        }

    return [task_item, *nested_task_lists]


def _create_task_list(items: list[dict[str, Any]]) -> AdfNode:
    content: list[AdfNode] = []
    for item in items:
        content.extend(_process_task_item(item))

    return {
        "type": "taskList",
        "attrs": {"localId": _generate_local_id()},
        "content": content,
    }


def _process_task_item_as_list_item(item: dict[str, Any]) -> AdfNode:
    list_item = _process_list_item(item)
    marker = "[x] " if item.get("attrs", {}).get("checked", False) else "[ ] "
    item_content = list_item["content"]

    if item_content and item_content[0].get("type") == "paragraph":
        paragraph = item_content[0]
        paragraph_content = paragraph.get("content", [])
        if paragraph_content:
            paragraph["content"] = _merge_adjacent_text_nodes([
                {"type": "text", "text": marker},
                *paragraph_content,
            ])
        else:
            paragraph["content"] = [{"type": "text", "text": marker.rstrip()}]
    else:
        item_content.insert(0, {
            "type": "paragraph",
            "content": [{"type": "text", "text": marker.rstrip()}],
        })

    return list_item


def _prefix_paragraph(node: AdfNode, prefix: str) -> None:
    if node.get("type") != "paragraph":
        return

    content = node.get("content", [])
    if content:
        node["content"] = _merge_adjacent_text_nodes([
            {"type": "text", "text": prefix},
            *content,
        ])
    else:
        node["content"] = [{"type": "text", "text": prefix.rstrip()}]


def _block_token_to_list_item_adf(token: dict[str, Any]) -> list[AdfNode]:
    token_type = token.get("type", "")

    if token_type == "block_text":
        return _process_paragraph(token.get("children", []))

    if token_type == "heading":
        level = token.get("attrs", {}).get("level", 1)
        paragraph: AdfNode = {
            "type": "paragraph",
            "content": _inline_to_adf(token.get("children", [])),
        }
        _prefix_paragraph(paragraph, f"{'#' * level} ")
        return [paragraph]

    if token_type == "block_quote":
        content: list[AdfNode] = []
        for child in token.get("children", []):
            content.extend(_block_token_to_list_item_adf(child))
        if not content:
            content = [{"type": "paragraph"}]

        quoted_content: list[AdfNode] = []
        for node in content:
            if node.get("type") == "paragraph":
                _prefix_paragraph(node, "> ")
            else:
                quoted_content.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": ">"}],
                })
            quoted_content.append(node)
        return quoted_content

    if token_type == "thematic_break":
        return [{
            "type": "paragraph",
            "content": [{"type": "text", "text": "---"}],
        }]

    if token_type == "table":
        text = _get_safe_text(token)
        if text:
            return [{
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }]
        return []

    return _tokens_to_adf([token])


def _process_list_item(item: dict[str, Any]) -> AdfNode:
    item_content: list[AdfNode] = []
    current_paragraph_tokens: list[dict[str, Any]] = []

    for token in item.get("children", []):
        token_type = token.get("type", "")

        if token_type in _INLINE_TOKEN_TYPES and not _contains_image(token):
            current_paragraph_tokens.append(token)
        else:
            if current_paragraph_tokens:
                item_content.append({
                    "type": "paragraph",
                    "content": _inline_to_adf(current_paragraph_tokens),
                })
                current_paragraph_tokens = []

            if token_type == "list":
                list_items = token.get("children", [])
                if _is_task_list(list_items) and not _task_list_requires_list_fallback(list_items):
                    item_content.append(_create_task_list(list_items))
                else:
                    item_content.append(_create_regular_list(token))
            else:
                item_content.extend(_block_token_to_list_item_adf(token))

    if current_paragraph_tokens:
        item_content.append({
            "type": "paragraph",
            "content": _inline_to_adf(current_paragraph_tokens),
        })

    if not item_content:
        item_content.append({"type": "paragraph"})

    return {
        "type": "listItem",
        "content": item_content,
    }


def _create_regular_list(token: dict[str, Any]) -> AdfNode:
    items = token.get("children", [])
    content = [
        _process_task_item_as_list_item(item)
        if item.get("type") == "task_list_item"
        else _process_list_item(item)
        for item in items
    ]
    is_ordered = token.get("attrs", {}).get("ordered", False)
    list_node: AdfNode = {
        "type": "orderedList" if is_ordered else "bulletList",
        "content": content,
    }
    if is_ordered:
        list_node["attrs"] = {"order": token.get("attrs", {}).get("start", 1)}
    return list_node


def _process_table_cell_content(children: list[dict[str, Any]]) -> list[AdfNode]:
    if not children:
        return [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]

    has_image = any(child.get("type") == "image" for child in children)
    if has_image:
        return _process_paragraph(children)

    inline_content = _inline_to_adf(children)
    if not inline_content:
        return [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]

    return [{"type": "paragraph", "content": inline_content}]


def _process_table(token: dict[str, Any]) -> AdfNode:
    content: list[AdfNode] = []

    for child in token.get("children", []):
        child_type = child.get("type", "")

        if child_type == "table_head":
            headers: list[AdfNode] = []
            for cell in child.get("children", []):
                if cell.get("type") == "table_cell":
                    cell_content = _process_table_cell_content(cell.get("children", []))
                    headers.append({
                        "type": "tableHeader",
                        "content": cell_content,
                    })
            if headers:
                content.append({"type": "tableRow", "content": headers})

        elif child_type == "table_body":
            for row in child.get("children", []):
                cells: list[AdfNode] = []
                for cell in row.get("children", []):
                    if cell.get("type") == "table_cell":
                        cell_content = _process_table_cell_content(cell.get("children", []))
                        cells.append({"type": "tableCell", "content": cell_content})
                if cells:
                    content.append({"type": "tableRow", "content": cells})

    return {"type": "table", "content": content}


def _tokens_to_adf(tokens: list[dict[str, Any]] | None) -> list[AdfNode]:
    if not tokens:
        return []

    result: list[AdfNode] = []

    for token in tokens:
        token_type = token.get("type", "")

        if token_type == "paragraph":
            result.extend(_process_paragraph(token.get("children", [])))

        elif token_type == "heading":
            level = token.get("attrs", {}).get("level", 1)
            result.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": _inline_to_adf(token.get("children", [])),
            })

        elif token_type == "list":
            list_items = token.get("children", [])
            if _is_task_list(list_items):
                if _task_list_requires_list_fallback(list_items):
                    result.append(_create_regular_list(token))
                else:
                    result.append(_create_task_list(list_items))
            else:
                result.append(_create_regular_list(token))

        elif token_type == "block_code":
            info_words = token.get("attrs", {}).get("info", "").split(maxsplit=1)
            lang = info_words[0] if info_words else "text"
            raw_text = token.get("raw", "").removesuffix("\n")
            code_block: AdfNode = {
                "type": "codeBlock",
                "attrs": {"language": lang},
            }
            if raw_text:
                code_block["content"] = [{"type": "text", "text": raw_text}]
            result.append(code_block)

        elif token_type == "block_quote":
            content = _tokens_to_adf(token.get("children", []))
            if not content:
                content = [{"type": "paragraph"}]
            result.append({
                "type": "blockquote",
                "content": content,
            })

        elif token_type == "thematic_break":
            result.append({"type": "rule"})

        elif token_type == "table":
            result.append(_process_table(token))

    return result


def markdown_to_adf(markdown: str, *, jira_mentions: bool = False) -> AdfDocument:
    plugins: list[PluginRef] = ["strikethrough", "table", "task_lists"]
    if jira_mentions:
        plugins.append(_jira_mentions)

    md = mistune.create_markdown(
        renderer=None,
        plugins=plugins,
    )
    result = md(markdown)
    tokens: list[dict[str, Any]] = result if isinstance(result, list) else []

    return {
        "version": 1,
        "type": "doc",
        "content": _tokens_to_adf(tokens),
    }
