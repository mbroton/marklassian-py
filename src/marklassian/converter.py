import re
import uuid
from typing import Any

import mistune

from .types import AdfDocument, AdfMark, AdfNode


def _generate_local_id() -> str:
    return str(uuid.uuid4())


def _get_safe_text(token: dict[str, Any]) -> str:
    children = token.get("children")
    if children and len(children) == 1:
        return _get_safe_text(children[0])

    if children:
        texts = [_get_safe_text(child) for child in children]
        combined = "".join(texts)
        return re.sub(r"\s+", " ", combined)

    raw = token.get("raw", "")
    if isinstance(raw, str):
        text = raw.rstrip("\n")
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text
    return ""


def _get_marks(token: dict[str, Any], marks: dict[str, AdfMark] | None = None) -> list[AdfMark]:
    if marks is None:
        marks = {}

    token_type = token.get("type", "")

    if token_type == "emphasis" and "em" not in marks:
        marks["em"] = {"type": "em"}

    if token_type == "strong" and "strong" not in marks:
        marks["strong"] = {"type": "strong"}

    if token_type == "strikethrough" and "strike" not in marks:
        marks["strike"] = {"type": "strike"}

    if token_type == "link":
        marks["link"] = {"type": "link", "attrs": {"href": token.get("attrs", {}).get("url", "")}}

    if token_type == "codespan" and "code" not in marks:
        marks["code"] = {"type": "code"}

    children = token.get("children", [])
    if children and len(children) == 1:
        return _get_marks(children[0], marks)

    resolved_marks = list(marks.values())

    if "code" in marks:
        return [m for m in resolved_marks if m["type"] in ("link", "code")]

    return resolved_marks


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


def _inline_to_adf(tokens: list[dict[str, Any]] | None) -> list[AdfNode]:
    if not tokens:
        return []

    result: list[AdfNode] = []

    for token in tokens:
        token_type = token.get("type", "")

        if token_type == "text":
            children = token.get("children")
            if children:
                result.extend(_inline_to_adf(children))
            else:
                text = _get_safe_text(token)
                if text:
                    result.append({"type": "text", "text": text})

        elif token_type == "emphasis":
            children = token.get("children", [])
            for child in children:
                text = _get_safe_text(child)
                if text:
                    result.append({
                        "type": "text",
                        "text": text,
                        "marks": _get_marks(child, {"em": {"type": "em"}}),
                    })

        elif token_type == "strong":
            children = token.get("children", [])
            for child in children:
                text = _get_safe_text(child)
                if text:
                    result.append({
                        "type": "text",
                        "text": text,
                        "marks": _get_marks(child, {"strong": {"type": "strong"}}),
                    })

        elif token_type == "strikethrough":
            children = token.get("children", [])
            for child in children:
                text = _get_safe_text(child)
                if text:
                    result.append({
                        "type": "text",
                        "text": text,
                        "marks": _get_marks(child, {"strike": {"type": "strike"}}),
                    })

        elif token_type == "link":
            text = _get_safe_text(token)
            if text:
                result.append({
                    "type": "text",
                    "text": text,
                    "marks": _get_marks(token),
                })

        elif token_type == "codespan":
            text = _get_safe_text(token)
            if text:
                result.append({
                    "type": "text",
                    "text": text,
                    "marks": _get_marks(token),
                })

        elif token_type == "linebreak":
            result.append({"type": "hardBreak"})

        elif token_type == "softbreak":
            result.append({"type": "text", "text": " "})

        elif token_type == "block_text":
            result.extend(_inline_to_adf(token.get("children", [])))

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


