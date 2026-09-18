"""The course plan: what is taught, in what order, before any lesson is written.

A course is not a bag of topics. Every rule this package enforces about a single
lesson — teach before you use, stay under the CEFR ceiling, do not smuggle in an
untaught mechanism — is only checkable if something knows what has already been
taught. That knowledge is the course plan, and it has to exist before the first
lesson is generated rather than being reconstructed afterwards.

The plan is also where the cost ceiling is decided. A build's price is very
nearly a linear function of how many lessons it contains, so the honest moment
to say "this classroom costs more than sixty cents" is here, before anything has
been paid for, not at lesson eleven of fourteen.

One model call produces the plan; everything after that is deterministic. The
shape it must satisfy is checked rather than trusted, and a plan that cannot be
repaired into shape falls back to a skeleton that is correct if unambitious —
because a course that builds is worth more than a course that was going to be
excellent and failed.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from services.authoring import budget as B
from services.authoring import prompts as P
from services.authoring import schema as S
from services.authoring import transport as T

__all__ = ["plan_course", "CoursePlan", "Unit", "Topic", "validate_plan", "skeleton_plan"]


TOPIC_TYPES = ("phonetics", "vocabulary", "grammar", "dialogue", "reading", "review")


# Unit and topic titles are the one part of a course that is genuinely
# BILINGUAL rather than single-track. Lesson bodies are read in one language and
# generating the other is waste; these appear in the lecturer's curriculum
# editor with an English and a Turkish column side by side, so both are real
# content and both must exist.
#
# They are also cheap — a title is a handful of tokens — which makes generating
# the pair far cheaper than producing one and translating it. Doing the latter
# cost a batch translation pass on every build, and when it did not land the
# editor showed Turkish text under ENGLISH UNIT NAME and an empty box under
# TÜRKÇE ÜNİTE ADI.

class Topic:
    __slots__ = ("id", "title", "title_tr", "type", "teaches")

    def __init__(self, title: str, type_: str = "vocabulary", teaches: Sequence[str] = (),
                 title_tr: str = ""):
        self.id = str(uuid.uuid4())
        self.title = title
        self.title_tr = title_tr or title
        self.type = type_ if type_ in TOPIC_TYPES else "vocabulary"
        self.teaches: List[str] = list(teaches)

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "title": self.title, "title_tr": self.title_tr,
                "type": self.type, "teaches": list(self.teaches)}


class Unit:
    __slots__ = ("title", "title_tr", "goal", "topics")

    def __init__(self, title: str, goal: str = "", topics: Optional[List[Topic]] = None,
                 title_tr: str = ""):
        self.title = title
        self.title_tr = title_tr or title
        self.goal = goal
        self.topics: List[Topic] = topics or []

    def as_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "title_tr": self.title_tr, "goal": self.goal,
                "topics": [t.as_dict() for t in self.topics]}


class CoursePlan:
    __slots__ = ("language", "level", "track", "units", "notes")

    def __init__(self, language: str, level: str, track: str = "tr",
                 units: Optional[List[Unit]] = None, notes: str = ""):
        self.language = language
        self.level = level
        self.track = track
        self.units: List[Unit] = units or []
        self.notes = notes

    @property
    def topics(self) -> List[Topic]:
        return [t for unit in self.units for t in unit.topics]

    @property
    def lesson_count(self) -> int:
        return len(self.topics)

    def taught_before(self, topic: Topic) -> List[str]:
        """Everything taught by the topics that precede `topic`, in order.

        This is what lets a lesson be told what it may assume, and what makes
        `teach before you use` a checkable instruction instead of a hope.
        """
        out: List[str] = []
        for candidate in self.topics:
            if candidate.id == topic.id:
                break
            out.extend(candidate.teaches or [candidate.title])
        return out

    def as_dict(self) -> Dict[str, Any]:
        return {"language": self.language, "level": self.level, "track": self.track,
                "units": [u.as_dict() for u in self.units], "notes": self.notes}


# ── Shape rules ──────────────────────────────────────────────────────────────
# Sizes chosen so a full course lands inside the cost ceiling with headroom.
# `project_classroom_cost` puts 40 lessons at ~$0.56 of the $0.60 allowance, so
# the hard cap sits below that rather than at it.

MIN_UNITS, MAX_UNITS = 3, 10
MIN_TOPICS_PER_UNIT, MAX_TOPICS_PER_UNIT = 2, 6
MAX_LESSONS = 36


def validate_plan(plan: CoursePlan) -> List[str]:
    """What is wrong with this plan. Empty means it is buildable."""
    problems: List[str] = []
    if not plan.units:
        return ["no units"]
    if not (MIN_UNITS <= len(plan.units) <= MAX_UNITS):
        problems.append(f"unit count {len(plan.units)} outside {MIN_UNITS}-{MAX_UNITS}")
    for index, unit in enumerate(plan.units, 1):
        if not str(unit.title or "").strip():
            problems.append(f"unit {index} has no title")
        if not (MIN_TOPICS_PER_UNIT <= len(unit.topics) <= MAX_TOPICS_PER_UNIT):
            problems.append(
                f"unit {index} has {len(unit.topics)} topics, want "
                f"{MIN_TOPICS_PER_UNIT}-{MAX_TOPICS_PER_UNIT}")
        for topic in unit.topics:
            if not str(topic.title or "").strip():
                problems.append(f"unit {index} has an untitled topic")
    if plan.lesson_count > MAX_LESSONS:
        problems.append(f"{plan.lesson_count} lessons exceeds the {MAX_LESSONS} the budget allows")

    seen = set()
    for topic in plan.topics:
        key = topic.title.strip().casefold()
        if key in seen:
            problems.append(f"duplicate topic {topic.title!r}")
        seen.add(key)

    # A beginner course in a language the learner cannot yet read must teach the
    # script first. Every other ordering rule is the model's judgement; this one
    # is structural, and getting it wrong makes lesson one unreadable.
    #
    # Scoped to A1 on purpose. A B2 Russian course opening with the Cyrillic
    # alphabet would be insulting, and a rule that fires at every level would
    # have forced one — the learner arrived able to read.
    profile = S.profile_for_language(plan.language)
    beginner = str(plan.level or "").strip().upper().startswith("A1")
    if beginner and profile and set(profile.scripts) - {"Latin"} and plan.topics:
        opener = f"{plan.topics[0].title} {plan.topics[0].type}".casefold()
        if not any(hint in opener for hint in
                   ("script", "alphabet", "alfabe", "sound", "ses", "phonetic", "writing",
                    "kana", "hangul", "harf", "pronunc")):
            problems.append("a non-Latin course must open with its writing system")
    return problems


# ── Generation ───────────────────────────────────────────────────────────────

def _system(language: str, level: str, track: str) -> str:
    band = P.cefr_band(level)
    profile = S.profile_for_language(language)
    script_line = ""
    if profile and set(profile.scripts) - {"Latin"}:
        script_line = (f"\n- {language} is written in {' + '.join(profile.scripts)}. Unit 1 "
                       f"MUST teach the writing system and its sounds before any word is "
                       f"asked to be read.")
    return f"""You are the curriculum architect for AulaAI. You plan one CEFR {level} course in {language} for adult learners. You return one JSON object and nothing else.

