#!/usr/bin/env python3
"""Regression: transient zero-cost OpenRouter admission 429s retry in-place."""

from __future__ import annotations
import os, sys
from types import SimpleNamespace

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

calls=[]
sleeps=[]
orig_call=Q.T.call_model
orig_sleep=Q.time.sleep

def fake_call(*args, **kwargs):
    calls.append(kwargs)
    if len(calls) < 3:
        return SimpleNamespace(
            ok=False,
            seconds=0.0,
            cost=0.0,
            error='HTTP 429: {"metadata":{"limit_source":"openrouter_admission_control"}}',
            data=None,
            input_tokens=0,
            output_tokens=0,
        )
    return SimpleNamespace(
        ok=True,
        seconds=0.2,
        cost=0.001,
        error=None,
        data={"value":"ok"},
        input_tokens=10,
        output_tokens=5,
    )

try:
    Q.T.call_model=fake_call
    Q.time.sleep=lambda seconds: sleeps.append(seconds)
    budget=Q.ReviewBudget(1.0)
    data=Q._call_review(
        model="google/gemini-3.7-flash",
        system="system",
        payload={"x":"y"},
        max_tokens=50,
        effort="low",
        budget=budget,
        stage="review_test",
        response_schema={
            "type":"object",
            "properties":{"value":{"type":"string"}},
            "required":["value"],
            "additionalProperties":False,
        },
        response_name="review_test",
    )
finally:
    Q.T.call_model=orig_call
    Q.time.sleep=orig_sleep

assert data == {"value":"ok"}, data
assert len(calls) == 3, len(calls)
assert sleeps == [2.0, 4.0], sleeps
assert abs(budget.spent - 0.001) < 1e-9, budget.spent
print("[ADMISSION-429] zero-cost transient admission failures retry without double-spend")


# The provider can also return a syntactically partial structured body with
# finish_reason=error and $0 cost. That is the exact production failure class
# seen on review_lesson and must retry without relaxing the schema.
json_calls=[]
orig_call=Q.T.call_model

def fake_json_call(*args, **kwargs):
    json_calls.append(kwargs)
    if len(json_calls) == 1:
        return SimpleNamespace(
            ok=False,
            seconds=0.1,
            cost=0.0,
            error=(
                'unparseable JSON body (finish_reason=error, chars=271, '
                'preview=\'{"topics":[{"topic_id":"x"\')'
            ),
            data=None,
            input_tokens=0,
            output_tokens=0,
            truncated=False,
        )
    return SimpleNamespace(
        ok=True,
        seconds=0.2,
        cost=0.001,
        error=None,
        data={"value":"ok"},
        input_tokens=10,
        output_tokens=5,
        truncated=False,
    )

try:
    Q.T.call_model=fake_json_call
    budget=Q.ReviewBudget(1.0)
    data=Q._call_review(
        model="google/gemini-3.7-flash",
        system="system",
        payload={"x":"y"},
        max_tokens=50,
        effort="low",
        budget=budget,
        stage="review_json_transport",
        response_schema={
            "type":"object",
            "properties":{"value":{"type":"string"}},
            "required":["value"],
            "additionalProperties":False,
        },
        response_name="review_json_transport",
    )
finally:
    Q.T.call_model=orig_call

assert data == {"value":"ok"}, data
assert len(json_calls) == 2, len(json_calls)
assert abs(budget.spent - 0.001) < 1e-9, budget.spent
print("[STRUCTURED-JSON] zero-cost finish_reason=error retries strict schema unchanged")


# Transport-level regression: HTTP 200 + partial JSON + finish_reason=error
# must consume the existing bounded transport retry and aggregate usage/cost.
import json as _json

class _FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return _json.dumps(self.payload).encode("utf-8")

transport_calls=[]
orig_urlopen=Q.T.urllib.request.urlopen
orig_key=Q.T.os.environ.get("OPENROUTER_API_KEY")
Q.T.os.environ["OPENROUTER_API_KEY"]="test-key-long-enough"

def fake_urlopen(request, timeout=None):
    transport_calls.append(1)
    if len(transport_calls) == 1:
        return _FakeHTTP({
            "choices":[{
                "message":{"content":"{\"value\":\"partial"},
                "finish_reason":"error",
            }],
            "usage":{
                "prompt_tokens":10,
                "completion_tokens":4,
                "cost":0.001,
            },
        })
    return _FakeHTTP({
        "choices":[{
            "message":{"content":"{\"value\":\"ok\"}"},
            "finish_reason":"stop",
        }],
        "usage":{
            "prompt_tokens":10,
            "completion_tokens":5,
            "cost":0.002,
        },
    })

try:
    Q.T.urllib.request.urlopen=fake_urlopen
    response=Q.T.call_model(
        [{"role":"system","content":"system"},{"role":"user","content":"user"}],
        max_tokens=50,
        temperature=0.0,
        model="google/gemini-3.7-flash",
        cache_system=False,
        attempts=2,
        reasoning_effort="low",
        response_schema={
            "type":"object",
            "properties":{"value":{"type":"string"}},
            "required":["value"],
            "additionalProperties":False,
        },
        response_name="transport_retry",
    )
finally:
    Q.T.urllib.request.urlopen=orig_urlopen
    if orig_key is None:
        Q.T.os.environ.pop("OPENROUTER_API_KEY",None)
    else:
        Q.T.os.environ["OPENROUTER_API_KEY"]=orig_key

assert response.ok, response.error
assert response.data == {"value":"ok"}, response.data
assert len(transport_calls) == 2, len(transport_calls)
assert response.input_tokens == 20, response.input_tokens
assert response.output_tokens == 9, response.output_tokens
assert abs(float(response.cost or 0.0) - 0.003) < 1e-9, response.cost
print("[TRANSPORT-STRUCTURED] finish_reason=error retries and aggregates billed usage")
