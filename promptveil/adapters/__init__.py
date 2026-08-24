"""Framework-native adapters for PromptVeil.

Available adapters
------------------
``wrap_openai``            Patch an OpenAI client's chat completions method.
``get_langchain_callback`` Build a LangChain BaseCallbackHandler subclass.

Both adapters have soft dependencies on their respective frameworks — they
raise ``ImportError`` only when actually called, so importing this package
does not require ``openai`` or ``langchain-core`` to be installed.
"""

from .langchain_adapter import get_langchain_callback
from .openai_adapter import wrap_openai

__all__ = [
    "wrap_openai",
    "get_langchain_callback",
]
