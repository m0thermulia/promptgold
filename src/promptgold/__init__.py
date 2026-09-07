"""promptgold — pytest for prompts."""

from promptgold import adversarial
from promptgold.assertions import contains, judge, matches
from promptgold.core import prompt_test
from promptgold.models import Model

__version__ = "0.1.0"
__all__ = [
    "prompt_test",
    "contains",
    "matches",
    "judge",
    "Model",
    "adversarial",
    "__version__",
]
