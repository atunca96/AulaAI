from services.curriculum_direct_generator import curriculum_is_complete, normalize_curriculum


def _complete_curriculum():
    chapters = []
    for chapter_index in range(6):
        chapters.append({
            "number": chapter_index + 1,
            "title": f"Unit {chapter_index + 1}: English Title",
            "title_tr": f"Ünite {chapter_index + 1}: Türkçe Başlık",
            "topics": [
                {
                    "title": f"Topic {topic_index + 1}",
                    "title_tr": f"Konu {topic_index + 1}",
                    "type": "grammar" if topic_index == 0 else "vocabulary",
                }
                for topic_index in range(5)
            ],
        })
    return chapters


def test_exact_six_by_five_is_required():
    chapters = normalize_curriculum(_complete_curriculum())
    assert curriculum_is_complete(chapters) is True

    assert curriculum_is_complete(chapters[:1]) is False
    assert curriculum_is_complete(chapters[:4]) is False
    assert curriculum_is_complete(chapters[:5]) is False


def test_each_chapter_requires_five_topics():
    chapters = normalize_curriculum(_complete_curriculum())
    chapters[2]["topics"] = chapters[2]["topics"][:4]
    assert curriculum_is_complete(chapters) is False


def test_missing_bilingual_title_is_rejected():
    chapters = normalize_curriculum(_complete_curriculum())
    chapters[0]["topics"][0]["title_tr"] = ""
    assert curriculum_is_complete(chapters) is False


def test_type_aliases_are_normalized_before_validation():
    chapters = _complete_curriculum()
    chapters[0]["topics"][0]["type"] = "grammatical"
    normalized = normalize_curriculum(chapters)
    assert normalized[0]["topics"][0]["type"] == "grammar"
    assert curriculum_is_complete(normalized) is True


def test_unit_prefixes_are_removed_without_touching_titles():
    normalized = normalize_curriculum(_complete_curriculum())
    assert normalized[0]["title"] == "English Title"
    assert normalized[0]["title_tr"] == "Türkçe Başlık"
