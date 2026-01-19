from importlib.metadata import version

from .converter import markdown_to_adf
from .types import AdfDocument, AdfMark, AdfNode

__all__ = ["markdown_to_adf", "AdfDocument", "AdfMark", "AdfNode"]
__version__ = version("marklassian")
