from types import SimpleNamespace

from services.assessment_direct_single_pass_experiment import install


def test_requested_count_is_sent_directly_without_headroom():
    captured = {}

    def call_ai(messages, **kwargs):
        captured["messages"] = messages
        return {
            "data": [
                {
                    "prompt": f"Question {i}",
                    "answer": f"Answer {i}",
                    "distractors": [f"Wrong {i}A", f"Wrong {i}B", f"Wrong {i}C"],
                }
                for i in range(7)
            ]
        }

    module = SimpleNamespace(
        _call_ai=call_ai,
        _uid=lambda: "qid",
        MODEL_STRUCTURAL="test-model",
    )
    install(module)

    result = module.ai_generate_questions(
        topic_title="Alphabet and pronunciation",
        topic_type="vocabulary",
        topic_content={"pages": [{"text": "lesson material"}]},
        language="Russian",
        count=7,
        level="A1",
        material_language="en",
    )

    prompt = captured["messages"][1]["content"]
    assert "Create a 7-question assessment" in prompt
    assert "Return exactly 7 multiple-choice questions" in prompt
    assert "11" not in prompt
    assert len(result) == 7


def test_prompt_stays_minimal_and_pedagogical():
    captured = {}

    def call_ai(messages, **kwargs):
        captured["messages"] = messages
        return {
            "data": [
                {
                    "prompt": "Which form fits the context?",
                    "answer": "correct",
                    "distractors": ["wrong one", "wrong two", "wrong three"],
                }
            ]
        }

    module = SimpleNamespace(
        _call_ai=call_ai,
        _uid=lambda: "qid",
        MODEL_STRUCTURAL="test-model",
    )
    install(module)

    module.ai_generate_questions(
        topic_title="Greetings",
        topic_content="source lesson",
        language="German",
        count=1,
        level="A1",
        material_language="tr",
    )

    system = captured["messages"][0]["content"]
    user = captured["messages"][1]["content"]
    assert system == "You are an expert language teacher creating a rigorous, fair CEFR-aligned assessment."
    assert "Choose the most important knowledge and skills to assess yourself." in user
    assert "Questions should not be repetitive" in user
    assert "distractors should be plausible" in user
    assert "objective" not in user.lower()
    assert "meta-linguistic" not in user.lower()
    assert "recent prompts" not in user.lower()
