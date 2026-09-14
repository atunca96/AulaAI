from services.material_quality_guard import _v56_release_cleanup, _v56_russian_text, _v56_turkish_text


def run():
    # Mixed-script repair.
    fixed, unsafe = _v56_russian_text("Этот журнал интересный, а этоt старый.")
    assert "этот" in fixed.casefold(), fixed
    assert not unsafe, fixed

    fixed, unsafe = _v56_russian_text("В суббоtu мы отдыхаем.")
    assert "субботу" in fixed.casefold(), fixed
    assert not unsafe, fixed

    # Exact production typos.
    fixed, _ = _v56_russian_text("Э́то писмо́. В кози́не де́вять я́блок.")
    assert "письмо́" in fixed, fixed
    assert "корзине" in fixed.casefold().replace("́", ""), fixed

    # Turkish publication cleanup.
    assert _v56_turkish_text("İlgi/İlgi/Tamlayan Hâli") == "İlgi/Tamlayan Hâli"
    assert _v56_turkish_text("O Physik odada beş kişi var.") == "O odada beş kişi var."

    # Fabricated distractor => prune whole MCQ, safe MCQ remains.
    bad = {"pages": [{
        "type": "mcq",
        "prompt": "книга çoğulu?",
        "options": ["книга", "книгы", "книги", "книге"],
        "answer": "книги",
    }]}
    assert _v56_release_cleanup(bad, "Russian")["pages"] == []

    safe = {"pages": [{
        "type": "mcq",
        "prompt": "Doğru biçimi seçin",
        "options": ["книга", "книге", "книги", "книгу"],
        "answer": "книги",
    }]}
    assert len(_v56_release_cleanup(safe, "Russian")["pages"]) == 1

    # Deliberate pure-Latin quotation remains untouched; only intra-token mixing is repaired.
    data = {"pages": [{"type": "vocabulary", "term": "как по-русски", "example": "Как по-русски dictionary?"}]}
    out = _v56_release_cleanup(data, "Russian")
    assert "dictionary" in out["pages"][0]["example"]

    print("[V56] final deterministic publication cleanup tests PASSED")


if __name__ == "__main__":
    run()
