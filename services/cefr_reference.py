"""
CEFR Reference & Conditioning Engine for AulaAI.
Grounded in authoritative international language proficiency standards for ALL supported languages:
- Turkish: Yunus Emre Enstitüsü (YEE) Yedi İklim Türkçe & Ankara Üniversitesi TÖMER
- Spanish: Instituto Cervantes - Plan Curricular del Instituto Cervantes (PCIC)
- German: Goethe-Institut & telc CEFR Framework
- French: France Éducation International (CIEP) - Cadre européen commun de référence (DELF/DALF)
- Italian: Università per Stranieri di Siena (CILS) & Perugia (CELI)
- Portuguese: Instituto Camões (CAPLE) & Celpe-Bras
- Russian: Pushkin State Russian Language Institute & TORFL (ТРКИ)
- Chinese (Mandarin): Center for Language Education and Cooperation (CLEC / Hanban) - HSK 3.0 / CEFR
- Japanese: Japan Foundation (JF Standard for Japanese-Language Education) & JLPT CEFR mapping
- Arabic: AL-Arabiyya Institute & CEFR Framework for Modern Standard Arabic
- Dutch: Nederlandse Taalunie & Certificaat Nederlands als Vreemde Taal (CNaVT)
- Swedish: Folkuniversitetet, Tisus & Swedex CEFR Framework
- Korean: National Institute for International Education (NIIED) - TOPIK / CEFR
- Greek: Centre for the Greek Language (Κέντρο Ελληνικής Γλώσσας - Πιστοποίηση Ελληνομάθειας)
- English: Cambridge English Profile & Council of Europe CEFR Companion Volume

This module enforces strict CEFR level calibration for all educational material generation across all languages.
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
            "Subtle connotations, polysemy, register modulation (authentic formal, academic, conversational, journalistic). "
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

# ── 2. LANGUAGE-SPECIFIC CEFR STANDARDS FOR ALL SUPPORTED LANGUAGES ──
LANGUAGE_CEFR_STANDARDS = {
    "Turkish": {
        "institution": "Yunus Emre Enstitüsü (YEE) / Ankara Üniversitesi TÖMER / İstanbul Üniversitesi",
        "levels": {
            "A1": {"grammar": "Şimdiki zaman (-iyor), belirli geçmiş zaman (-di), ad durum ekleri (-e, -de, -den, -i), iyelik ekleri."},
            "A2": {"grammar": "Gelecek zaman (-ecek), geniş zaman (-er/-ir), -den önce / sonra, karşılaştırma (-den daha), bağlaçlar."},
            "B1": {"grammar": "Duyulan geçmiş zaman (-miş), gereklilik (-meli), sıfat-fiiller (-en, -dik), zarf-fiiller (-ken, -erek)."},
            "B2": {"grammar": "Şart birleşik kipleri (-seydi, -ecekti), edilgen/dönüşlü çatı, dolaylı aktarma, karmaşık bağlaçlar."},
            "C1": {
                "institution_reference": "Yunus Emre Enstitüsü 'Yedi İklim Türkçe C1' & İstanbul Üniversitesi C1 ('Bir Maruzatım Var', 'İşini Şansa Bırakma')",
                "pedagogical_focus": "Örtük Anlam (Implicit Meaning), İma ve Kinaye (Nuance & Subtext), Argümantasyon ve İkna, Resmi/Akademik Dil, Deyimler ve Retorik.",
                "grammar": "Zarf-fiil incelikleri (-dıkça, -meksizin, -masına karşın, -eceği yerde, -casına), birleşik kipler (-acak gibi olmak, -mış bulunmak), devrik cümle, söylem belirleyicileri (nitekim, bilakis, mamafih, gelgelelim, kaldı ki).",
                "lexicon": "Örtük anlam, ima, kinaye, satır arası, serzeniş, sitem, laf dokundurmak, nabza göre şerbet vermek, aba altından sopa göstermek, lafı gediğine koymak, gönül koymak, telmih, gerekçelendirme, meşruiyet, aidiyet, basiret, feraset."
            },
            "C2": {"grammar": "Edebi metin tahlili, arkaik ekler, felsefi ve hukuki metinlerin sözdizimi, tam retorik hakimiyet."}
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
                "institution_reference": "Plan Curricular del Instituto Cervantes (Nivel C1 - Dominio Operativo Eficaz / DELE C1)",
                "pedagogical_focus": "Discurso argumentativo, ironía y ambigüedad, presuposiciones, registros formal/académico, expresiones idiomáticas complejas.",
                "grammar": "Subjuntivo en oraciones concesivas y modales complejas, correlación temporal avanzada, pasiva refleja/impersonal, inversión estilística, conectores argumentativos (por consiguiente, no obstante, en vista de que, ahora bien).",
                "lexicon": "Léxico abstracto, modismos y refranes, ambigüedad retórica, matices diplomáticos y académicos (sutileza, sesgo, perspicacia, menoscabo, reticencia, conjetura, paliar, vislumbrar)."
            },
            "C2": {"grammar": "Maestría retórica, sutilezas estilísticas, análisis de textos literarios e históricos."}
        }
    },
    "German": {
        "institution": "Goethe-Institut / telc Deutsch / ÖSD",
        "levels": {
            "A1": {"grammar": "Präsens, trennbare Verben, Perfekt basics, Akkusativ/Dativ basics, Satzklammer."},
            "A2": {"grammar": "Perfekt, Präteritum von Hilfsverben, Modalverben im Präteritum, Nebensätze mit weil/dass, Komparativ."},
            "B1": {"grammar": "Konjunktiv II (Wunsch/Höflichkeit), Passiv Präsens, Relativsätze, Infinitiv mit zu, temporale Nebensätze."},
            "B2": {"grammar": "Passiv in allen Zeiten, Passiversatzformen, Konjunktiv I (indirekte Rede), Partizipialattribute, feste Nomen-Verb-Verbindungen."},
            "C1": {
                "institution_reference": "Goethe-Zertifikat C1 / telc Deutsch C1 Hochschule",
                "pedagogical_focus": "Wissenschafts- und Fachsprache, rhetorische Mittel, Nuancen und Subtext, komplexe Argumentation, gehobenes Register.",
                "grammar": "Erweiterte Partizipialattribute (die zu treffenden Maßnahmen), modale Infinitivkonstruktionen (haben/sein + zu + Infinitiv), Konjunktiv I/II Nuancen, Zustandspassiv, Diskursmarker (insofern, allerdings, demzufolge, ungeachtet dessen).",
                "lexicon": "Funktionsverbgefüge (in Betracht ziehen, zur Folge haben, außer Zweifel stehen), gehobener Wortschatz (Ambivalenz, Schlüssigkeit, Diskrepanz, Implikation, Beschaffenheit, Zugeständnis)."
            },
            "C2": {"grammar": "Nahezu muttersprachliche Beherrschung, literarische Stilebenen, idiomatischer Feinschliff."}
        }
    },
    "French": {
        "institution": "France Éducation International (CIEP) - Cadre européen (DELF/DALF)",
        "levels": {
            "A1": {"grammar": "Présent de l'indicatif, articles définis/indéfinis, genre et nombre, négation simple (ne... pas), interrogations de base."},
            "A2": {"grammar": "Passé composé vs imparfait (sensibilisation), pronoms COD/COI, futur simple, comparatif/superlatif."},
            "B1": {"grammar": "Subjonctif présent (obligation, sentiment, doute), conditionnel présent, discours indirect au présent, pronoms relatifs qui/que/dont/où."},
            "B2": {"grammar": "Subjonctif passé, conditionnel passé, passif, double pronominalisation, connecteurs logiques (bien que, afin que, pourtant)."},
            "C1": {
                "institution_reference": "DALF C1 (Diplôme Approfondi de Langue Française) / CIEP",
                "pedagogical_focus": "Synthèse et argumentation, ironie, présuppositions, registre soutenu, figures de style et nuances culturelles.",
                "grammar": "Inversion du sujet après adverbes initiaux (à peine, peut-être), concordance des temps complexe, subjonctif imparfait (reconnaissance), participes présents et gérondifs en subordination, connecteurs rhétoriques (néanmoins, nonobstant, d'ores et déjà, quant à, force est de constater).",
                "lexicon": "Vocabulaire abstrait, registre soutenu, tournures idiomatiques (subtilité, réticence, équivoque, partialité, compromis, paradoxe, prérogative, perspicacité)."
            },
            "C2": {"grammar": "DALF C2 - Maîtrise stylistique littéraire, joutes oratoires et analyses critiques approfondies."}
        }
    },
    "Italian": {
        "institution": "Università per Stranieri di Siena (CILS) & Università per Stranieri di Perugia (CELI)",
        "levels": {
            "A1": {"grammar": "Presente indicativo, articoli, accordo genere/numero, verbi essere/avere, preposizioni semplici."},
            "A2": {"grammar": "Passato prossimo vs imperfetto, pronomi diretti/indiretti, preposizioni articolate, futuro semplice."},
            "B1": {"grammar": "Congiuntivo presente e passato, condizionale presente, periodo ipotetico della possibilità (2° tipo), particelle ci e ne."},
            "B2": {"grammar": "Congiuntivo imperfetto e trapassato, condizionale composto, periodo ipotetico dell'irrealtà, forma passiva (venire/andare + p.p.)."},
            "C1": {
                "institution_reference": "Certificazione di Italiano come Lingua Straniera (CILS C1 / CELI 4)",
                "pedagogical_focus": "Sfumature semantiche, ironia e impliciti, registro accademico e formale, figure retoriche e modi di dire complessi.",
                "grammar": "Concordanza complessa dei tempi del congiuntivo, gerundio implicito con valore concessivo/ipotetico, si passivante e impersonale complesso, connettivi testuali (tuttavia, nondimeno, benché, ciò premesso, per quanto concerne).",
                "lexicon": "Linguaggio forbito, locuzioni idiomatiche avanzate (sottigliezza, reticenza, perspicacia, discrepanza, ambiguità, encomio, velleità, perorare)."
            },
            "C2": {"grammar": "CILS C2 - Padronanza oratoria, linguaggio letterario e giuridico-amministrativo."}
        }
    },
    "Portuguese": {
        "institution": "Instituto Camões (CAPLE) & Ministério da Educação do Brasil (Celpe-Bras)",
        "levels": {
            "A1": {"grammar": "Presente do indicativo, ser vs estar, artigos, concordância de gênero/número, pronomes pessoais."},
            "A2": {"grammar": "Pretérito perfeito vs imperfeito, futuro do presente, pronomes oblíquos, comparativos."},
            "B1": {"grammar": "Presente do subjuntivo/conjuntivo, condicional/futuro do pretérito, infinitivo pessoal básico, orações relativas."},
            "B2": {"grammar": "Imperfeito e futuro do subjuntivo, colocação pronominal (próclise, mesóclise, ênclise), voz passiva, orações concessivas."},
            "C1": {
                "institution_reference": "DAPLE (Diploma Avançado de Português Língua Estrangeira - C1) / Celpe-Bras Avançado",
                "pedagogical_focus": "Subentendidos e pressuposições, argumentação complexa, registros formal/acadêmico, expressões idiomáticas e provérbios.",
                "grammar": "Infinitivo pessoal composto, correlação modo-temporal complexa no conjuntivo, estruturas estilísticas com inversão, conectores discursivos (todavia, não obstante, por conseguinte, no que tange a, conquanto).",
                "lexicon": "Vocabulário culto e abstrato, expressões idiomáticas avançadas (sutileza, perspicácia, ambivalência, complacência, resiliência, mitigar, vislumbrar)."
            },
            "C2": {"grammar": "DUPLE (C2) - Domínio estilístico pleno, erudição literária e retórica sofisticada."}
        }
    },
    "Russian": {
        "institution": "Государственный институт русского языка им. А.С. Пушкина / ТРКИ (TORFL)",
        "levels": {
            "A1": {"grammar": "Настоящее время, базовые падежи (именительный, предложный, винительный), род и число, порядок слов."},
            "A2": {"grammar": "Прошедшее и будущее время, родительный и дательный падежи, глаголы движения (идти/ехать), вид глагола (введение)."},
            "B1": {"grammar": "Творительный падеж, совершенный/несовершенный вид глагола, причастия и деепричастия (введение), сложноподчиненные предложения."},
            "B2": {"grammar": "Причастные и деепричастные обороты, глаголы движения с приставками, сослагательное наклонение, прямая и косвенная речь."},
            "C1": {
                "institution_reference": "ТРКИ-3 / TORFL-3 (C1 - Профессиональное владение русским языком)",
                "pedagogical_focus": "Подтекст и скрытый смысл (ирония, аллюзии), научный и публицистический стиль, фразеологизмы и метафоры, аргументация.",
                "grammar": "Сложные бессоюзные предложения, стилистическая инверсия, экспрессивные синтаксические конструкции, вводные слова и текстовые скрепы (следовательно, тем не менее, вопреки тому что, в силу того что, коль скоро).",
                "lexicon": "Абстрактная лексика, идиомы и фразеологизмы высокой частоты (нюанс, намёк, упрёк, проницательность, предвзятость, компромисс, двусмысленность, метафоричность)."
            },
            "C2": {"grammar": "ТРКИ-4 / TORFL-4 (C2) - Свободное владение стилями русской художественной литературы и публицистики."}
        }
    },
    "Chinese": {
        "institution": "Center for Language Education and Cooperation (CLEC / Hanban) - HSK 3.0 / CEFR",
        "levels": {
            "A1": {"grammar": "HSK 1: 基本句型 (SVO), '是'字句, '有'字句, 疑问代词 (什么, 谁, 哪儿), 基础量词."},
            "A2": {"grammar": "HSK 2: '了'表示变化/完成, 连动句, 比较句 (比), 趋向补语, 时间状语."},
            "B1": {"grammar": "HSK 3: '把'字句, '被'字句, 结果补语, 状态补语, 关联词 (不仅...而且, 虽然...但是)."},
            "B2": {"grammar": "HSK 4: 复合趋向补语, 复杂复句 (宁可...也不, 即使...也), 书面语连接词 (然而, 从而, 进而)."},
            "C1": {
                "institution_reference": "HSK 5-6 / HSK 3.0 高等 (Level 7-9) / CEFR C1",
                "pedagogical_focus": "成语 (Chengyu 4-character idioms), 弦外之音 (Implicit Meaning / Subtext), 论说文与论辩技巧, 书面语与典故.",
                "grammar": "文言句式在现代汉语中的运用 (非...莫属, 无可厚非, 毋庸置疑), 高级关联结构 (与其说...不如说, 鉴于, 纵使), 复杂紧缩句, 语体转换.",
                "lexicon": "高阶成语与隐喻 (旁敲侧击, 欲盖弥彰, 指桑骂槐, 针锋相对, 意味深长, 委婉, 隐喻, 见微知著, 逻辑严密, 权衡)."
            },
            "C2": {"grammar": "HSK Level 9 / CEFR C2 - 古今汉语融合, 经典文学解析与精湛修辞."}
        }
    },
    "Japanese": {
        "institution": "Japan Foundation (JF Standard for Japanese-Language Education) & JLPT",
        "levels": {
            "A1": {"grammar": "JLPT N5: です/ます, 格助词 (は, が, を, に, で), そ・こ・あ・ど, 存在文 (あります/います)."},
            "A2": {"grammar": "JLPT N4: て形, た形, ない形, 辞書形, 授受動詞 (あげる/もらう/くれる), 比較, 意向形."},
            "B1": {"grammar": "JLPT N3: 受身 (Passive), 使役 (Causative), 敬語 (Sonkeigo/Kenjougo basics), 条件形 (ば, たら, なら), 複文."},
            "B2": {"grammar": "JLPT N2: 使役受身, 高度な敬語, 複合助詞 (〜をはじめ, 〜にわたって, 〜わけにはいかない), 論理的接続詞."},
            "C1": {
                "institution_reference": "JLPT N1 / JF Standard C1 (Advanced Operational Proficiency)",
                "pedagogical_focus": "行間を読む (Reading Between the Lines), 本音と建前 (Nuance & Pragmatics), 論文・論説文の論理構造, 慣用句と四字熟語.",
                "grammar": "高度な文語的表現 (〜極まりない, 〜を余儀なくされる, 〜であれ〜であれ, 〜ずにはおかない), 複文の重層的従属, 高度な待遇表現.",
                "lexicon": "抽象語彙、四字熟語、ニュアンス表現 (含蓄、皮肉、嫌味、阿吽の呼吸、顔を立てる、釘を刺す、示唆、洞察力、妥協、葛藤)."
            },
            "C2": {"grammar": "JF Standard C2 - 古典・近現代文学の精読、格調高い公的演説と修辞."}
        }
    },
    "Arabic": {
        "institution": "AL-Arabiyya Institute & CEFR Framework for Modern Standard Arabic (Fusha)",
        "levels": {
            "A1": {"grammar": "الجملة الاسمية البسيطة, الضمائر المنفصلة, أسماء الإشارة, الإضافة البسيطة, النعت والمنعوت."},
            "A2": {"grammar": "الجملة الفعلية (الماضي والمضارع), حروف الجر, كان وأخواتها (مقدمة), المفعول به, أدوات الاستفهام."},
            "B1": {"grammar": "النواصب والجوازم, أوزان الفعل المزيد (الأوزان العشرة), المبني للمجهول, الحال, الأسماء الموصولة."},
            "B2": {"grammar": "إنّ وأخواتها, التمييز, الاستثناء, الممنوع من الصرف, أسلوب الشرط الجازم وغير الجازم."},
            "C1": {
                "institution_reference": "CEFR C1 for Modern Standard Arabic (المستوى المتقدم الفعال)",
                "pedagogical_focus": "البلاغة (المعاني والبيان والبديع), الكناية والاستعارة, دلالات الألفاظ والسياق الثقافي, لغة المقال والمناظرة.",
                "grammar": "أساليب التوكيد والقصر, المفعول المطلق والمفعول لأجله بدقة أسلوبية, التضمين النحوي, أدوات الربط البلاغية (بيد أنّ, لا جرم, سيّما, ناهيك عن, على رِسْلِك).",
                "lexicon": "ألفاظ مجردة وتراكيب بلاغية (إيحاء, تلميح, تهكم, عتاب, دلالة ضمنية, فراسة, بصيرة, حنكة, مفارقة, مراوغة, إجماع)."
            },
            "C2": {"grammar": "أعلى مستويات الفصاحة البيانية والتراثية والنقد الأدبي التحليلي."}
        }
    },
    "Dutch": {
        "institution": "Nederlandse Taalunie & Certificaat Nederlands als Vreemde Taal (CNaVT)",
        "levels": {
            "A1": {"grammar": "Tegenwoordige tijd, zinsvolgorde (SVO), scheidbare werkwoorden, lidwoorden (de/het), ontkenning (niet/geen)."},
            "A2": {"grammar": "Perfectum (hebben/zijn), imperfectum regelmatige werkwoorden, bijzinnen met 'omdat' en 'dat', er + prepositie."},
            "B1": {"grammar": "Imperfectum onregelmatige werkwoorden, passieve vorm (worden/zijn), relatieve bijzinnen, indirecte rede."},
            "B2": {"grammar": "Complexe passiefconstructies, te + infinitief, conditionele zinnen, signaalwoorden (echter, daarentegen, immers)."},
            "C1": {
                "institution_reference": "CNaVT Educatief Professioneel (C1) / Staatsexamen NT2 II",
                "pedagogical_focus": "Impliciete betekenis, nuance, ironie en sarcasme, academische argumentatie, idiomatische uitdrukkingen.",
                "grammar": "Complexe beknopte bijzinnen, inversie in formele stijl, subtiele modale partikels (immers, trouwens, overigens, weliswaar), formele connectoren (desalniettemin, dientengevolge, mits, voor zover).",
                "lexicon": "Abstract vocabulaire, spreekwoorden en uitdrukkingen (ondertoon, toespeling, verwijt, fijnzinnigheid, terughoudendheid, paradox, pragmatiek)."
            },
            "C2": {"grammar": "CNaVT C2 - Volledige stilistische en academische taalbeheersing."}
        }
    },
    "Swedish": {
        "institution": "Folkuniversitetet / Tisus / Swedex (Svenska som andraspråk)",
        "levels": {
            "A1": {"grammar": "Presens, V2-regeln (omvänd ordföljd), bestämd/obestämd form, personliga pronomen, hjälpverb."},
            "A2": {"grammar": "Preteritum, supinum (perfekt), bisatsordföljd (BIFF-regeln), adjektivböjning, komparation."},
            "B1": {"grammar": "Pluskvamperfekt, passiv med -s, modala hjälpverb, konditionala bisatser, relativa bisatser (som)."},
            "B2": {"grammar": "Participer (presens och perfekt particip), formellt passiv, komplexa sambandsord (dock, emellertid, trots att)."},
            "C1": {
                "institution_reference": "Tisus (Test i svenska för universitets- och högskolestudier - C1) / Swedex C1",
                "pedagogical_focus": "Undertext och implicit mening, ironi, akademisk och professionell textstruktur, nyanser och idiom.",
                "grammar": "Komplexa participfraser, stilistisk inversion, formella textbindare (icke desto mindre, följaktligen, i synnerhet, vad beträffar, låt vara att).",
                "lexicon": "Abstrakt och akademiskt ordförråd (undertext, antydan, förebråelse, fingertoppskänsla, ambivalens, kompromiss, urskillning)."
            },
            "C2": {"grammar": "Närmast modersmålsnivå med litterär och stilistisk finess."}
        }
    },
    "Korean": {
        "institution": "National Institute for International Education (NIIED) - TOPIK / CEFR",
        "levels": {
            "A1": {"grammar": "TOPIK I (1급): 기본 어순 (SOV), 격조사 (이/가, 은/는, 을/를), 이에요/예요, 아요/어요, 시제 (았/었)."},
            "A2": {"grammar": "TOPIK I (2급): 존댓말 (시), 연결어미 (고, 지만, 아서/어서), 불규칙 동사, 능력/불능 (-을 수 있다/없다)."},
            "B1": {"grammar": "TOPIK II (3급): 사동/피동 기초, 간접화법 (-다고 하다), 추측/의도 (-을 것 같다, -으려고 하다), 조건/가정 (-으면)."},
            "B2": {"grammar": "TOPIK II (4급): 복합 연결어미 (-는데도, -을 뿐만 아니라, -을 텐데), 고급 피동/사동, 관용구 기초, 논설문 기초."},
            "C1": {
                "institution_reference": "TOPIK II (5-6급) / CEFR C1",
                "pedagogical_focus": "행간의 의미 (Implicit Meaning / Subtext), 뉘앙스와 수사법 (Nuance & Rhetoric), 사자성어 (Sajaseong-eo 4-character idioms), 학술 및 공적 담화.",
                "grammar": "고급 문어체 표현 (-기 짝이 없다, -을 지경이다, -을 리 만무하다, -기에 망정이지), 격식적 연결표현 (그럼에도 불구하고, 미루어 보건대, 에 비추어), 고차원 피동.",
                "lexicon": "고급 사자성어와 추상 어휘 (일침을 가하다, 완곡한 표현, 속내, 눈치를 보다, 비아냥, 복선, 통찰력, 괴리감, 딜레마)."
            },
            "C2": {"grammar": "TOPIK 6급 심화 / CEFR C2 - 고전문학 해독 및 최고 수준의 학술적/외교적 어휘 구사."}
        }
    },
    "Greek": {
        "institution": "Centre for the Greek Language (Κέντρο Ελληνικής Γλώσσας - Πιστοποίηση Ελληνομάθειας)",
        "levels": {
            "A1": {"grammar": "Ενεστώτας (Ομάδα Α/Β), οριστικό/αόριστο άρθρο, κλίση ουσιαστικών (πτώσεις), προσωπικές αντωνυμίες."},
            "A2": {"grammar": "Παρατατικός, Αόριστος (ενεργητική φωνή), μέλλοντας εξακολουθητικός/στιγμιαίος, αιτιατική πτώση."},
            "B1": {"grammar": "Παθητική φωνή (Ενεστώτας, Αόριστος), υποτακτική, υποθετικοί λόγοι (1ο/2ο είδος), αναφορικές προτάσεις."},
            "B2": {"grammar": "Παρακείμενος, Υπερσυντέλικος, μετοχές παθητικού παρακειμένου (-μένος), πλάγιος λόγος, σύνδεσμοι (παρόλο που, επομένως)."},
            "C1": {
                "institution_reference": "Πιστοποίηση Ελληνομάθειας - Επίπεδο Γ1 (Advanced / C1)",
                "pedagogical_focus": "Υπονοούμενα (Implicit Meaning), ειρωνεία, ρητορικά σχήματα, επίσημο/ακαδημαϊκό ύφος, λόγιες εκφράσεις και ιδιωματισμοί.",
                "grammar": "Λόγιες συντάξεις και απαρέμφατα, μετοχές λογίας προέλευσης (όντας, διανύων), υποθετικοί λόγοι του απραγματοποίητου, διαρθρωτικοί δείκτες (εντούτοις, μολαταύτα, ως εκ τούτου, ενόψει του ότι).",
                "lexicon": "Λόγιο και αφηρημένο λεξιλόγιο, ιδιωματισμοί (υπαινιγμός, ειρωνεία, επίπληξη, οξυδέρκεια, διφορούμενο, συμβιβασμός, διορατικότητα, επίμετρο)."
            },
            "C2": {"grammar": "Επίπεδο Γ2 - Πλήρης αριστοτεχνική γνώση της λόγιας και λογοτεχνικής γλώσσας."}
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
                "grammar": "Inversion with negative adverbials (Seldom have I seen...), cleft sentences, participle clauses, subtle modal hedging, formal discourse markers (notwithstanding, henceforth, whereas, albeit).",
                "lexicon": "Collocations with narrow semantic range, abstract nouns, academic vocabulary, idiomatic mastery (subtlety, reproach, allusion, double entendre, veiled threat, perspicacity, ambiguity)."
            },
            "C2": {"grammar": "Cambridge C2 Proficiency (CPE) - Stylistic elegance, rhetorical precision, idiomatic and dialectal mastery."}
        }
    }
}

# ── 3. STRICT FORBIDDEN ELEMENTARY WORDS MATRIX (FOR B2/C1/C2) ────────
# Contains beginner-tier baseline words that MUST NEVER appear in advanced lessons
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
        "madre", "padre", "hermano", "amigo", "mesa", "silla", "puerta", "comer", "beber", "ir"
    ],
    "german": [
        "hallo", "guten tag", "guten morgen", "gute nacht", "danke", "bitte", "tschüss", "auf wiedersehen",
        "kaffee", "wasser", "brot", "apfel", "haus", "auto", "hund", "katze", "schule", "buch",
        "mutter", "vater", "bruder", "tisch", "stuhl", "essen", "trinken", "gehen", "kommen"
    ],
    "french": [
        "bonjour", "salut", "au revoir", "merci", "s'il vous plaît", "bonne nuit", "bonsoir",
        "café", "eau", "pain", "pomme", "maison", "voiture", "chien", "chat", "école", "livre",
        "mère", "père", "frère", "table", "chaise", "manger", "boire", "aller", "venir"
    ],
    "italian": [
        "ciao", "buongiorno", "buonasera", "buonanotte", "arrivederci", "grazie", "per favore",
        "caffè", "acqua", "pane", "mela", "casa", "macchina", "cane", "gatto", "scuola", "libro",
        "madre", "padre", "fratello", "tavolo", "sedia", "mangiare", "bere", "andare", "venire"
    ],
    "portuguese": [
        "olá", "oi", "adeus", "tchau", "obrigado", "obrigada", "por favor", "bom dia", "boa tarde", "boa noite",
        "café", "água", "pão", "maçã", "casa", "carro", "cão", "cachorro", "gato", "escola", "livro",
        "mãe", "pai", "irmão", "mesa", "cadeira", "comer", "beber", "ir", "vir"
    ],
    "russian": [
        "привет", "здравствуйте", "до свидания", "пока", "спасибо", "пожалуйста", "доброе утро", "добрый день",
        "кофе", "вода", "хлеб", "яблоко", "дом", "машина", "собака", "кот", "кошка", "школа", "книга",
        "мама", "папа", "брат", "стол", "стул", "есть", "пить", "идти", "ходить"
    ],
    "chinese": [
        "你好", "您好", "再见", "谢谢", "不客气", "请", "早上好", "晚安",
        "咖啡", "水", "茶", "苹果", "面包", "家", "车", "狗", "猫", "学校", "书",
        "爸爸", "妈妈", "哥哥", "弟弟", "桌子", "椅子", "吃", "喝", "去", "来"
    ],
    "japanese": [
        "こんにちは", "おはよう", "こんばんは", "さようなら", "ありがとう", "どういたしまして", "お願いします",
        "コーヒー", "水", "お茶", "パン", "りんご", "家", "車", "犬", "猫", "学校", "本",
        "お父さん", "お母さん", "兄", "机", "椅子", "食べる", "飲む", "行く", "来る"
    ],
    "arabic": [
        "مرحبا", "أهلا", "مع السلامة", "شكرا", "عفوا", "من فضلك", "صباح الخير", "مساء الخير",
        "قهوة", "ماء", "شاي", "خبز", "تفاحة", "بيت", "سيارة", "كلب", "قطة", "مدرسة", "كتاب",
        "أب", "أم", "أخ", "طاولة", "كرسي", "أكل", "شرب", "ذهب", "جاء"
    ],
    "dutch": [
        "hallo", "hoi", "dag", "tot ziens", "bedankt", "dank je", "alsjeblieft", "goedemorgen", "goedenavond",
        "koffie", "water", "thee", "brood", "appel", "huis", "auto", "hond", "kat", "school", "boek",
        "moeder", "vader", "broer", "tafel", "stoel", "eten", "drinken", "gaan", "komen"
    ],
    "swedish": [
        "hej", "hejdå", "tack", "snälla", "god morgon", "god kväll", "god natt",
        "kaffe", "vatten", "te", "bröd", "äpple", "hus", "bil", "hund", "katt", "skola", "bok",
        "mamma", "pappa", "bror", "bord", "stol", "äta", "dricka", "gå", "komma"
    ],
    "korean": [
        "안녕하세요", "안녕", "안녕히 가세요", "감사합니다", "고맙습니다", "부탁합니다", "좋은 아침",
        "커피", "물", "차", "빵", "사과", "집", "차", "개", "고양이", "학교", "책",
        "어머니", "아버지", "형", "탁자", "의자", "먹다", "마시다", "가다", "오다"
    ],
    "greek": [
        "γεια", "γεια σας", "αντίο", "ευχαριστώ", "παρακαλώ", "καλημέρα", "καλησπέρα", "καληνύχτα",
        "καφές", "νερό", "τσάι", "ψωμί", "μήλο", "σπίτι", "αυτοκίνητο", "σκύλος", "γάτα", "σχολείο", "βιβλίο",
        "μητέρα", "πατέρας", "αδελφός", "τραπέζι", "καρέκλα", "τρώω", "πίνω", "πηγαίνω", "έρχομαι"
    ],
    "english": [
        "hello", "hi", "goodbye", "bye", "good morning", "good evening", "thank you", "thanks", "please",
        "coffee", "water", "tea", "bread", "apple", "house", "car", "dog", "cat", "school", "book",
        "mother", "father", "brother", "table", "chair", "eat", "drink", "go", "come"
    ]
}

# Curated C1 reference items for prominent topics across languages
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


# ── 4. CEFR CONDITIONING ENGINE ──────────────────────────────────────
def get_cefr_conditioning(language: str, level: str, topic: str = "", topic_type: str = "vocabulary") -> str:
    """
    Constructs an inescapable, authoritative CEFR prompt conditioning instruction.
    Injects Council of Europe and national framework standards into the LLM system prompt for ANY language.
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
    institution = lang_standards.get("institution", f"Council of Europe CEFR Companion Volume ({language})")

    # Build Negative Constraints (Forbidden Lexicon & Level Difficulty Calibration)
    forbidden_summary = ""
    is_advanced = lvl_key in ["B2", "C1", "C2"]
    if is_advanced:
        lang_key = language.lower()
        forbidden_list = UNIVERSAL_ELEMENTARY_WORDS.get(lang_key, UNIVERSAL_ELEMENTARY_WORDS.get("english", []))
        forbidden_sample = ", ".join(forbidden_list[:30])
        forbidden_summary = f"""
CRITICAL NEGATIVE CONSTRAINT (STRICT ZERO-TOLERANCE BAN):
- YOU ARE AUTHORING MATERIAL FOR {lvl_key} ({universal_spec['name']}).
- IT IS A CRITICAL DEFECT TO INCLUDE ELEMENTARY, BEGINNER-TIER WORDS, TOURIST CLICHES, OR ROUTINE GREETINGS.
- SPECIFICALLY BANNED FOR THIS {lvl_key} LESSON IN {language.upper()} (DO NOT GENERATE ANY OF THESE OR SIMILAR BASICS):
  [{forbidden_sample}]
- NEVER treat a {lvl_key} topic like an introductory cultural trivia lesson. Adult {lvl_key} learners have already mastered basic vocabulary years ago.
- EVERY vocabulary term MUST be an advanced, academic, literary, polysemous, or idiomatic lexical item appropriate for university-level discourse.
"""
    elif lvl_key == "B1":
        forbidden_summary = f"""
CRITICAL CEFR B1 DIFFICULTY & REGISTER CALIBRATION (STRICT STANDARD EVERYDAY LANGUAGE):
- YOU ARE AUTHORING MATERIAL FOR B1 ({universal_spec['name']}).
- B1 REPRESENTS INDEPENDENT EVERYDAY THRESHOLD MASTERY (Alltagssprache / clear standard language).
- STRICT BAN ON C1/B2 HYPER-TECHNICAL BUREAUCRATIC OVERLOAD:
  * Do NOT use heavy administrative officialese, hyper-technical engineering/infrastructure jargon, or dense legalistic compound nouns.
  * For example, in transit/services, avoid overloading the test with specialized dispatch terminology or obscure tariff rules. Use clear standard everyday expressions (e.g. general technical problem, boarding assistance, schedule delay, polite staff inquiry).
  * A learner at B1 needs to communicate, ask for help, understand standard public announcements, and solve practical travel/daily situations, NOT act as a legal dispatcher or transport authority lawyer!
"""
    elif lvl_key in ["A1", "A2"]:
        forbidden_summary = f"""
CRITICAL CEFR {lvl_key} DIFFICULTY & LEARNER ERROR MODELING:
- YOU ARE AUTHORING MATERIAL FOR {lvl_key} ({universal_spec['name']}).
- USE SHORT, CLEAR, CONCRETE SCENARIOS grounded in immediate everyday life.
- FOR NUMBERS & VOCABULARY: Distractors must NOT merely be adjacent numbers. They must model authentic learner error patterns (e.g. compounding errors, apocope/gender agreement, false friends).
- EVERYDAY SPOKEN REALISM: In time and daily expressions, use natural spoken terms (e.g. 'medianoche' / 'las doce de la noche', NEVER artificial 'las cero horas').
"""

    specific_rules = ""
    if lang_level_spec:
        inst_ref = lang_level_spec.get("institution_reference", institution)
        ped_focus = lang_level_spec.get("pedagogical_focus", "")
        grammar_points = lang_level_spec.get("grammar", "")
        lexicon_points = lang_level_spec.get("lexicon", "")
        ped_part = f"- PEDAGOGICAL DOMAIN: {ped_focus}\n" if ped_focus else ""
        lex_part = f"- TARGET LEXICAL EXPECTATIONS FOR {lvl_key}:\n{lexicon_points}\n" if lexicon_points else ""
        specific_rules = f"""
AUTHORITATIVE CURRICULUM REFERENCE ({institution}):
- REFERENCE FRAMEWORK: {inst_ref}
{ped_part}- TARGET GRAMMATICAL STRUCTURES FOR {lvl_key}:
{grammar_points}
{lex_part}"""

    conditioning = f"""
================================================================================
CEFR PROFICIENCY DIRECTIVE: STRICT LEVEL {lvl_key} ({universal_spec['name']}) - {language.upper()}
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


# ── 5. CEFR VALIDATOR & LEVEL SANITIZER ──────────────────────────────
def validate_cefr_level(term: str, language: str, level: str) -> bool:
    """
    Validates whether a generated vocabulary item complies with the target CEFR level.
    Returns True if valid, False if it violates level constraints (e.g. A1 word in C1).
    Works across ALL 15 platform languages.
    """
    if not term:
        return False
    clean_term = term.strip().lower()
    clean_lvl = (level or "A1").upper().strip()

    # If level is B2, C1, or C2, check against forbidden elementary list
    if any(k in clean_lvl for k in ["B2", "C1", "C2"]):
        lang_key = language.lower()
        forbidden = set(UNIVERSAL_ELEMENTARY_WORDS.get(lang_key, UNIVERSAL_ELEMENTARY_WORDS.get("english", [])))
        if clean_term in forbidden:
            return False
        # Check sub-words for single elementary words
        term_words = [w.strip() for w in re.split(r'\s+', clean_term) if len(w.strip()) > 1]
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
