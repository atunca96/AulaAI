from services.material_display_stabilizer import (
    _FORBIDDEN_ENGLISH_ANCHORS,
    _is_letter_like,
    _looks_english,
    _looks_turkish,
    _split_option,
)


def test_russian_letter_cards_are_detected():
    assert _is_letter_like("Л л") is True
    assert _is_letter_like("Х х") is True
    assert _is_letter_like("Щ щ") is True
    assert _is_letter_like("молоко") is False


def test_unrelated_language_anchors_are_forbidden_in_english_pronunciation():
    bad = "Pronounced like 'ch' in Scottish 'loch' or German 'Bach'."
    assert _FORBIDDEN_ENGLISH_ANCHORS.search(bad)
    assert _FORBIDDEN_ENGLISH_ANCHORS.search("It sounds like the Turkish 's'.")


def test_mixed_target_form_plus_english_is_still_english_ui_prose():
    text = "What does «дома» mean when the stress is on the first syllable?"
    assert _looks_english(text) is True


def test_turkish_ui_prose_is_detected():
    assert _looks_turkish("Vurgu ilk hecedeyken bu kelime ne anlama gelir?") is True


def test_ipa_prefix_is_separated_from_explanatory_gloss():
    prefix, note = _split_option("[mɐlɐkó] (first two o's reduce, final o is stressed)")
    assert prefix == "[mɐlɐkó]"
    assert note.startswith("first two")
