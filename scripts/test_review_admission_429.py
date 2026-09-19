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
