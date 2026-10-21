"""Thin wrapper around the xAI Responses API with server-side web_search / x_search tools."""
import json
import re
import urllib.error
import urllib.request

import config

API_URL = "https://api.x.ai/v1/responses"


class LLMError(RuntimeError):
    pass


def ask(prompt, tools=("web_search",), system=None):
    """Return (text, citations). tools: any of "web_search", "x_search"."""
    if config.DEMO:
        import demo
        return demo.answer(prompt), ["https://example.com/demo-source"]
    if not config.XAI_API_KEY:
        raise LLMError("XAI_API_KEY is not set (or run with MOGUL_DEMO=1)")
    body = {"model": config.XAI_MODEL, "input": prompt, "tools": [{"type": t} for t in tools]}
    if system:
        body["input"] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {config.XAI_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        raise LLMError(f"xAI API {e.code}: {e.read()[:500]!r}") from e
    text = "".join(
        c.get("text", "")
        for item in resp.get("output", []) if item.get("type") == "message"
        for c in item.get("content", []) if c.get("type") == "output_text"
    )
    return text, resp.get("citations", [])


def ask_json(prompt, tools=("web_search",)):
    """Ask for a JSON answer and parse the first JSON object/array in the reply."""
    text, citations = ask(prompt + "\n\nReply with JSON only, no prose.", tools)
    return extract_json(text), citations


def extract_json(text):
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise LLMError(f"no JSON in model reply: {text[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj
