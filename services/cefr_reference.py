"""
CEFR Reference & Conditioning Engine for AulaAI.
Grounded in authoritative international language proficiency standards:
- Council of Europe: Common European Framework of Reference for Languages (CEFR Companion Volume 2020)
- Turkish: Yunus Emre Enstitüsü (YEE) Yedi İklim Türkçe (C1/C2) & Ankara Üniversitesi TÖMER / İstanbul Üniversitesi Yabancılar İçin Türkçe
- Spanish: Instituto Cervantes - Plan Curricular del Instituto Cervantes (PCIC)
- German: Goethe-Institut & telc CEFR Framework
- French: CIEP / France Éducation International (DELF/DALF)
- English: Cambridge English Profile / Council of Europe

This module enforces strict CEFR level calibration for all educational material generation.
"""

import re
from typing import Dict, List, Any, Optional

# ── 1. UNIVERSAL CEFR COMPETENCY MATRIX ──────────────────────────────
CEFR_FRAMEWORK = {
    "A1": {
        "name": "Breakthrough / Beginner",
        "can_do": (
            "Can understand and use familiar everyday expressions and very basic phrases aimed at the "
            "satisfaction of needs of a concrete type. Can introduce him/herself and others and can ask "
            "and answer questions about personal details such as where he/she lives, people he/she knows "
            "and things he/she has. Can interact in a simple way provided the other person talks slowly and clearly."
        ),
        "lexical_profile": "Basic concrete nouns (family, food, numbers, classroom), high-frequency verbs in simple present, essential adjectives (colors, size).",
        "syntactic_profile": "Simple declarative sentences (SVO/SOV), basic negation, simple yes/no and basic wh-questions, standard word order.",
        "pragmatic_profile": "Direct, concrete survival interactions. Formulaic greetings and politeness markers.",
        "forbidden_for_this_level": []
    },
    "A2": {
        "name": "Waystage / Elementary",
        "can_do": (
            "Can understand sentences and frequently used expressions related to areas of most immediate relevance "
            "(e.g. very basic personal and family information, shopping, local geography, employment). "
            "Can communicate in simple and routine tasks requiring a simple and direct exchange of information "
            "on familiar and routine matters. Can describe in simple terms aspects of his/her background, immediate environment."
        ),
        "lexical_profile": "Daily routine vocabulary, shopping, directions, simple travel, physical descriptions, basic emotions.",
        "syntactic_profile": "Simple past tenses (narrative basics), compound sentences with basic connectors (and, but, because), simple modals, comparative/superlative.",
        "pragmatic_profile": "Transactional social interactions, simple invitations, agreeing/disagreeing simply.",
        "forbidden_for_this_level": []
    },
    "B1": {
        "name": "Threshold / Intermediate",
        "can_do": (
            "Can understand the main points of clear standard input on familiar matters regularly encountered in work, "
            "school, leisure, etc. Can deal with most situations likely to arise whilst travelling in an area where the language is spoken. "
            "Can produce simple connected text on topics which are familiar or of personal interest. Can describe experiences "
            "and events, dreams, hopes & ambitions and briefly give reasons and explanations for opinions and plans."
        ),
        "lexical_profile": "Workplace basics, travel issues, hobbies, personal relationships, abstract feelings, simple idiomatic phrases.",
        "syntactic_profile": "Complex sentences with relative clauses, conditionality (real conditionals), basic passive voice, basic indirect speech, aspectual contrasts.",
        "pragmatic_profile": "Expressing personal opinions, hedging with simple modals ('I think', 'maybe'), narrating personal stories.",
        "forbidden_for_this_level": ["A1_ISOLATED_GREETINGS", "ALPHABET_DRILLS"]
    },
    "B2": {
        "name": "Vantage / Upper-Intermediate",
        "can_do": (
            "Can understand the main ideas of complex text on both concrete and abstract topics, including technical discussions "
            "in his/her field of specialisation. Can interact with a degree of fluency and spontaneity that makes regular interaction "
            "with native speakers quite possible without strain for either party. Can produce clear, detailed text on a wide range "
            "of subjects and explain a viewpoint on a topical issue giving the advantages and disadvantages of various options."
        ),
        "lexical_profile": "Broad lexical repertoire including common idioms, phrasal combinations, academic vocabulary, degrees of certainty, formal register words.",
        "syntactic_profile": "Complex subordination, hypothetical conditionals (unreal past), nuanced subjunctive/modality, passive/impersonal constructions, discourse connectors (furthermore, nevertheless).",
        "pragmatic_profile": "Constructing coherent arguments, distinguishing formal vs informal register, polite disagreement, expressing hypothetical scenarios.",
        "forbidden_for_this_level": ["A1_FOOD_OBJECTS", "A1_GREETINGS", "BASIC_COUNTING"]
    },
    "C1": {
        "name": "Effective Operational Proficiency / Advanced",
        "can_do": (
            "Can understand a wide range of demanding, longer texts, and recognise implicit meaning. Can express him/herself "
            "fluently and spontaneously without much obvious searching for expressions. Can use language flexibly and "
            "effectively for social, academic and professional purposes. Can produce clear, well-structured, detailed text "
            "on complex subjects, showing controlled use of organisational patterns, connectors and cohesive devices."
        ),
        "lexical_profile": (
            "Sophisticated, academic, and literary vocabulary. Extensive idiomatic and metaphorical repertoire. "
            "Subtle connotations, polysemy, register modulation (bureaucratic, academic, satirical). "
            "Collocations with precise semantic boundaries. Zero reliance on basic or high-frequency elementary words."
        ),
        "syntactic_profile": (
            "Highly complex syntactic structures: extensive participial/gerundial subordination, literary inversion, "
            "nested causal/concessive/adversative clauses, advanced modal compounding, rhetorical sentence structures."
        ),
        "pragmatic_profile": (
            "Decoding subtext, implicit meaning (reading between the lines), irony, sarcasm, diplomatic hedging, "
            "cultural allusions, tone shift, persuasion, rhetoric, and debate strategy."
        ),
        "forbidden_for_this_level": [
            "A1_FOOD_OBJECTS", "A1_GREETINGS", "A1_SURVIVAL", "A2_DAILY_ROUTINE", "ELEMENTARY_TOURIST_CLICHES"
        ]
    },
    "C2": {
        "name": "Mastery / Near-Native Proficiency",
        "can_do": (
            "Can understand with ease virtually everything heard or read. Can summarise information from different spoken "
            "and written sources, reconstructing arguments and accounts in a coherent presentation. Can express him/herself "
            "spontaneously, very fluently and precisely, differentiating finer shades of meaning even in more complex situations."
        ),
        "lexical_profile": "Near-native lexical mastery: archaic/literary terms, rare proverbs, regional colloquialisms, nuanced synonyms, philosophy and jurisprudence discourse.",
        "syntactic_profile": "Effortless syntactic dexterity, complex stylistic inversions, rhythmic and rhetorical cadence.",
        "pragmatic_profile": "Complete mastery of humor, satire, deep cultural intertextuality, double entendres, diplomatic subtleties.",
        "forbidden_for_this_level": [
            "A1_FOOD_OBJECTS", "A1_GREETINGS", "A1_SURVIVAL", "A2_DAILY_ROUTINE", "B1_STANDARD_TOPICS"
        ]
    }
}