A CEFR {level} learner can {band['can']}.
- STRUCTURAL CEILING for the whole course: {band['ceiling']}.
- LEXIS: {band['lexis']}.

PLANNING RULES
- Between {MIN_UNITS} and {MAX_UNITS} units, each with {MIN_TOPICS_PER_UNIT} to {MAX_TOPICS_PER_UNIT} topics. Never more than {MAX_LESSONS} topics in total.
- Strict progression: every topic must be teachable using only what earlier topics taught. Nothing may depend on a later unit.{script_line}
- Each topic states, in `teaches`, the specific things it introduces — the structures, functions and word families a later topic is allowed to assume. Be concrete: "present tense of ser/estar", not "basic grammar".
- Each unit has one communicative goal a learner could name.
- Cover what this level genuinely needs and stop. Do not pad to fill units, and do not reach above the ceiling to look thorough.
- Give each topic a `type` from: {", ".join(TOPIC_TYPES)}.

TITLES ARE BILINGUAL. Every unit and every topic carries BOTH an English title
and a Turkish one, because the lecturer's curriculum editor shows the two side
by side. They must be the same title in two languages — a real Turkish title,
not the English one copied across, and not a transliteration. Write `teaches`
and `goal` in English only.

Return ONLY:
{{
  "units": [
    {{
      "title": "Unit title in English",
      "title_tr": "Aynı ünite başlığı, doğal Türkçe",
      "goal": "What the learner can do after it, in English",
      "topics": [
        {{"title": "Topic title in English", "title_tr": "Aynı konu başlığı, doğal Türkçe", "type": "vocabulary", "teaches": ["concrete item", "concrete item"]}}
      ]
    }}
  ]
}}"""


def _parse(payload: Any, language: str, level: str, track: str) -> Optional[CoursePlan]:
    if isinstance(payload, list):
        payload = {"units": payload}
    if not isinstance(payload, dict):
        return None
    raw_units = payload.get("units") or payload.get("chapters") or []
    if not isinstance(raw_units, list) or not raw_units:
        return None
    units: List[Unit] = []
    for raw in raw_units[:MAX_UNITS]:
        if not isinstance(raw, dict):
            continue
        topics: List[Topic] = []
        for raw_topic in (raw.get("topics") or [])[:MAX_TOPICS_PER_UNIT]:
            if isinstance(raw_topic, str):
                topics.append(Topic(raw_topic.strip()))
            elif isinstance(raw_topic, dict):
                title = str(raw_topic.get("title") or "").strip()
                if not title:
                    continue
                teaches = raw_topic.get("teaches")
                topics.append(Topic(title, str(raw_topic.get("type") or "vocabulary").strip(),
                                    [str(t).strip() for t in teaches
                                     if str(t).strip()] if isinstance(teaches, list) else [],
                                    title_tr=str(raw_topic.get("title_tr") or "").strip()))
        if topics:
            units.append(Unit(str(raw.get("title") or "").strip(),
                              str(raw.get("goal") or "").strip(), topics,
                              title_tr=str(raw.get("title_tr") or "").strip()))
    return CoursePlan(language, level, track, units) if units else None


def _trim_to_budget(plan: CoursePlan) -> CoursePlan:
    """Drop trailing topics until the plan fits, rather than failing the build."""
    while plan.lesson_count > MAX_LESSONS and plan.units:
        for unit in reversed(plan.units):
            if len(unit.topics) > MIN_TOPICS_PER_UNIT:
                unit.topics.pop()
                break
        else:
            plan.units.pop()
    return plan


def plan_course(*, language: str, level: str, track: str = "tr",
                ledger: Optional[B.BuildLedger] = None, extra: str = "",
                model: str = "") -> CoursePlan:
    """The course plan. Falls back to a skeleton rather than failing a build."""
    ledger = ledger or B.BuildLedger(label=f"{language} {level}")
    system = _system(language, level, track)
    user = (f"Plan the complete CEFR {level} {language} course."
            + (f"\n\nAdditional requirements: {extra}" if extra else ""))

    input_tokens = int((len(system) + len(user)) / 4)
    ceiling = 2600
    try:
        ledger.require(stage="curriculum", input_tokens=input_tokens, output_tokens=ceiling)
    except B.BudgetExceeded:
        return skeleton_plan(language, level, track)

    response = T.call_model(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=ceiling, temperature=0.4, model=model or B.MODEL)
    ledger.record(stage="curriculum", subject=f"{language} {level}", wasted=not response.ok,
                  input_tokens=response.input_tokens or input_tokens,
                  output_tokens=response.output_tokens, cached_tokens=response.cached_tokens,
                  reported_cost=response.cost)
    if not response.ok:
        return skeleton_plan(language, level, track)

    plan = _parse(response.data, language, level, track)
    if plan is None:
        return skeleton_plan(language, level, track)
    plan = _trim_to_budget(plan)
    if validate_plan(plan):
        # One repair pass: drop malformed units, then accept if what remains is
        # buildable. A second model call to fix a plan costs more than the plan.
        plan.units = [u for u in plan.units
                      if str(u.title or "").strip() and len(u.topics) >= MIN_TOPICS_PER_UNIT]
        if validate_plan(plan):
            return skeleton_plan(language, level, track)
    return plan


# ── The fallback ─────────────────────────────────────────────────────────────

# Each row is (English title, Turkish title, type, what it teaches). The Turkish
# column is written out rather than translated at run time for the same reason
# the planner emits both: this is the fallback, so it runs when the model is
# unavailable, and a fallback that needs a model call is not one.
_SKELETON = {
    "A1": [("Sounds and writing", "Sesler ve Yazı Sistemi", "phonetics",
            ["the writing system", "the sound inventory"]),
           ("Greetings and introductions", "Selamlaşma ve Tanışma", "vocabulary",
            ["greeting formulas", "saying your name"]),
           ("Numbers, time and prices", "Sayılar, Saat ve Fiyatlar", "vocabulary",
            ["numbers 0-100", "telling the time"]),
           ("People, family and description", "İnsanlar, Aile ve Tanımlama", "vocabulary",
            ["family words", "basic adjectives"]),
           ("Everyday actions in the present", "Günlük Eylemler: Şimdiki Zaman", "grammar",
            ["present tense of frequent verbs"]),
           ("Getting around and asking for things", "Yol Sorma ve İstekte Bulunma", "dialogue",
            ["requests", "directions"])],
    "A2": [("Talking about the past", "Geçmişten Söz Etmek", "grammar",
            ["the common past tense"]),
           ("Plans and the future", "Planlar ve Gelecek", "grammar", ["future forms"]),
           ("Shopping, food and services", "Alışveriş, Yemek ve Hizmetler", "vocabulary",
            ["transactional language"]),
           ("Home, work and routine", "Ev, İş ve Günlük Düzen", "vocabulary",
            ["daily routine", "workplace words"]),
           ("Giving reasons and opinions", "Gerekçe ve Görüş Bildirme", "grammar",
            ["simple connectors"]),
           ("Travel and arrangements", "Seyahat ve Düzenlemeler", "dialogue",
            ["booking", "timetables"])],
    "B1": [("Narrating experience", "Deneyim Anlatımı", "grammar",
            ["past tenses in contrast"]),
           ("Opinions and justification", "Görüş ve Gerekçelendirme", "grammar",
            ["standard connectors"]),
           ("Work and study", "İş ve Eğitim", "vocabulary",
            ["workplace and academic register"]),
           ("Problems and solutions", "Sorunlar ve Çözümler", "dialogue",
            ["complaints", "negotiation"]),
           ("Conditions and hypotheses", "Koşullar ve Varsayımlar", "grammar",
            ["everyday conditionals"]),
           ("Reading connected text", "Bağlantılı Metin Okuma", "reading",
            ["extended comprehension"])],
    "B2": [("Argument and counter-argument", "Sav ve Karşı Sav", "grammar",
            ["concession and contrast"]),
           ("Abstract and specialised topics", "Soyut ve Uzmanlık Konuları", "vocabulary",
            ["abstract lexis"]),
           ("Register and formality", "Üslup ve Resmiyet", "grammar",
            ["formal and informal contrast"]),
           ("Reported and attributed speech", "Aktarılan Söz", "grammar",
            ["reported speech"]),
           ("Extended narrative", "Uzun Anlatı", "reading", ["long-form comprehension"]),
           ("Professional interaction", "Profesyonel İletişim", "dialogue",
            ["meetings", "correspondence"])],
    "C1": [("Implicit meaning and inference", "Örtük Anlam ve Çıkarım", "reading",
            ["reading between the lines"]),
           ("Cohesion across paragraphs", "Paragraflar Arası Bağdaşıklık", "grammar",
            ["discourse organisation"]),
           ("Idiom and collocation", "Deyim ve Eşdizim", "vocabulary",
            ["idiomatic precision"]),
           ("Stylistic word order", "Üslupsal Sözcük Dizimi", "grammar",
            ["marked constructions"]),
           ("Debate and nuance", "Tartışma ve İnce Ayrım", "dialogue", ["qualified argument"]),
           ("Synthesis of sources", "Kaynakların Sentezi", "reading",
            ["summarising across texts"])],
    "C2": [("Fine shades of meaning", "İnce Anlam Ayrımları", "vocabulary",
            ["near-synonym discrimination"]),
           ("Rhetoric and figurative language", "Retorik ve Mecaz", "reading",
            ["figurative interpretation"]),
           ("Literary and historical register", "Yazınsal ve Tarihsel Üslup", "reading",
            ["marked register"]),
           ("Precision under complexity", "Karmaşıklıkta Kesinlik", "grammar",
            ["complex subordination"]),
           ("Reconstructing argument", "Savı Yeniden Kurma", "reading", ["source synthesis"]),
           ("Spontaneous formal speech", "Hazırlıksız Resmi Konuşma", "dialogue",
            ["extended formal turns"])],
}


def skeleton_plan(language: str, level: str, track: str = "tr") -> CoursePlan:
    """A correct if unambitious course, used when planning fails.

    Deliberately not a placeholder: a learner who receives this gets a coherent,
    correctly ordered course. It exists so that a provider outage degrades the
    ambition of a build rather than its validity.
    """
    key = str(level or "A1").strip().upper()[:2]
    rows = _SKELETON.get(key, _SKELETON["A1"])
    if key != "A1":
        rows = [r for r in rows if r[2] != "phonetics"] or rows

    def topic(row) -> Topic:
        title, title_tr, kind, teaches = row
        return Topic(title, kind, teaches, title_tr=title_tr)

    units: List[Unit] = []
    for index in range(0, len(rows), 2):
        chunk = rows[index:index + 2]
        if len(chunk) < 2 and units:
            units[-1].topics.extend(topic(r) for r in chunk)
            break
        units.append(Unit(title=chunk[0][0], goal="", topics=[topic(r) for r in chunk],
                          title_tr=chunk[0][1]))
    return CoursePlan(language, level, track, units, notes="skeleton")
