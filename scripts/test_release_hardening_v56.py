from sitecustomize import _clean_option, _clean_target, _clean_tree


def run():
    assert _clean_option("Средний род (Neuter)") == "Средний род"
    assert _clean_option("Женский род (Feminine)") == "Женский род"
    assert _clean_option("[ɐ] (an unstressed 'a'-like sound)") == "[ɐ]"
    assert _clean_option("[u] (a close rounded 'u' sound)") == "[u]"
    assert _clean_option("кофе (çekimsiz eril)") == "кофе (çekimsiz eril)"
    assert _clean_option("word (formal)") == "word (formal)"

    assert _clean_target("Чей это [kto]?") == "Чей это?"
    assert _clean_target("мат [mat] / мать [matʲ]") == "мат [mat] / мать [matʲ]"

    page = {
        "type": "mcq",
        "options": ["Мужской род (Masculine)", "Средний род (Neuter)", "обычный"],
        "answer": "Средний род (Neuter)",
    }
    cleaned = _clean_tree(page)
    assert cleaned["options"][0] == "Мужской род"
    assert cleaned["options"][1] == "Средний род"
    assert cleaned["answer"] == "Средний род"

    comparison = {
        "comparisons": [
            {"target": "Чей это [kto]?", "translation_tr": "Bu kimin?"},
            {"target": "мат [mat] / мать [matʲ]", "translation_tr": "karşılaştırma"},
        ]
    }
    cleaned_comparison = _clean_tree(comparison)
    assert cleaned_comparison["comparisons"][0]["target"] == "Чей это?"
    assert cleaned_comparison["comparisons"][1]["target"] == "мат [mat] / мать [matʲ]"

    print("[V56] publication cleanup regression tests PASSED")


if __name__ == "__main__":
    run()
