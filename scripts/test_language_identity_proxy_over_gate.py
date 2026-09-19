#!/usr/bin/env python3
"""Regression: EN/TR language-ID heuristics are routing signals, never gates.

The production failure was valid Spanish dialogue:
  Mi madre es de Madrid o de Sevilla.
The cheap function-word detector calls this Turkish because mi/de/o overlap
Turkish function words. In a 15-language product that suspicion must reach the
semantic reviewer, but it may not become a fail-closed publication fact.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402


spanish = "Mi madre es de Madrid o de Sevilla."
assert A.instructional_language_of(spanish) == "tr", (
    "fixture must exercise the real lexical collision"
)

lesson = {
    "pages": [{
        "type": "dialogue",
        "title": "Family conversation",
        "title_tr": "Aile konuşması",
        "dialogue": [{
            "speaker": "A",
            "text": spanish,
            "line_en": "My mother is from Madrid or Seville.",
            "line_tr": "Annem Madrid veya Sevilla kökenli.",
        }],
    }]
}

findings = A.audit_lesson(lesson, language="Spanish", track="tr")
proxy = [
    f for f in findings
    if f.code == "instructional_prose_in_target_field"
]
assert proxy, findings
assert all(f.severity == A.WARN for f in proxy), proxy
assert not any(
    f.code == "instructional_prose_in_target_field"
    for f in A.blocking(findings)
), A.blocking(findings)

payload = Q._semantic_proxy_findings_payload(findings)
assert any(row["code"] == "instructional_prose_in_target_field" for row in payload)
assert "semantic_proxy_findings" in Q._LESSON_REVIEW_SYSTEM
assert "ADVISORY" in Q._LESSON_REVIEW_SYSTEM

# A real Turkish leak in a Latin-script target field is also a semantic
# suspicion, not deterministic proof; the reviewer must receive it.
turkish_leak = {
    "pages": [{
        "type": "dialogue",
        "title": "Dialogue",
        "title_tr": "Diyalog",
        "dialogue": [{
            "speaker": "A",
            "text": "Bu cümle tamamen Türkçe ve burada kalmamalı.",
            "line_en": "This sentence is in Turkish.",
            "line_tr": "Bu cümle Türkçedir.",
        }],
    }]
}
leak_findings = A.audit_lesson(turkish_leak, language="Spanish", track="tr")
leak_proxy = [
    f for f in leak_findings
    if f.code == "instructional_prose_in_target_field"
]
assert leak_proxy and all(f.severity == A.WARN for f in leak_proxy)
assert Q._semantic_proxy_findings_payload(leak_findings), leak_findings

# Demoting lexical language-ID does NOT demote closed writing-system facts.
# Latin Turkish prose inside a Russian target field is still deterministically
# rejected by the script validator.
russian = {
    "pages": [{
        "type": "dialogue",
        "title": "Dialogue",
        "title_tr": "Diyalog",
        "dialogue": [{
            "speaker": "A",
            "text": "Bu cümle Türkçe yazılmıştır ve Rusça değildir.",
            "line_en": "This is not Russian.",
            "line_tr": "Bu Rusça değildir.",
        }],
    }]
}
ru_findings = A.audit_lesson(russian, language="Russian", track="tr")
ru_blocks = A.blocking(ru_findings)
assert any(
    f.code in {"mixed_script_token", "alien_script_token"}
    for f in ru_blocks
), ru_blocks

print(
    "[LANGUAGE-PROXY] lexical EN/TR collisions are advisory across target "
    "languages; semantic review sees them; closed script invariants still block"
)
