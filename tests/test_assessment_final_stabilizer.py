import unittest

from services import assessment_guard as guard
from services import assessment_legacy_filter as gate
from services import assessment_final_stabilizer as stabilizer


def _q(prompt, answer, op, target, distractors=None):
    return {
        "prompt": prompt,
        "answer": answer,
        "distractors": distractors or ["x1", "x2", "x3"],
        "why": f"[[AULAOBJ:{op}]] [[AULATGT:{target}]] reason",
        "difficulty": "A1",
    }


class AssessmentFinalStabilizerTests(unittest.TestCase):
    def test_noncentral_topic_caps_meta_and_dedupes_canonical_target(self):
        items = [
            _q("Use uno before a masculine noun", "un", "grammar", "uno apocope masculine", ["uno", "una", "unos"]),
            _q("How does uno change before a masculine noun?", "un", "grammar", "uno apocope masculine singular", ["uno", "una", "unos"]),
            _q("Which form carries the written accent?", "dieciséis", "orthography-form", "accent in sixteen", ["diecisiete", "dieciocho", "diecinueve"]),
            _q("Which other form carries the written accent?", "veintidós", "orthography-form", "accent in twenty two", ["veinticuatro", "veinticinco", "veintisiete"]),
            _q("Which item illustrates a sound contrast?", "cinco", "pronunciation", "soft hard c contrast", ["cero", "ocho", "doce"]),
            _q("Choose the contextual quantity", "dos", "contextual-use", "quantity in cafe order", ["tres", "cuatro", "cinco"]),
        ]
        selected = stabilizer._batch_select(
            guard,
            gate,
            items,
            10,
            (),
            {"topic_title": "Basic numbers", "topic_type": "vocabulary"},
        )

        targets = [stabilizer._objective_parts(q, guard)[1] for q in selected]
        meta_ops = [stabilizer._objective_parts(q, guard)[0] for q in selected]
        self.assertEqual(len([t for t in targets if "uno apocope masculine" in t]), 1)
        self.assertLessEqual(sum(op in stabilizer._META_OPS for op in meta_ops), 2)

    def test_pronunciation_topic_does_not_apply_meta_cap(self):
        items = [
            _q(f"Sound item {i}", f"a{i}", "pronunciation", f"sound target {i}", [f"b{i}", f"c{i}", f"d{i}"])
            for i in range(4)
        ]
        selected = stabilizer._batch_select(
            guard,
            gate,
            items,
            4,
            (),
            {"topic_title": "Pronunciation and sounds", "topic_type": "pronunciation"},
        )
        self.assertEqual(len(selected), 4)


if __name__ == "__main__":
    unittest.main()
