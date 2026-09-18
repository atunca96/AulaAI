"""The one way this package talks to a model.

Everything the old `_call_ai` did across 180 lines and six provider special
cases, for the one provider and one model this system now uses. What is
deliberately different:

* **Usage is requested, not guessed.** The request carries
  ``"usage": {"include": true}``, so OpenRouter returns what the call actually
  cost and how much of the input was served from cache. The old pipeline never
  asked, so it never got a cost back, so its hand-maintained rate table did all
  the accounting — and that table was wrong by half for the model it was
  pricing. A ledger fed by measurements is worth having; one fed by estimates
  is a second opinion about your own invoice.

* **The cache breakpoint is explicit.** A plain string ``content`` is nothing to
  remember; the prefix is cached only when the request marks it. The system half
  of every prompt in this package is class-invariant by construction, so marking
  it is always correct here and the flag exists only so a caller with a
  per-request system prompt cannot accidentally poison a cache entry.

* **Failure is a value, not an exception.** `Response` carries the parsed body,
  the usage, and why it failed if it did. A generation step that cannot tell a
  refusal from a timeout from a truncation cannot decide whether retrying is
  worth paying for.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from services.authoring import budget as _budget

__all__ = ["Response", "call_model", "available", "extract_json"]

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class Response:
    """What one model call produced, including what it cost and how it failed."""

    __slots__ = ("data", "raw", "error", "truncated", "input_tokens", "output_tokens",
                 "cached_tokens", "cost", "model", "seconds")

    def __init__(self, *, data: Any = None, raw: str = "", error: str = "",
                 truncated: bool = False, input_tokens: int = 0, output_tokens: int = 0,
                 cached_tokens: int = 0, cost: Optional[float] = None,
                 model: str = "", seconds: float = 0.0):
        self.data = data
        self.raw = raw
        self.error = error
        self.truncated = truncated
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached_tokens = cached_tokens
        self.cost = cost
        self.model = model
        self.seconds = seconds

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.error


def available() -> bool:
    return len(os.getenv("OPENROUTER_API_KEY", "")) > 10


# ── JSON recovery ────────────────────────────────────────────────────────────

def extract_json(text: str) -> Optional[Any]:
    """Parse a JSON body out of a response that may be wrapped or truncated."""
    if not text:
        return None
    body = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    body = re.sub(r"```\s*$", "", body, flags=re.MULTILINE).strip()

    start_obj, start_arr = body.find("{"), body.find("[")
    if start_obj < 0 and start_arr < 0:
        return None
    if start_obj >= 0 and (start_arr < 0 or start_obj < start_arr):
        start, end = start_obj, body.rfind("}")
    else:
        start, end = start_arr, body.rfind("]")
    if start < 0 or end <= start:
        return None

    candidate = body[start:end + 1]
    try:
        return json.loads(candidate, strict=False)
    except Exception:
        pass
    return _salvage(body[start:])


def _open_brackets(text: str):
    """The still-open brackets of `text`, ignoring those inside string literals."""
    stack = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack and ((ch == "}" and stack[-1] == "{") or (ch == "]" and stack[-1] == "[")):
                stack.pop()
            else:
                return None  # unbalanced in a way closing cannot fix
    return None if in_string else stack


def _salvage(text: str):
    """Recover the complete entries of a JSON body that was cut off mid-answer.

    An assessment batch that ran out of tokens has written nine good items and
    half of a tenth. Throwing the whole answer away costs those nine and pays
    for them twice, so the closing brackets the model never reached are supplied
    here and the half-written tail is dropped.

    Walks the positions where an element genuinely ends — from the last one
    backwards — rather than guessing at a suffix, so the result is always a
    prefix of what the model actually said.
    """
    ends = [i for i, ch in enumerate(text) if ch in "}]"]
    for index in reversed(ends[-400:]):
        prefix = text[:index + 1]
        stack = _open_brackets(prefix)
        if stack is None:
            continue
        closing = "".join("}" if b == "{" else "]" for b in reversed(stack))
        try:
            return json.loads(prefix + closing, strict=False)
        except Exception:
            continue
    return None


def _cacheable(message: Dict[str, Any]) -> Dict[str, Any]:
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return message
    return {"role": message.get("role", "system"),
            "content": [{"type": "text", "text": content,
                         "cache_control": {"type": "ephemeral"}}]}


def _message_text(content: Any) -> str:
    """Normalize provider message content to plain text before JSON parsing.

    OpenRouter normally returns a string, but reasoning/structured-output routes
    may return content blocks. Calling str(list_of_blocks) produces Python repr,
    which is not JSON and was the direct cause of a fail-closed review build
    becoming "unparseable JSON body".
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                value = block.get("text")
                if isinstance(value, str):
                    parts.append(value)
                else:
                    value = block.get("content")
                    if isinstance(value, str):
                        parts.append(value)
        return "".join(parts)
    if isinstance(content, dict):
        for key in ("text", "content"):
            value = content.get(key)
            if isinstance(value, str):
                return value
    return ""


