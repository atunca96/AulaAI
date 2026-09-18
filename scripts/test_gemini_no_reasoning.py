#!/usr/bin/env python3
"""Gemini repair calls must use the smallest mandatory reasoning mode."""

from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-gemini-noreason-"))

from services.authoring import transport as T

captured = {}
requests = []
original = T.urllib.request.urlopen

class FakeHTTP:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 0},
                "cost": 0.0001,
            },
        }).encode("utf-8")

def fake_urlopen(request, timeout=None):
    payload = json.loads(request.data.decode("utf-8"))
    captured["payload"] = payload
    requests.append(payload)
    return FakeHTTP()

schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}

try:
    T.urllib.request.urlopen = fake_urlopen
    response37 = T.call_model(
        [{"role": "user", "content": "repair exact path"}],
        max_tokens=2000,
        model="google/gemini-3.7-flash",
        reasoning_effort="none",
        response_schema=schema,
        response_name="gemini37_no_reasoning",
        attempts=1,
    )
    response38 = T.call_model(
        [{"role": "user", "content": "repair exact path"}],
        max_tokens=3200,
        model="google/gemini-3.8-flash",
        reasoning_effort="none",
        response_schema=schema,
        response_name="gemini38_min_reasoning",
        attempts=1,
    )
finally:
    T.urllib.request.urlopen = original

assert response37.ok and response37.data == {"ok": True}
assert response38.ok and response38.data == {"ok": True}
assert requests[0].get("reasoning") == {"effort": "low"}, requests[0].get("reasoning")
assert requests[1].get("reasoning") == {"effort": "low"}, requests[1].get("reasoning")
assert requests[1]["max_tokens"] == 3200
assert requests[1]["response_format"]["type"] == "json_schema"
print("[GEMINI-REASONING] mandatory Gemini reasoning maps historical none to low")
