from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import services.material_quality_guard as guard


def run():
    # Existing V56 repairs remain active.
    fixed, unsafe = guard._v56_russian_text("В суббоtu мы отдыхаем.")
    assert "субботу" in fixed.casefold(), fixed
    assert not unsafe, fixed

    fixed, _ = guard._v56_russian_text("Э́то писмо́. В кози́не де́вять я́блок.")
    assert "письмо" in fixed.casefold().replace("́", ""), fixed
    assert "корзине" in fixed.casefold().replace("́", ""), fixed
    assert "Physik" not in guard._v56_turkish_text("O Physik odada bes kisi var.")

    # One learner-facing pronunciation system: English option glosses disappear,
    # one-letter Cyrillic phonetic labels become IPA, and Cyrillic respelling in
    # prose is removed while real IPA/transliteration remains.
    assert guard._v56f_clean_option("[ɐ] (similar to an unstressed 'a')") == "[ɐ]"
    assert guard._v56f_clean_option("[дʲ]") == "[dʲ]"
    fixed, _ = guard._v56_russian_text("клуб [клуп], город [горат]; мат [mat] — мать [matʲ]")
    assert "[клуп]" not in fixed and "[горат]" not in fixed, fixed
    assert "мат [mat]" in fixed and "мать [matʲ]" in fixed, fixed

    # Alphabet inventory normalization is exact and deterministic.
    alphabet = {"pages": [{"type": "vocabulary", "items": [
        {"term": "Ч ч", "phonetic": "[t͡ɕː]"},
        {"term": "Щ щ", "phonetic": "[ɕː]"},
        {"term": "Ъ ъ", "phonetic": "[-]"},
        {"term": "Ь ь", "phonetic": "[-]"},
    ]}]}
    out = guard._v56_release_cleanup(alphabet, "Russian")
    items = out["pages"][0]["items"]
    assert items[0]["phonetic"] == "[t͡ɕ]", items
    assert items[1]["phonetic"] == "[ɕː]", items
    assert items[2]["phonetic"] == "", items
    assert items[3]["phonetic"] == "", items

    # A malformed distractor is not repaired into invented language: the whole MCQ is cropped.
    malformed = {"pages": [{
        "type": "mcq",
        "prompt_tr": "Каждый вечер я ____ ужин дома.",
        "options": ["готовит", "готовлю", "готовишь", "готовю"],
        "answer": "готовлю",
        "explanation_tr": "'готовю' ise araya gelmesi zorunlu 'л' sesini içermediği için yanlıştır.",
    }]}
    assert guard._v56_release_cleanup(malformed, "Russian")["pages"] == []

    malformed_case = {"pages": [{
        "type": "mcq",
        "prompt_tr": "Моя подруга сейчас живёт в...",
        "options": ["Италия", "Италие", "Италию", "Италии"],
        "answer": "Италии",
        "explanation_tr": "'Италие' ise hatalı bir formdur.",
    }]}
    assert guard._v56_release_cleanup(malformed_case, "Russian")["pages"] == []

    # Name -> real-world gender is unsupported. The question is cropped, not rewritten.
    hidden_gender = {"pages": [{
        "type": "mcq",
        "prompt_tr": "Вчера Анна весь вечер ________ новую книгу.",
        "options": ["читало", "читали", "читал", "читала"],
        "answer": "читала",
        "explanation_tr": "Özne tekil dişil olan 'Анна' olduğu için fiil dişil eki olan -ла biçimini almalıdır.",
    }]}
    assert guard._v56_release_cleanup(hidden_gender, "Russian")["pages"] == []

    # Grammatical gender supplied by a noun is legitimate and must survive.
    safe_gender = {"pages": [{
        "type": "mcq",
        "prompt_tr": "Это очень ___ рыба.",
        "options": ["вкусное", "вкусная", "вкусные", "вкусный"],
        "answer": "вкусная",
        "explanation_tr": "'Рыба' ismi yalın hâlde dişil ve tekildir; sıfat isimle uyum sağlar.",
    }]}
    assert len(guard._v56_release_cleanup(safe_gender, "Russian")["pages"]) == 1

    # IPA-option cleanup reaches the actual page structure and its answer value.
    phonetic_mcq = {"pages": [{
        "type": "mcq",
        "prompt_tr": "Doğru sesi seçiniz.",
        "options": ["[o] (clear long 'o')", "[ɐ] (similar to an unstressed 'a')", "[д]", "[т]"],
        "answer": "[ɐ] (similar to an unstressed 'a')",
    }]}
    out = guard._v56_release_cleanup(phonetic_mcq, "Russian")
    assert out["pages"][0]["options"] == ["[o]", "[ɐ]", "[d]", "[t]"], out
    assert out["pages"][0]["answer"] == "[ɐ]", out

    # Deliberate multilingual quotation remains untouched.
    data = {"pages": [{"type": "vocabulary", "term": "как по-русски", "example": "Как по-русски dictionary?"}]}
    out = guard._v56_release_cleanup(data, "Russian")
    assert "dictionary" in out["pages"][0]["example"]

    print("[V56] final one-shot publication regression tests PASSED")


if __name__ == "__main__":
    run()
