from sitecustomize import _clean_option, _clean_target, _clean_tree, _clean_tr_text


def run():
    assert _clean_option("Средний род (Neuter)") == "Средний род"
    assert _clean_option("[ɐ] (an unstressed 'a'-like sound)") == "[ɐ]"
    assert _clean_option("кофе (çekimsiz eril)") == "кофе (çekimsiz eril)"
    assert _clean_target("Чей это [kto]?") == "Чей это?"
    assert _clean_target("мат [mat] / мать [matʲ]") == "мат [mat] / мать [matʲ]"

    data = {"pages": [{"type": "vocabulary", "items": [{"term": "пальто", "example_tr": "Bu benim palтом."}]}]}
    cleaned = _clean_tree(data, language="Russian")
    assert cleaned["pages"][0]["items"][0]["example_tr"] == "Bu benim paltom."
    assert "Yönelme Hâli" in _clean_tr_text("yönelme hâli (datif / Dativ)")
    assert "Belirtme Hâli" in _clean_tr_text("Belirtme Durumu (Akkuzatif / Akkusativ)")
    assert _clean_tr_text("Yalın Hâl singular; Genitif plural") == "Yalın Hâl tekil; İlgi/Tamlayan Hâli çoğul"
    assert _clean_tr_text("masculine / feminine / neuter") == "eril / dişil / nötr"

    target = {"pages": [{"type": "vocabulary", "items": [
        {"term": "гулять", "example": "В суббоtu мы гуляем в парке.", "example_tr": "Cumartesi parkta gezeriz."},
        {"term": "как по-русски", "example": "Как по-русски dictionary?", "example_tr": "Dictionary Rusça nasıl denir?"},
    ]}]}
    target_clean = _clean_tree(target, language="Russian")
    assert target_clean["pages"][0]["items"][0]["example"] == "В субботу мы гуляем в парке."
    assert "dictionary" in target_clean["pages"][0]["items"][1]["example"]

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

    bad_gender = {"pages": [{
        "type": "mcq", "prompt_tr": "Anna okulda çalışıyor. O zaten ____.",
        "options": ["за́мужем", "жена́т", "холо́ст", "брат"], "answer": "за́мужем",
        "explanation_tr": "Özne dişil ('Она' / 'Анна') olduğu için bu biçim kullanılır."
    }]}
    assert _clean_tree(bad_gender, language="Russian")["pages"] == []

    safe_gender = {"pages": [{
        "type": "mcq", "prompt_tr": "Bu kadın evlidir. Rusçada uygun biçimi seçin.",
        "options": ["за́мужем", "жена́т", "холо́ст", "брат"], "answer": "за́мужем",
        "explanation_tr": "Özne açıkça kadın ve evli olarak verilmiştir."
    }]}
    assert len(_clean_tree(safe_gender, language="Russian")["pages"]) == 1

    bad_job = {"pages": [{
        "type": "mcq", "prompt_tr": "Oleg okulda çalışıyor. Mesleği nedir?",
        "options": ["учитель", "врач", "инженер", "студент"], "answer": "учитель",
        "explanation_tr": "Okulda çalıştığı için öğretmendir."
    }]}
    assert _clean_tree(bad_job, language="Russian")["pages"] == []

    bad_trait = {"pages": [{
        "type": "mcq", "prompt_tr": "İvan çok dakiktir. İşe ____ geç kalır.",
        "options": ["никогда", "иногда", "часто", "редко"], "answer": "никогда"
    }]}
    assert _clean_tree(bad_trait, language="Russian")["pages"] == []

    bad_distractor = {"pages": [{
        "type": "mcq", "prompt_tr": "«друг» sözcüğünün çoğulunu seçin.",
        "options": ["друга", "другы", "други", "друзья"], "answer": "друзья"
    }]}
    assert _clean_tree(bad_distractor, language="Russian")["pages"] == []

    print("[V57] final release-policy regression tests PASSED")


if __name__ == "__main__":
    run()
