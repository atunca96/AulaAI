from sitecustomize import _clean_option, _clean_target, _clean_tree


def run():
    # Existing V56 cleanup remains intact.
    assert _clean_option("Средний род (Neuter)") == "Средний род"
    assert _clean_option("[ɐ] (an unstressed 'a'-like sound)") == "[ɐ]"
    assert _clean_target("Чей это [kto]?") == "Чей это?"
    assert _clean_target("мат [mat] / мать [matʲ]") == "мат [mat] / мать [matʲ]"

    # Mixed-script corruption in Turkish learner-facing text is repaired only
    # when Latin and Cyrillic were accidentally combined inside one token.
    data = {"pages": [{"type": "vocabulary", "items": [{"term": "пальто", "example_tr": "Bu benim palтом."}]}]}
    cleaned = _clean_tree(data, language="Russian")
    assert cleaned["pages"][0]["items"][0]["example_tr"] == "Bu benim paltom."

    # Repeated Russian alphabet defects are normalized deterministically.
    alphabet = {"pages": [{"type": "vocabulary", "items": [
        {"term": "Ч ч", "phonetic": "[t͡ɕː]"},
        {"term": "Щ щ", "phonetic": "[ɕː]"},
        {"term": "Ъ ъ", "phonetic": "[-]"},
        {"term": "Ь ь", "phonetic": "[-]"},
    ]}]}
    fixed = _clean_tree(alphabet, language="Russian")
    items = fixed["pages"][0]["items"]
    assert items[0]["phonetic"] == "[t͡ɕ]"
    assert items[1]["phonetic"] == "[ɕː]"
    assert items[2]["phonetic"] == ""
    assert items[3]["phonetic"] == ""

    # Name -> gender -> marital-status inference is removed, not rewritten.
    bad_gender = {
        "pages": [{
            "type": "mcq",
            "prompt_tr": "Anna okulda çalışıyor. O zaten ____.",
            "options": ["за́мужем", "жена́т", "холо́ст", "брат"],
            "answer": "за́мужем",
            "explanation_tr": "Özne dişil ('Она' / 'Анна') olduğu için bu biçim kullanılır.",
        }]
    }
    assert _clean_tree(bad_gender, language="Russian")["pages"] == []

    # Explicitly stated gender keeps a legitimate grammar question.
    safe_gender = {
        "pages": [{
            "type": "mcq",
            "prompt_tr": "Özne açıkça kadın olarak verilmiştir. Doğru biçimi seçin.",
            "options": ["за́мужем", "жена́т", "холо́ст", "брат"],
            "answer": "за́мужем",
            "explanation_tr": "Özne dişil olduğu için bu biçim kullanılır.",
        }]
    }
    assert len(_clean_tree(safe_gender, language="Russian")["pages"]) == 1

    # A fabricated Russian spelling distractor causes omission of the whole MCQ.
    bad_distractor = {
        "pages": [{
            "type": "mcq",
            "prompt_tr": "«друг» sözcüğünün çoğulunu seçin.",
            "options": ["друга", "другы", "други", "друзья"],
            "answer": "друзья",
        }]
    }
    assert _clean_tree(bad_distractor, language="Russian")["pages"] == []

    print("[V57] final release-policy regression tests PASSED")


if __name__ == "__main__":
    run()
