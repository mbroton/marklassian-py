# marklassian-py

A lightweight Python library that converts Markdown to the [Atlassian Document Format (ADF)](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/). Built for easy integration with Atlassian products like Jira and Confluence.

This is a Python port of the excellent [marklassian](https://github.com/jamsinclair/marklassian) JavaScript library by [@jamsinclair](https://github.com/jamsinclair).

## Features

- Convert Markdown to ADF with a single function call
- Support for common Markdown syntax including GFM task lists
- Minimal dependencies (only [mistune](https://github.com/lepture/mistune))
- Full type hints for IDE support
- Python 3.10+

## Installation

```bash
pip install marklassian
```

Or with uv:

```bash
uv add marklassian
```

## Usage

```python
from marklassian import markdown_to_adf

markdown = "# Hello World\n\nThis is **bold** and *italic* text."
adf = markdown_to_adf(markdown)
```

The result is a dictionary that can be serialized to JSON:

```python
import json
print(json.dumps(adf, indent=2))
```

## Supported Markdown Features

- Headings (H1-H6)
- Paragraphs and line breaks
- Emphasis (bold, italic, strikethrough)
- Links and images
- Inline code and code blocks with language support
- Ordered and unordered lists with nesting
- Blockquotes
- Horizontal rules
- Tables
- Task lists (GitHub Flavored Markdown)

## API Reference

### `markdown_to_adf(markdown: str) -> AdfDocument`

Converts a Markdown string to an ADF document object.

### Types

```python
from marklassian import AdfDocument, AdfNode, AdfMark

# AdfDocument is a TypedDict with:
# - version: Literal[1]
# - type: Literal["doc"]
# - content: list[AdfNode]

# AdfNode is a TypedDict with:
# - type: str (required)
# - attrs: dict[str, Any] (optional)
# - content: list[AdfNode] (optional)
# - marks: list[AdfMark] (optional)
# - text: str (optional)

# AdfMark is a TypedDict with:
# - type: str (required)
# - attrs: dict[str, Any] (optional)
```

## Caveats

This library aims to provide a lightweight and mostly accurate conversion from Markdown to ADF.

For complex Markdown documents or strict ADF conformance requirements, consider using the official Atlassian libraries. Note that those are heavier dependencies.

## References

- [Atlassian Document Format Reference](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
- [ADF Interactive Builder](https://developer.atlassian.com/cloud/jira/platform/apis/document/playground/)
- [Original marklassian (JavaScript)](https://github.com/jamsinclair/marklassian)

## Credits

This library is a Python port of [marklassian](https://github.com/jamsinclair/marklassian) by [Jamie Sinclair](https://github.com/jamsinclair). All credit for the original implementation and conversion logic goes to them.

## License

MIT - see [LICENSE](LICENSE) for details.
