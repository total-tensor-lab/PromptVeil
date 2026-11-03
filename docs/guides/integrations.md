---
id: integrations
title: Integrations
---

# Integrations

## OpenAI

```bash
pip install "promptveil[openai]"
```

```python
from openai import OpenAI
from promptveil.adapters import wrap_openai

client = wrap_openai(OpenAI(), shield)   # patches chat.completions.create
client.chat.completions.create(model="gpt-4o-mini", messages=[...])
```

Messages are scanned before sending; blocked prompts raise
`SensitiveDataError` and no request is made. Only string `content` on
`chat.completions.create` is scanned.

To scan the model's replies too, pass `scan_responses=True`. Works with both
`OpenAI` and `AsyncOpenAI`; streaming (`stream=True`) isn't supported in this
mode and raises `ConfigurationError`.

```python
client = wrap_openai(OpenAI(), shield, scan_responses=True)
```

## LangChain

```bash
pip install "promptveil[langchain]"
```

```python
from promptveil.adapters import get_langchain_callback

callback = get_langchain_callback()(shield)
chat_model.invoke(prompt, config={"callbacks": [callback]})
```

Chat models are masked in place. String LLMs can't be rewritten by a callback,
so pass `shield.scan(prompt)` yourself; a prompt needing masking raises.

## FastAPI / Starlette

```bash
pip install "promptveil[fastapi]"
```

```python
from fastapi import FastAPI
from promptveil.middleware import PromptVeilMiddleware

app = FastAPI()
app.add_middleware(PromptVeilMiddleware, shield=shield, prompt_field="prompt")
```

POST requests with a JSON `prompt` field are masked; blocked prompts get a
`400` with code `SENSITIVE_DATA_BLOCKED`. Nested fields are not scanned.

To scan replies too, pass `response_field`. The field is masked in 2xx JSON
responses; blocked replies get a `502` with code
`SENSITIVE_DATA_BLOCKED_RESPONSE`.

```python
app.add_middleware(
    PromptVeilMiddleware, shield=shield,
    prompt_field="prompt", response_field="response",
)
```

Full details and limitations: [API reference](../api-reference.md#integrations).