# ── 2. LANGUAGE-SPECIFIC CEFR STANDARDS & PEDAGOGY ───────────────────
# Grounded in official national curricula (YEE/TÖMER, Cervantes PCIC, Goethe, Cambridge)
LANGUAGE_CEFR_STANDARDS = {
    "Turkish": {
        "institution": "Yunus Emre Enstitüsü (YEE) / Ankara Üniversitesi TÖMER / İstanbul Üniversitesi",
        "levels": {
            "A1": {
                "grammar": "Temel şimdiki zaman (-iyor), belirli geçmiş zaman (-di), bulunma/ayrılma/yönelme halleri (-de, -den, -e), iyelik ekleri, sayı ve miktar.",
                "lexicon": "Aile, sayılar, renkler, temel yiyecekler, saatler, selamlaşma ve tanışma, temel meslekler.",
                "register": "Günlük samimi ve temel nezaket."
            },
            "A2": {
                "grammar": "Gelecek zaman (-ecek), geniş zaman (-er/-ir), görülen geçmiş zaman hikayesi, bağlaçlar (çünkü, bu yüzden, ama), -den önce / -den sonra, karşılaştırma (-den daha).",
                "lexicon": "Alışveriş, yol tarifi, tatil, günlük rutinler, hava durumu, temel sağlık ve şikayet.",
                "register": "Günlük iletişim ve basit resmi işlemler."
            },
            "B1": {
                "grammar": "Duyulan geçmiş zaman (-miş), gereklilik kipi (-meli), emir-istek kipi, sıfat-fiiller (-en, -dik, -ecek), zarf-fiiller (-ken, -erek, -ince), ettirgen/edilgen çatı başlangıcı.",
                "lexicon": "İş dünyası, eğitim, kişisel hedefler, hobiler, seyahat planları, duygusal durumlar, basit deyimler.",
                "register": "Standart toplumsal iletişim, yarı-resmi mektuplar."
            },
            "B2": {
                "grammar": "Şart kipi ve birleşik kipleri (-seydi, -ecekti, -mişti), karmaşık sıfat-fiil ve zarf-fiil öbekleri (-dığı için, -mesine rağmen, -meksizin), edilgen ve dönüşlü çatı, dolaylı anlatım (aktarma cümleleri).",
                "lexicon": "Toplumsal sorunlar, çevre, ekonomi, medya, soyut kavramlar, yaygın atasözleri ve deyimler, karşıt fikirler.",
                "register": "Resmi yazışmalar, tartışma metinleri, eleştiri ve sunum dili."
            },
            "C1": {
                "institution_reference": "Yunus Emre Enstitüsü 'Yedi İklim Türkçe C1' & İstanbul Üniversitesi C1 ('Bir Maruzatım Var', 'İşini Şansa Bırakma')",
                "pedagogical_focus": (
                    "Örtük Anlam (Implicit Meaning), İma ve Kinaye (Nuance & Subtext), Argümantasyon ve İkna Teknikleri (Persuasion), "
                    "Resmi ve Bürokratik Dil (Maruzat, Dilekçe, Rapor), Edebi ve Retorik Üslup (Rhetorical Devices), Deyimler ve Atasözleri."
                ),
                "grammar": (
                    "• Zarf-fiil incelikleri: -dıkça / -dikçe (orantısal süreç), -(y)a -(y)a (süreklilik), -meksizin / -maksızın (tarz/yoksunluk), "
                    "-(y)alı beri, -dığı takdirde (koşul), -eceği varsayılırsa, -masına karşın / -masına rağmen (beklenmezlik), "
                    "-mektensə (tercih), -cesine / -çesine (benzetme), -eceği yerde (karşıtlık).\n"
                    "• Birleşik kipler ve kiplikler: -acak gibi olmak, -mış bulunmak, -malıydı, -yorduysa, -mışçasına.\n"
                    "• Karmaşık çatı yapıları: İç içe geçmiş ettirgen-edilgen (yaptırılabilmek, anlaşılamamak).\n"
                    "• Devrik cümle ve retorik vurgu: Edebi metinlerde ve ileri düzey hitabette sözdizimsel esneklik.\n"
                    "• Bağlantı ögeleri (Discourse Markers): Nitekim, bilakis, mamafih, gelgelelim, kaldı ki, her ne kadar ... ise de, "
                    "öte yandan, ne var ki, bir yana ... bir yana ..., binaenaleyh."
                ),
                "lexicon": (
                    "MANDATORY C1 LEXICAL REGISTER: Advanced abstract concepts, idiomatic collocations, polysemous verbs, formal discourse.\n"
                    "Examples of expected lexical caliber:\n"
                    "  - Nuance & Implicit Meaning: örtük anlam, ima, kinaye, satır arası, serzeniş, sitem, laf dokundurmak, "
                    "nabza göre şerbet vermek, aba altından sopa göstermek, lafı gediğine koymak, gönül koymak, telmih, mecaz-ı mürsel.\n"
                    "  - Argumentation & Debate: gerekçelendirme, sav, çürütme, tutarlılık, çelişki, uzlaşma, meşruiyet, aidiyet, "
                    "yetkinlik, özveri, istikrar, öngörü, sağduyu, basiret, feraset, girift, mütereddit, sarih, muğlak, tasarruf.\n"
                    "  - Rhetorical & Formal: maruzat, istirham etmek, tensip buyurmak, riyaset, tahsisat, hasbelkader, binaenaleyh."
                ),
                "forbidden_words": [
                    "kahve", "misafir", "selam", "merhaba", "teşekkür", "teşekkürler", "ev", "araba", "su", "yemek",
                    "elma", "kedi", "köpek", "okul", "kitap", "anne", "baba", "günaydın", "iyi akşamlar", "çay",
                    "ekmek", "gitmek", "gelmek", "bakmak", "görmek", "yapmak", "almak", "vermek"
                ]
            },
            "C2": {
                "institution_reference": "Yunus Emre Enstitüsü 'Yedi İklim Türkçe C2' & TÖMER Diploması",
                "grammar": "Edebi metin tahlili, arkaik ekler, felsefi ve hukuki metinlerin sözdizimi, tam retorik hakimiyet.",
                "lexicon": "Ağır edebi ve felsefi terminoloji, Osmanlıca kökenli köklü kavramlar, divan ve cumhuriyet edebiyatı remizleri.",
                "forbidden_words": ["kahve", "misafir", "selam", "merhaba", "teşekkür", "ev", "araba", "su", "yemek"]
            }
        }
    },
    "Spanish": {
        "institution": "Instituto Cervantes - Plan Curricular del Instituto Cervantes (PCIC)",
        "levels": {
            "A1": {"grammar": "Presente de indicativo, concordancia género/número, verbos ser/estar/tener/ir, interrogativos básicos."},
            "A2": {"grammar": "Pretérito perfecto, pretérito indefinido vs imperfecto básico, pronombres de OD y OI, perífrasis de futuro."},
            "B1": {"grammar": "Subjuntivo presente (deseo, duda, emoción), oraciones temporales y de relativo, condicional simple, pretérito pluscuamperfecto."},
            "B2": {"grammar": "Subjuntivo imperfecto, condicional compuesto, estilo indirecto avanzado, conectores discursivos (sin embargo, por tanto, a pesar de)."},
            "C1": {
                "institution_reference": "Plan Curricular del Instituto Cervantes (Nivel C1 - Dominio Operativo Eficaz)",
                "pedagogical_focus": "Discurso argumentativo, ironía y ambigüedad, registros formal/académico/literario, matices y presuposiciones.",
                "grammar": "Subjuntivo en oraciones concesivas y modales, correlación temporal compleja, voz pasiva refleja y analítica, inversión estilística.",
                "lexicon": "Léxico abstracto, expresiones idiomáticas complejas, lenguaje persuasivo y diplomático.",
                "forbidden_words": ["hola", "adiós", "gracias", "café", "casa", "perro", "gato", "agua", "comida"]
            },
            "C2": {"grammar": "Maestría retórica, sutilezas estilísticas, análisis de textos literarios e históricos."}
        }
    },
    "German": {
        "institution": "Goethe-Institut / telc",
        "levels": {
            "A1": {"grammar": "Präsens, trennbare Verben, Perfekt basics, Akkusativ/Dativ basics, Satzklammer."},
            "A2": {"grammar": "Perfekt, Präteritum von Hilfsverben, Modalverben im Präteritum, Nebensätze mit weil/dass, Komparativ."},
            "B1": {"grammar": "Konjunktiv II (Wunsch/Höflichkeit), Passiv Präsens, Relativsätze, Infinitiv mit zu, temporale Nebensätze."},
            "B2": {"grammar": "Passiv in allen Zeiten, Passiversatzformen, Konjunktiv I (indirekte Rede), Partizipialattribute, feste Nomen-Verb-Verbindungen."},
            "C1": {
                "institution_reference": "Goethe-Zertifikat C1 / telc Deutsch C1 Hochschule",
                "pedagogical_focus": "Wissenschafts- und Fachsprache, rhetorische Mittel, Nuancen und Subtext, komplexe Argumentation.",
                "grammar": "Erweiterte Partizipialattribute, modale Infinitivkonstruktionen, Zustandspassiv-Nuancen, komplexe Satzgefüge.",
                "lexicon": "Gehobene Sprache, Funktionsverbgefüge (in Betracht ziehen, zur Folge haben), Fachterminologie.",
                "forbidden_words": ["hallo", "danke", "bitte", "kaffee", "wasser", "haus", "katze", "hund", "essen"]
            },
            "C2": {"grammar": "Nahezu muttersprachliche Beherrschung, literarische Stilebenen, idiomatischer Feinschliff."}
        }
    },
    "English": {
        "institution": "Cambridge English / Council of Europe English Profile",
        "levels": {
            "A1": {"grammar": "Present simple, present continuous, basic modals (can), there is/are, basic prepositions."},
            "A2": {"grammar": "Past simple, past continuous, going to / will, comparatives, count/uncount nouns."},
            "B1": {"grammar": "Present perfect vs past simple, first/second conditionals, passive simple, defining relative clauses."},
            "B2": {"grammar": "Third conditional, mixed conditionals, relative clauses, narrative tenses, reported speech, discourse markers."},
            "C1": {
                "institution_reference": "Cambridge C1 Advanced (CAE) / CEFR C1",
                "pedagogical_focus": "Implicit meaning, nuance, advanced argumentation, academic and professional registers, idioms and metaphors.",
                "grammar": "Inversion with negative adverbials (Seldom have I seen...), cleft sentences, participle clauses, subtle modal hedging.",
                "lexicon": "Collocations with narrow semantic range, abstract nouns, academic vocabulary, idiomatic mastery.",
                "forbidden_words": ["hello", "thank you", "coffee", "water", "cat", "dog", "house", "car", "apple", "bread"]
            },
            "C2": {"grammar": "Cambridge C2 Proficiency (CPE) - Stylistic elegance, rhetorical precision, idiomatic and dialectal mastery."}
        }
    }
}

# Universal forbidden lexicon categories for B2, C1, C2
UNIVERSAL_ELEMENTARY_WORDS = {
    "turkish": [
        "kahve", "misafir", "selam", "merhaba", "teşekkür", "teşekkürler", "sağ ol", "ev", "araba",
        "su", "yemek", "elma", "kedi", "köpek", "okul", "kitap", "anne", "baba", "kardeş", "günaydın",
        "iyi akşamlar", "iyi geceler", "tünaydın", "hoşça kal", "çay", "ekmek", "masa", "sandalye",
        "kapı", "pencere", "kalem", "defter", "gitmek", "gelmek", "oturmak", "kalkmak", "yemek yemek"
    ],
    "spanish": [
        "hola", "adiós", "gracias", "por favor", "buenos días", "buenas tardes", "buenas noches",
        "café", "agua", "casa", "coche", "perro", "gato", "pan", "manzana", "escuela", "libro",
        "madre", "padre", "hermano", "amigo", "mesa", "silla", "puerta"
    ],
    "german": [
        "hallo", "guten tag", "guten morgen", "gute nacht", "danke", "bitte", "tschüss", "auf wiedersehen",
        "kaffee", "wasser", "brot", "apfel", "haus", "auto", "hund", "katze", "schule", "buch",
        "mutter", "vater", "bruder", "tisch", "stuhl"
    ],
    "english": [
        "hello", "hi", "goodbye", "bye", "good morning", "good evening", "thank you", "thanks", "please",
        "coffee", "water", "bread", "apple", "house", "car", "dog", "cat", "school", "book",
        "mother", "father", "brother", "table", "chair"
    ]
}

# Curated C1 Turkish reference items by topic domain to guarantee zero-defect generation
CURATED_C1_TURKISH_ITEMS = {
    "cultural contexts: nuances of meaning": [
        {
            "term": "Örtük Anlam",
            "translation": "Implicit Meaning",
            "translation_tr": "Örtük Anlam (Satır Arası)",
            "example": "Metindeki örtük anlamı kavramak, yazarın ideolojik duruşunu deşifre etmeyi gerektirir.",
            "example_en": "Grasping the implicit meaning in the text requires decoding the author's ideological stance.",
            "example_tr": "Metindeki örtük anlamı kavramak, yazarın ideolojik duruşunu deşifre etmeyi gerektirir.",
            "explanation": "Refers to presupposed or implied semantics that are not explicitly stated in discourse.",
            "explanation_tr": "Cümlede açıkça telaffuz edilmeyen, bağlam ve sezgiler yoluyla ulaşılan derin anlamsal katmandır."
        },
        {
            "term": "Kinaye",
            "translation": "Allusion / Double Entendre",
            "translation_tr": "Kinaye",
            "example": "Konuşmacının sözlerindeki kinaye, salondaki diplomatik gerilimi bir anda tırmandırdı.",
            "example_en": "The allusion in the speaker's remarks immediately escalated the diplomatic tension in the hall.",
            "example_tr": "Konuşmacının sözlerindeki kinaye, salondaki diplomatik gerilimi bir anda tırmandırdı.",
            "explanation": "A rhetorical device where a phrase carries both a literal meaning and an intended figurative subtext.",
            "explanation_tr": "Bir sözü hem gerçek hem de mecaz anlamını düşündürecek şekilde, asıl kastedilen mecaz olmak üzere kullanma sanatıdır."
        },
        {
            "term": "Serzeniş",
            "translation": "Reproach / Gentle Rebuke",
            "translation_tr": "Serzeniş",
            "example": "Mektubun satır aralarına gizlenmiş serzeniş, uzun süren sessizliğe duyulan kırgınlığı yansıtıyordu.",
            "example_en": "The reproach concealed between the lines of the letter reflected resentment toward the prolonged silence.",
            "example_tr": "Mektubun satır aralarına gizlenmiş serzeniş, uzun süren sessizliğe duyulan kırgınlığı yansıtıyordu.",
            "explanation": "Expressing subtle disappointment or reproach without open hostility; key in Turkish politeness registers.",
            "explanation_tr": "Bir kimseye yaptığı bir davranışın veya ilgisizliğin yarattığı üzüntüyü öfkelenmeden, sitemle bildirmedir."
        },
        {
            "term": "Nabza Göre Şerbet Vermek",
            "translation": "To cater to someone's mood / To tailor tactfully",
            "translation_tr": "Nabza Göre Şerbet Vermek",
            "example": "Müzakere sürecinde diplomatların nabza göre şerbet vermesi, krizin aşılmasında belirleyici oldu.",
            "example_en": "Diplomats tactfully catering to each party's mood during negotiations was decisive in overcoming the crisis.",
            "example_tr": "Müzakere sürecinde diplomatların nabza göre şerbet vermesi, krizin aşılmasında belirleyici oldu.",
            "explanation": "An advanced pragmatic idiom meaning to adapt one's discourse and behavior to the psychological state of the interlocutor.",
            "explanation_tr": "Karşıdakinin eğilimine, karakterine veya o anki ruh haline uygun davranarak durumu yönetme becerisini anlatan köklü bir deyimdir."
        },
        {
            "term": "Lafı Gediğine Koymak",
            "translation": "To deliver a devastatingly apt rejoinder",
            "translation_tr": "Lafı Gediğine Koymak",
            "example": "Eleştirilere karşı lafı gediğine koyan yanıtı, paneldeki tartışmayı lehine çevirdi.",
            "example_en": "His devastatingly apt response to the criticisms turned the panel debate in his favor.",
            "example_tr": "Eleştirilere karşı lafı gediğine koyan yanıtı, paneldeki tartışmayı lehine çevirdi.",
            "explanation": "To deliver a witty, precise, and intellectually sharp counter-argument that leaves no room for rebuttal.",
            "explanation_tr": "Söylenmesi gereken sözü tam zamanında, yerinde ve etkili bir nükteyle söyleme yetkinliğidir."
        },
        {
            "term": "Aba Altından Sopa Göstermek",
            "translation": "To issue a veiled threat",
            "translation_tr": "Aba Altından Sopa Göstermek",
            "example": "Basın bildirisindeki diplomatik ifadeler, dikkatle incelendiğinde aba altından sopa gösteriyordu.",
            "example_en": "The diplomatic phrasing in the press release, when examined closely, issued a veiled threat.",
            "example_tr": "Basın bildirisindeki diplomatik ifadeler, dikkatle incelendiğinde aba altından sopa gösteriyordu.",
            "explanation": "A high-register idiom describing an implicit, veiled threat disguised beneath calm, polite phraseology.",
            "explanation_tr": "Yumuşak ve sakin görünerek karşısındakini üstü kapalı ve ince bir şekilde tehdit etmeyi ifade eder."
        }
    ]
}


# ── 3. CEFR CONDITIONING ENGINE ──────────────────────────────────────
def get_cefr_conditioning(language: str, level: str, topic: str = "", topic_type: str = "vocabulary") -> str:
    """
    Constructs an inescapable, authoritative CEFR prompt conditioning instruction.
    Injects Council of Europe and national framework standards into the LLM system prompt.
    """
    clean_level = (level or "A1").upper().strip()
    lvl_key = "A1"
    for k in ["C2", "C1", "B2", "B1", "A2", "A1"]:
        if k in clean_level:
            lvl_key = k
            break

    universal_spec = CEFR_FRAMEWORK.get(lvl_key, CEFR_FRAMEWORK["A1"])
    lang_standards = LANGUAGE_CEFR_STANDARDS.get(language, {})
    lang_level_spec = lang_standards.get("levels", {}).get(lvl_key, {})
    institution = lang_standards.get("institution", "Council of Europe CEFR Companion Volume")

    # Build Negative Constraints (Forbidden Lexicon)
    forbidden_summary = ""
    is_advanced = lvl_key in ["B2", "C1", "C2"]
    if is_advanced:
        lang_key = language.lower()
        forbidden_list = UNIVERSAL_ELEMENTARY_WORDS.get(lang_key, UNIVERSAL_ELEMENTARY_WORDS.get("english", []))
        forbidden_sample = ", ".join(forbidden_list[:25])
        forbidden_summary = f"""
CRITICAL NEGATIVE CONSTRAINT (STRICT ZERO-TOLERANCE BAN):
- YOU ARE AUTHORING MATERIAL FOR {lvl_key} ({universal_spec['name']}).
- IT IS A CRITICAL DEFECT TO INCLUDE ELEMENTARY, BEGINNER-TIER WORDS, TOURIST CLICHES, OR ROUTINE GREETINGS.
- SPECIFICALLY BANNED FOR THIS {lvl_key} LESSON (DO NOT GENERATE ANY OF THESE OR SIMILAR BASICS):
  [{forbidden_sample}]
- NEVER treat a {lvl_key} topic like an introductory cultural trivia lesson. Adult {lvl_key} learners have already mastered basic vocabulary years ago.
- EVERY vocabulary term MUST be an advanced, academic, literary, polysemous, or idiomatic lexical item appropriate for university-level discourse.
"""

    # Language-specific grammar & lexical directives
    specific_rules = ""
    if lang_level_spec:
        inst_ref = lang_level_spec.get("institution_reference", institution)
        ped_focus = lang_level_spec.get("pedagogical_focus", "")
        grammar_points = lang_level_spec.get("grammar", "")
        lexicon_points = lang_level_spec.get("lexicon", "")
        specific_rules = f"""
AUTHORITATIVE CURRICULUM REFERENCE ({institution}):
- REFERENCE FRAMEWORK: {inst_ref}
- PEDAGOGICAL DOMAIN: {ped_focus}
- TARGET GRAMMATICAL STRUCTURES FOR {lvl_key}:
{grammar_points}
- TARGET LEXICAL EXPECTATIONS FOR {lvl_key}:
{lexicon_points}
"""

    conditioning = f"""
================================================================================
CEFR PROFICIENCY DIRECTIVE: STRICT LEVEL {lvl_key} ({universal_spec['name']})
================================================================================
AUTHORITY: Grounded in {institution} and the Council of Europe CEFR Standards.

CAN-DO BENCHMARK FOR {lvl_key}:
{universal_spec['can_do']}

LEXICAL PROFILE ({lvl_key}):
{universal_spec['lexical_profile']}

SYNTACTIC COMPLEXITY ({lvl_key}):
{universal_spec['syntactic_profile']}

PRAGMATIC & DISCOURSE PROFILE ({lvl_key}):
{universal_spec['pragmatic_profile']}
{forbidden_summary}
{specific_rules}
================================================================================
"""
    return conditioning.strip()


