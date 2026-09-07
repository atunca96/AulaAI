"""
Enrich Existing Topics Script.
Upgrades all existing topics in data/aula.db with brief pedagogical explanations
for phonetic, grammatical, and linguistic concept items in both English and Turkish.
"""

import os
import sys
import json
import sqlite3

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.concept_explanations import get_concept_explanation

DB_PATH = os.path.join(ROOT_DIR, "data", "aula.db")

def enrich_database():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, content FROM topics WHERE content IS NOT NULL")
    rows = c.fetchall()

    enriched_count = 0
    total_items_enriched = 0

    for tid, ttitle, content_raw in rows:
        try:
            content = json.loads(content_raw)
        except Exception:
            continue

        pages = content.get("pages", [])
        modified = False

        for p in pages:
            items = p.get("items") or p.get("vocabulary") or p.get("words") or []
            if not isinstance(items, list):
                continue

            for it in items:
                if not isinstance(it, dict):
                    continue

                term_val = str(it.get("term") or it.get("word") or "")
                trans_val = str(it.get("translation") or it.get("meaning") or it.get("english") or "")

                c_en = get_concept_explanation(term_val, trans_val, "en")
                c_tr = get_concept_explanation(term_val, trans_val, "tr")

                if c_en:
                    if not it.get("explanation") or len(str(it.get("explanation")).strip()) <= 2:
                        it["explanation"] = c_en
                        it["explanation_en"] = c_en
                        it["explanation_tr"] = c_tr
                        modified = True
                        total_items_enriched += 1
                    else:
                        if not it.get("explanation_en"):
                            it["explanation_en"] = it["explanation"]
                            modified = True
                        if not it.get("explanation_tr"):
                            it["explanation_tr"] = c_tr
                            modified = True

        if modified:
            c.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(content, ensure_ascii=False), tid))
            enriched_count += 1

    conn.commit()
    conn.close()
    print(f"Enrichment Complete: Updated {enriched_count} topics with {total_items_enriched} concept explanations.")

if __name__ == "__main__":
    enrich_database()