def _usage_of(payload: Dict[str, Any]) -> Dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    return {
        "input": int(usage.get("prompt_tokens") or 0),
        "output": int(usage.get("completion_tokens") or 0),
        "cached": int(details.get("cached_tokens") or usage.get("cached_tokens") or 0),
        "cost": usage.get("cost"),
    }


def call_model(messages: List[Dict[str, Any]], *, max_tokens: int,
               temperature: float = 0.6, model: str = "", cache_system: bool = True,
               timeout: Optional[int] = None, attempts: int = 3,
               reasoning_effort: Optional[str] = None,
               response_schema: Optional[Dict[str, Any]] = None,
               response_name: str = "aulaai_response") -> Response:
    """One call. Returns a Response whatever happens — never raises for a bad answer."""
    target = model or _budget.MODEL
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return Response(error="OPENROUTER_API_KEY missing", model=target)

    body = list(messages)
    # OpenAI prompt caching is automatic. Anthropic-style cache_control blocks
    # are useful for Claude but can make OpenAI upstream requests invalid.
    if cache_system and body and body[0].get("role") == "system" and \
            not target.lower().startswith("openai/"):
        body = [_cacheable(body[0])] + body[1:]

    payload: Dict[str, Any] = {
        "model": target,
        "messages": body,
        "max_tokens": int(max_tokens),
        "response_format": (
            {
                "type": "json_schema",
                "json_schema": {
                    "name": re.sub(r"[^A-Za-z0-9_-]", "_", response_name or "aulaai_response")[:64],
                    "strict": True,
                    "schema": response_schema,
                },
            }
            if isinstance(response_schema, dict)
            else {"type": "json_object"}
        ),
        # Ask for the real cost and the real cache split. Without this the
        # ledger is an estimate of an invoice we could simply have been told.
        "usage": {"include": True},
    }
    if "gemini" in target.lower() or "google" in target.lower():
        payload["temperature"] = float(temperature)
        payload["provider"] = {"order": ["Google AI Studio", "Google"], "allow_fallbacks": True}
        payload["reasoning"] = {"effort": reasoning_effort or "low"}
    elif target.lower().startswith("openai/gpt-5.6-"):
        # OpenAI reasoning models reject/ignore sampling controls in several
        # provider paths. Luna Pro is already a model alias with pro reasoning
        # pinned by the provider; do not overwrite that mode with an effort
        # parameter. Standard GPT-5.6 routes still accept explicit effort.
        payload["provider"] = {"sort": "throughput"}
        if not target.lower().endswith("-pro"):
            payload["reasoning"] = {"effort": reasoning_effort or "low"}
    else:
        payload["temperature"] = float(temperature)

    if isinstance(response_schema, dict):
        provider = payload.setdefault("provider", {})
        provider["require_parameters"] = True

    seconds = timeout or (180 if max_tokens > 8000 else (120 if max_tokens > 3000 else 60))
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "HTTP-Referer": "https://aulaai.com", "X-Title": "AulaAI"}
    encoded = json.dumps(payload).encode("utf-8")

    last_error = "unknown"
    for attempt in range(max(1, attempts)):
        started = time.perf_counter()
        try:
            request = urllib.request.Request(_ENDPOINT, data=encoded, headers=headers)
            with urllib.request.urlopen(request, timeout=seconds) as raw_response:
                parsed = json.loads(raw_response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:300]
            except Exception:
                pass
            last_error = f"HTTP {exc.code}: {detail}"
            # 4xx other than rate limiting will not improve on a retry.
            if exc.code not in (408, 409, 425, 429) and exc.code < 500:
                return Response(error=last_error, model=target,
                                seconds=time.perf_counter() - started)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            elapsed = time.perf_counter() - started
            usage = _usage_of(parsed)
            choices = parsed.get("choices") or []
            if not choices:
                return Response(error=f"no choices: {str(parsed)[:200]}", model=target,
                                input_tokens=usage["input"], output_tokens=usage["output"],
                                cached_tokens=usage["cached"], cost=usage["cost"],
                                seconds=elapsed)
            choice = choices[0] or {}
            text = _message_text((choice.get("message") or {}).get("content"))
            finish_reason = str(choice.get("finish_reason") or "").lower()
            truncated = finish_reason in ("length", "max_tokens")
            data = extract_json(text)
            parse_error = ""
            if data is None:
                preview = re.sub(r"\s+", " ", text[:180]).strip()
                parse_error = (
                    f"unparseable JSON body (finish_reason={finish_reason or 'unknown'}, "
                    f"chars={len(text)}, preview={preview!r})"
                )
            return Response(
                data=data, raw=text, truncated=truncated,
                error=parse_error,
                input_tokens=usage["input"], output_tokens=usage["output"],
                cached_tokens=usage["cached"], cost=usage["cost"],
                model=target, seconds=elapsed)
        time.sleep(0.6 * (attempt + 1))

    return Response(error=last_error, model=target)
