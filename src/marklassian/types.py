from typing import Any, Literal, Required, TypedDict


class AdfMark(TypedDict, total=False):
    type: Required[str]
    attrs: dict[str, Any]


class AdfNode(TypedDict, total=False):
    type: Required[str]
    attrs: dict[str, Any]
    content: list["AdfNode"]
    marks: list[AdfMark]
    text: str


class AdfDocument(TypedDict):
    version: Literal[1]
    type: Literal["doc"]
    content: list[AdfNode]
