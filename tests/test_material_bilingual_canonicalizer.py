from services.material_bilingual_canonicalizer import (
    _call_native_explanation_pairs,
    _letter_like,
    _localize_options,
    _scrub_cross_language_reference,
    _split_preserved_option,
)


class _FakeAiEngine:
    MODEL_TRANSLATOR = "fake"

    @staticmethod
    def _call_ai(*args, **kwargs):
        return {
            "0": {
                "en": "The letter Ё normally represents /jo/ and is always stressed when written explicitly.",
                "tr": "MODEL BUNU YENİDEN YAZMAYA ÇALIŞTI.",
                "existing_tr_accurate": True,
            }
        }


def test_cross_language_reference_is_removed_from_english():
    value = "It is written like Latin C, but it is always pronounced like the Turkish 's'."
    cleaned = _scrub_cross_language_reference(value)
    assert "Turkish" not in cleaned
    assert "'s' sound" in cleaned


def test_russian_alphabet_cards_are_letter_like():
    assert _letter_like("А а") is True
    assert _letter_like("Б б") is True
    assert _letter_like("Ё ё") is True
    assert _letter_like("семья") is False


def test_accurate_existing_turkish_explanation_is_preserved_verbatim():
    existing_tr = "Ё harfi genellikle 'yo' diye okunur; bulunduğu hece her zaman vurguludur."
    entries = [
        (
            "token",
            "alphabet",
            "Ё ё",
            "It is pronounced like the Turkish 'yo' sound.",
            existing_tr,
            "ёлка",
        )
    ]
    result = _call_native_explanation_pairs(_FakeAiEngine(), entries, "Russian")
    assert result["token"]["tr"] == existing_tr
    assert "Turkish" not in result["token"]["en"]


def test_ipa_prefix_is_preserved_while_note_is_localized():
    raw = "[mɐlɐkó] (first two 'o's reduce, final 'o' is stressed)"
    prefix, note = _split_preserved_option(raw)
    assert prefix == "[mɐlɐkó]"
    assert note.startswith("first two")

    en, tr = _localize_options(
        [raw],
        {note: "ilk iki 'o' daralır, son 'o' vurguludur"},
        {},
    )
    assert en == [raw]
    assert tr == ["[mɐlɐkó] (ilk iki 'o' daralır, son 'o' vurguludur)"]


def test_plain_english_meaning_option_gets_turkish_pair():
    raw = "At home (or of the house)"
    en, tr = _localize_options([raw], {raw: "Evde (veya evin)"}, {})
    assert en == [raw]
    assert tr == ["Evde (veya evin)"]


def test_pure_target_form_is_not_translated():
    raw = "дома"
    en, tr = _localize_options([raw], {}, {})
    assert en == [raw]
    assert tr == [raw]
