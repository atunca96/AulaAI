#!/usr/bin/env python3
"""Regression: a unit assessment that returns 0/10 gets one bounded semantic rescue."""

from __future__ import annotations

import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

from services import ai_engine as AE

calls=[]
orig=AE.ai_generate_questions

def fake_generate(*args, **kwargs):
    calls.append(dict(kwargs))
    # First call simulates Gemini yielding 0 validated items after its retries.
    if len(calls)==1:
        return []
    # Rescue call returns the missing 10 already-valid items.
    prompts = [
        "¿Qué palabra significa pan?",
        "Elige la bebida: agua.",
        "¿Dónde compras fruta normalmente?",
        "Completa: Quiero pagar con ____.",
        "¿Qué dices para pedir un café?",
        "Selecciona el lugar: la farmacia.",
        "¿Cuál opción nombra una verdura?",
        "Completa la compra: Necesito dos ____.",
        "¿Qué frase sirve para preguntar el precio?",
        "Selecciona la comida que aparece en la unidad.",
    ]
    out=[]
    for i, prompt in enumerate(prompts):
        out.append({
            "id":f"q{i}",
            "type":"mcq",
            "prompt":prompt,
            "answer":f"respuesta {i+1}",
            "distractors":[f"d{i+1}a",f"d{i+1}b",f"d{i+1}c"],
            "options":[f"respuesta {i+1}",f"d{i+1}a",f"d{i+1}b",f"d{i+1}c"],
            "why":"Grounded in unit evidence.",
            "why_tr":"Ünite içeriğine dayanır.",
        })
    return out

unit_topics=[{
    "title":"Food and Drink Staples",
    "content":{
        "pages":[{
            "type":"vocabulary",
            "title":"Food",
            "items":[
                {"term":"pan","translation_tr":"ekmek","translation":"bread"},
                {"term":"agua","translation_tr":"su","translation":"water"}
            ]
        }]
    }
}]

try:
    AE.ai_generate_questions=fake_generate
    result=AE.generate_unit_assessment(
        "Shopping, Food, and Public Services",
        unit_topics,
        "Spanish",
        level="A1",
        material_language="tr",
        count=10,
    )
finally:
    AE.ai_generate_questions=orig

assert len(result)==10, f"expected rescued 10/10, got {len(result)}"
assert len(calls)==2, f"expected primary + one rescue call, got {len(calls)}"
assert calls[0].get("model_override") is None
assert calls[1].get("model_override")=="openai/gpt-5.6-luna-pro"
assert calls[1].get("count")==10
assert calls[1].get("allow_partial") is True

print("[UNIT-ASSESS-RESCUE] zero-item assessment rescue regression PASSED")
