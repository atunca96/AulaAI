from services.lesson_integrity import has_lesson_pages


def test_empty_payload_is_not_complete():
    assert has_lesson_pages({}) is False
    assert has_lesson_pages({"pages": []}) is False
    assert has_lesson_pages('{"pages": []}') is False


def test_metadata_only_page_is_not_complete():
    assert has_lesson_pages({"pages": [{"type": "overview", "title": "Overview", "title_tr": "Genel Bakış"}]}) is False


def test_real_content_page_is_complete():
    assert has_lesson_pages({"pages": [{"type": "overview", "title": "Overview", "text": "Useful lesson content"}]}) is True
    assert has_lesson_pages({"pages": [{"type": "vocabulary", "items": [{"term": "bonjour"}]}]}) is True
    assert has_lesson_pages({"pages": [{"type": "examples", "dialogue": [{"speaker": "A", "text": "Bonjour !"}]}]}) is True


def test_invalid_json_is_not_complete():
    assert has_lesson_pages("not-json") is False
