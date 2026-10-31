"""Tests that run the LangChain callback through real LangChain models."""

import asyncio

import pytest

pytest.importorskip("langchain_core")

from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.language_models.llms import LLM
from langchain_core.runnables import RunnableLambda

from promptveil import SensitiveDataError, Shield
from promptveil.adapters import get_langchain_callback
from promptveil.policy.models import Action, PolicyConfig, Rule

EMAIL_PROMPT = "Contact bob@example.com"
MASKED_PROMPT = "Contact b***@example.com"
API_KEY_PROMPT = "Use sk-abcdefghijklmnopqrstuvwxyz1234"


class RecordingLLM(LLM):
    """String LLM that records the prompts it receives."""

    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "recording"

    def _call(self, prompt, stop=None, run_manager=None, **kwargs):
        self.seen.append(prompt)
        return "ok"


class RecordingChatModel(SimpleChatModel):
    """Chat model that records the last message content it receives."""

    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "recording"

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages[-1].content)
        return "ok"


async def _astream(runnable, prompt, **kwargs):
    return [chunk async for chunk in runnable.astream(prompt, **kwargs)]


ENTRY_POINTS = {
    "invoke": lambda m, p, c: m.invoke(p, config=c),
    "stream": lambda m, p, c: list(m.stream(p, config=c)),
    "batch": lambda m, p, c: m.batch([p], config=c),
    "ainvoke": lambda m, p, c: asyncio.run(m.ainvoke(p, config=c)),
    "astream": lambda m, p, c: asyncio.run(_astream(m, p, config=c)),
    "abatch": lambda m, p, c: asyncio.run(m.abatch([p], config=c)),
}


@pytest.fixture(params=sorted(ENTRY_POINTS))
def call(request):
    return ENTRY_POINTS[request.param]


@pytest.fixture
def config():
    shield = Shield(
        config=PolicyConfig(
            rules=[
                Rule(type="email", action=Action.MASK),
                Rule(type="api_key", action=Action.BLOCK),
            ],
        ),
    )
    return {"callbacks": [get_langchain_callback()(shield)]}


@pytest.fixture
def llm():
    return RecordingLLM(seen=[])


@pytest.fixture
def chat_model():
    return RecordingChatModel(seen=[])


def test_blocked_prompt_never_reaches_llm(call, config, llm):
    with pytest.raises(SensitiveDataError):
        call(llm, API_KEY_PROMPT, config)
    assert llm.seen == []


def test_blocked_prompt_never_reaches_chat_model(call, config, chat_model):
    with pytest.raises(SensitiveDataError):
        call(chat_model, API_KEY_PROMPT, config)
    assert chat_model.seen == []


def test_prompt_needing_masking_never_reaches_llm(call, config, llm):
    with pytest.raises(SensitiveDataError):
        call(llm, EMAIL_PROMPT, config)
    assert llm.seen == []


def test_chat_model_receives_masked_prompt(call, config, chat_model):
    call(chat_model, EMAIL_PROMPT, config)
    assert chat_model.seen == [MASKED_PROMPT]


def test_llm_receives_clean_prompt(call, config, llm):
    call(llm, "Hello", config)
    assert llm.seen == ["Hello"]


def test_llm_accepts_prompt_masked_by_shield(call, config, llm):
    shield = config["callbacks"][0]._shield
    call(RunnableLambda(shield.scan) | llm, EMAIL_PROMPT, config)
    assert llm.seen == [MASKED_PROMPT]