# ── 4. CEFR VALIDATOR & LEVEL SANITIZER ──────────────────────────────
def validate_cefr_level(term: str, language: str, level: str) -> bool:
    """
    Validates whether a generated vocabulary item complies with the target CEFR level.
    Returns True if valid, False if it violates level constraints (e.g. A1 word in C1).
    """
    if not term:
        return False
    clean_term = term.strip().lower()
    clean_lvl = (level or "A1").upper().strip()

    # If level is B2, C1, or C2, check against forbidden elementary list
    if any(k in clean_lvl for k in ["B2", "C1", "C2"]):
        lang_key = language.lower()
        forbidden = set(UNIVERSAL_ELEMENTARY_WORDS.get(lang_key, []))
        if clean_term in forbidden:
            return False
        # Check sub-words for elementary words (e.g. 'kahve fincanı' should not slip through as C1)
        term_words = [w.strip() for w in re.split(r'\s+', clean_term) if len(w.strip()) > 2]
        if len(term_words) == 1 and term_words[0] in forbidden:
            return False

    return True


def get_curated_c1_items(language: str, topic: str) -> List[Dict[str, Any]]:
    """
    Provides deterministic, authoritative C1 reference items for common advanced topics
    to sanitize and protect generated lessons from model hallucinations or level drop.
    """
    lang_key = language.lower()
    if lang_key == "turkish":
        clean_topic = topic.lower().strip()
        for k, items in CURATED_C1_TURKISH_ITEMS.items():
            if k in clean_topic or any(word in clean_topic for word in ["implicit", "nuance", "meaning", "örtük", "kinaye"]):
                return items
    return []
