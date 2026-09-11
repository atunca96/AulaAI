from services.bilingual_translation_guard import _is_bad_translation, _looks_obviously_english


def test_exact_source_copy_is_rejected_for_turkish():
    source = "Feminine noun ending in -я. Notice that the stress shifts to the end syllable."
    assert _is_bad_translation(source, source, "tr") is True


def test_obviously_english_turkish_field_is_rejected():
    value = "The standard, affectionate term used in everyday speech. Grammatically feminine."
    assert _looks_obviously_english(value) is True
    assert _is_bad_translation("Some English source", value, "tr") is True


def test_real_turkish_translation_is_accepted():
    source = "The standard, affectionate term used in everyday speech. Grammatically feminine."
    translated = "Günlük konuşmada kullanılan standart ve samimi bir hitap sözcüğüdür. Dilbilgisel olarak dişildir."
    assert _is_bad_translation(source, translated, "tr") is False


def test_target_terms_inside_turkish_do_not_make_it_english():
    source = "The noun 'семья' is feminine and the stress falls on the final syllable."
    translated = "'семья' dişil bir isimdir ve vurgu son heceye düşer."
    assert _is_bad_translation(source, translated, "tr") is False


def test_existing_turkish_source_may_remain_identical():
    source = "Bu ifade günlük konuşmada kullanılır."
    assert _is_bad_translation(source, source, "tr") is False