def _process_task_item(item: dict[str, Any]) -> AdfNode:
    item_content: list[AdfNode] = []
    current_paragraph_tokens: list[dict[str, Any]] = []

    inline_types = {"text", "emphasis", "strong", "strikethrough", "link", "codespan", "block_text"}

    for token in item.get("children", []):
        token_type = token.get("type", "")

        if token_type in inline_types:
            current_paragraph_tokens.append(token)
        else:
            if current_paragraph_tokens:
                item_content.extend(_inline_to_adf(current_paragraph_tokens))
                current_paragraph_tokens = []

            if token_type == "list":
                list_items = token.get("children", [])
                if _is_task_list(list_items):
                    item_content.append({
                        "type": "taskList",
                        "attrs": {"localId": _generate_local_id()},
                        "content": [_process_task_item(li) for li in list_items],
                    })
                else:
                    is_ordered = token.get("attrs", {}).get("ordered", False)
                    start = token.get("attrs", {}).get("start", 1)
                    list_node: AdfNode = {
                        "type": "orderedList" if is_ordered else "bulletList",
                        "content": [_process_list_item(li) for li in list_items],
                    }
                    if is_ordered:
                        list_node["attrs"] = {"order": start}
                    item_content.append(list_node)
            else:
                processed = _tokens_to_adf([token])
                item_content.extend(processed)

    if current_paragraph_tokens:
        item_content.extend(_inline_to_adf(current_paragraph_tokens))

    checked = item.get("attrs", {}).get("checked", False)
    return {
        "type": "taskItem",
        "attrs": {
            "localId": _generate_local_id(),
            "state": "DONE" if checked else "TODO",
        },
        "content": item_content,
    }


def _process_list_item(item: dict[str, Any]) -> AdfNode:
    item_content: list[AdfNode] = []
    current_paragraph_tokens: list[dict[str, Any]] = []

    inline_types = {"text", "emphasis", "strong", "strikethrough", "link", "codespan", "block_text"}

    for token in item.get("children", []):
        token_type = token.get("type", "")

        if token_type in inline_types:
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
                if _is_task_list(list_items):
                    item_content.append({
                        "type": "taskList",
                        "attrs": {"localId": _generate_local_id()},
                        "content": [_process_task_item(li) for li in list_items],
                    })
                else:
                    is_ordered = token.get("attrs", {}).get("ordered", False)
                    start = token.get("attrs", {}).get("start", 1)
                    list_node: AdfNode = {
                        "type": "orderedList" if is_ordered else "bulletList",
                        "content": [_process_list_item(li) for li in list_items],
                    }
                    if is_ordered:
                        list_node["attrs"] = {"order": start}
                    item_content.append(list_node)
            else:
                processed = _tokens_to_adf([token])
                item_content.extend(processed)

    if current_paragraph_tokens:
        item_content.append({
            "type": "paragraph",
            "content": _inline_to_adf(current_paragraph_tokens),
        })

    return {
        "type": "listItem",
        "content": item_content,
    }


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
                result.append({
                    "type": "taskList",
                    "attrs": {"localId": _generate_local_id()},
                    "content": [_process_task_item(item) for item in list_items],
                })
            else:
                is_ordered = token.get("attrs", {}).get("ordered", False)
                start = token.get("attrs", {}).get("start", 1)
                list_node: AdfNode = {
                    "type": "orderedList" if is_ordered else "bulletList",
                    "content": [_process_list_item(item) for item in list_items],
                }
                if is_ordered:
                    list_node["attrs"] = {"order": start}
                result.append(list_node)

        elif token_type == "block_code":
            lang = token.get("attrs", {}).get("info", "") or "text"
            raw_text = token.get("raw", "")
            if raw_text.endswith("\n"):
                raw_text = raw_text[:-1]
            result.append({
                "type": "codeBlock",
                "attrs": {"language": lang},
                "content": [{"type": "text", "text": raw_text}],
            })

        elif token_type == "block_quote":
            result.append({
                "type": "blockquote",
                "content": _tokens_to_adf(token.get("children", [])),
            })

        elif token_type == "thematic_break":
            result.append({"type": "rule"})

        elif token_type == "table":
            result.append(_process_table(token))

    return result


def markdown_to_adf(markdown: str) -> AdfDocument:
    md = mistune.create_markdown(
        renderer=None,
        plugins=["strikethrough", "table", "task_lists"],
    )
    result = md(markdown)
    tokens: list[dict[str, Any]] = result if isinstance(result, list) else []

    return {
        "version": 1,
        "type": "doc",
        "content": _tokens_to_adf(tokens),
    }
