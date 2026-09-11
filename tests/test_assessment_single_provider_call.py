from types import SimpleNamespace

from services.assessment_single_provider_call import install


def test_legacy_top_up_cannot_make_second_provider_call():
    provider_calls = []

    def provider_generate(*args, **kwargs):
        provider_calls.append(kwargs.get("count"))
        return [{"prompt": "q", "answer": "a", "distractors": ["b", "c", "d"]}]

    ai_engine = SimpleNamespace(ai_generate_questions=provider_generate)

    def legacy_assessment(*args, **kwargs):
        first = ai_engine.ai_generate_questions(count=10)
        second = ai_engine.ai_generate_questions(count=9)
        return first + second

    content_engine = SimpleNamespace(generate_assessment_set=legacy_assessment)
    install(content_engine, ai_engine)

    result = content_engine.generate_assessment_set(topic_ids=["t1"], count=10)

    assert provider_calls == [10]
    assert len(result) == 1


def test_generator_is_unrestricted_outside_assessment_scope():
    provider_calls = []

    def provider_generate(*args, **kwargs):
        provider_calls.append(kwargs.get("count"))
        return ["ok"]

    ai_engine = SimpleNamespace(ai_generate_questions=provider_generate)
    content_engine = SimpleNamespace(generate_assessment_set=lambda *args, **kwargs: [])
    install(content_engine, ai_engine)

    assert ai_engine.ai_generate_questions(count=3) == ["ok"]
    assert ai_engine.ai_generate_questions(count=4) == ["ok"]
    assert provider_calls == [3, 4]
