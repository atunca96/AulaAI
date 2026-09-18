#!/usr/bin/env python3
"""Gemini targeted repairs must not spend their output budget on hidden reasoning."""

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
    captured["payload"] = json.loads(request.data.decode("utf-8"))
    return FakeHTTP()

schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}

try:
    T.urllib.request.urlopen = fake_urlopen
    response = T.call_model(
        [{"role": "user", "content": "repair exact path"}],
        max_tokens=2000,
        model="google/gemini-3.7-flash",
        reasoning_effort="none",
        response_schema=schema,
        response_name="gemini_no_reasoning",
        attempts=1,
    )
finally:
    T.urllib.request.urlopen = original

assert response.ok and response.data == {"ok": True}
payload = captured["payload"]
assert payload.get("reasoning") == {"max_tokens": 0}, payload.get("reasoning")
assert payload["max_tokens"] == 2000
assert payload["response_format"]["type"] == "json_schema"
print("[GEMINI-NO-REASONING] targeted repair leaves completion budget for JSON")
