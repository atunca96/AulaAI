from types import SimpleNamespace

from services.assessment_direct_single_pass_experiment import install


def _fake_module(items):
    calls = []

    def call_ai(messages, **kwargs):
        calls.append((messages, kwargs))
        return {"data": items}

    counter = {"n": 0}

    def uid():
        counter["n"] += 1
        return f"q{counter['n']}"

    module = SimpleNamespace(
        MODEL_STRUCTURAL="google/gemini-test",
        _call_ai=call_ai,
        _uid=uid,
    )
    install(module)
    return module, calls


def _items():
    data = [
        {
            "prompt": "Bad duplicate normalization 1?",
            "answer": "Ё",
            "distractors": ["Е", "Е!", "Э"],
        },
        {
            "prompt": "Bad duplicate normalization 2?",
            "answer": "33 буквы",
            "distractors": ["33-буквы", "30 букв", "32 буквы"],
        },
    ]
    for i in range(12):
        data.append({
            "prompt": f"Question {i + 1}?",
            "answer": f"Correct {i + 1}",
            "distractors": [f"Wrong {i + 1}A", f"Wrong {i + 1}B", f"Wrong {i + 1}C"],
        })
    return data


def test_direct_writer_uses_ui_language_not_course_language():
    module, calls = _fake_module(_items())

    result = module.ai_generate_questions(
        topic_title="Русский алфавит",
        topic_type="pronunciation",
        topic_content={"pages": []},
        language="Russian",
        count=10,
        level="A1",
        material_language="tr",
    )

    assert len(result) == 10
    assert result[0]["prompt"] == "Question 1?"
    system = calls[0][0][0]["content"]
    user = calls[0][0][1]["content"]
    assert "instructional/UI language is Turkish" in system
    assert "COURSE LANGUAGE: Russian" in user
    assert "INSTRUCTION LANGUAGE: Turkish" in user
    assert "Keep authentic Russian words" in system


def test_direct_writer_defaults_to_english_instruction_language():
    module, calls = _fake_module(_items())

    result = module.ai_generate_questions(
        topic_title="Russian alphabet",
        topic_type="pronunciation",
        topic_content={"pages": []},
        language="Russian",
        count=3,
        level="A1",
        material_language="en",
    )

    assert len(result) == 3
    system = calls[0][0][0]["content"]
    assert "instructional/UI language is English" in system
