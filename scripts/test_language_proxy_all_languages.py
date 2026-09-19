#!/usr/bin/env python3
"""Regression: lexical EN/TR language-ID can never be a publication gate.

The detector is intentionally cheap and only distinguishes the two
instructional tracks. In a 15-language product its result is advisory evidence,
not proof that target-language prose is wrong. This test forces the proxy to
misclassify valid target prose in every non-EN/TR taught language and proves:
  * the finding is preserved for semantic review,
  * its severity is WARN, never BLOCK,
  * closed writing-system invariants remain independent and blocking.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402


TARGETS = {
    "Spanish": "Hola amigos buenos días",
    "German": "Guten Tag meine Freunde",
    "French": "Bonjour mes amis aujourd’hui",
    "Italian": "Buongiorno amici come state",
    "Portuguese": "Bom dia meus amigos",
    "Russian": "Привет мои хорошие друзья",
    "Chinese": "你好 我的 朋友 今天",
    "Japanese": "こんにちは 私 の 友達",
    "Arabic": "مرحبا يا أصدقائي اليوم",
    "Dutch": "Goedemorgen mijn beste vrienden",
    "Swedish": "God morgon mina vänner",
    "Korean": "안녕하세요 나의 좋은 친구들",
    "Greek": "Γεια σας καλοί φίλοι",
}

assert len(TARGETS) == 13

orig_detector = A.instructional_language_of
target_values = set(TARGETS.values())


def forced_detector(text: str):
    if str(text) in target_values:
        # Simulate the exact class of false positive seen in production:
        # a valid taught-language target string happens to cross the cheap
        # Turkish/English function-word threshold.
        return "tr"
    return orig_detector(text)


try:
    A.instructional_language_of = forced_detector

    for language, target in TARGETS.items():
        lesson = {
            "pages": [{
                "type": "dialogue",
                "title": "Dialogue",
                "title_tr": "Diyalog",
                "dialogue": [{
                    "speaker": "A",
                    "text": target,
                    "line_en": "A valid target-language utterance.",
                    "line_tr": "Geçerli bir hedef dil ifadesi.",
                }],
            }]
        }

        findings = A.audit_lesson(lesson, language=language, track="tr")
        proxies = [
            f for f in findings
            if f.code == "instructional_prose_in_target_field"
            and f.value == target
        ]
        assert proxies, (language, findings)
        assert all(f.severity == A.WARN for f in proxies), (language, proxies)
        assert not any(
            f.code == "instructional_prose_in_target_field" and f.value == target
            for f in A.blocking(findings)
        ), (language, A.blocking(findings))

        semantic = Q._semantic_proxy_findings_payload(findings)
        assert any(
            row.get("code") == "instructional_prose_in_target_field"
            and row.get("value") == target[:120]
            for row in semantic
        ), (language, semantic)

finally:
    A.instructional_language_of = orig_detector


# English and Turkish are the instructional languages themselves, so target
# language-ID proxy routing is deliberately not applied to them.
for language, target in (
    ("English", "This is ordinary English target prose."),
    ("Turkish", "Bu sıradan bir Türkçe hedef dil cümlesidir."),
):
    lesson = {
        "pages": [{
            "type": "dialogue",
            "dialogue": [{"speaker": "A", "text": target}],
        }]
    }
    findings = A.audit_lesson(lesson, language=language, track="tr")
    assert not any(
        f.code == "instructional_prose_in_target_field"
        for f in findings
    ), (language, findings)


# Separate invariant: a genuinely alien non-Latin script is still a closed,
# deterministic fact and remains BLOCK. Demoting lexical identity must never
# weaken script integrity.
russian = {
    "pages": [{
        "type": "dialogue",
        "dialogue": [{
            "speaker": "A",
            "text": "Привет κόσμος",
        }],
    }]
}
ru_blocks = A.blocking(A.audit_lesson(russian, language="Russian", track="tr"))
assert any(
    f.code in {"mixed_script_token", "alien_script_token"}
    for f in ru_blocks
), ru_blocks

assert "semantic_proxy_findings" in Q._LESSON_REVIEW_SYSTEM
assert "semantic_proxy_findings" in Q._ASSESSMENT_REVIEW_SYSTEM
assert "ADVISORY" in Q._LESSON_REVIEW_SYSTEM
assert "ADVISORY" in Q._ASSESSMENT_REVIEW_SYSTEM

print(
    "[LANGUAGE-PROXY-MATRIX] 15/15 languages: lexical proxy is advisory; "
    "semantic reviewer receives it; closed script invariants remain blocking"
)
