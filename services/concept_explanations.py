"""
Pedagogical Concept Explanations Dictionary & Resolver.
Provides rich, brief, CEFR-aligned explanations for linguistic, phonetic,
and grammatical concepts in both English and Turkish.
"""

import re
import unicodedata

def _normalize(text: str) -> str:
    if not text:
        return ""
    # Lowercase & trim
    t = text.lower().strip()
    # Strip common articles / markers
    for prefix in ["der ", "die ", "das ", "el ", "la ", "los ", "las ", "the ", "a ", "an ", "ein ", "eine ", "un ", "una "]:
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    # Remove accents for relaxed matching
    nfkd = unicodedata.normalize('NFKD', t)
    t_clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Remove non-alphanumeric except spaces
    t_clean = re.sub(r'[^a-z0-9\s]', '', t_clean).strip()
    return t_clean

# Master dictionary: maps normalized concept keys to { "en": "...", "tr": "..." }
CONCEPT_EXPLANATIONS = {
    # ── PHONETICS & PRONUNCIATION ──
    "vowel": {
        "en": "A core speech sound produced with an open vocal tract without air obstruction (A, E, I, O, U).",
        "tr": "Ses yolunda bir engelle karşılaşmadan serbestçe çıkan temel sesler (A, E, I, İ, O, Ö, U, Ü)."
    },
    "consonant": {
        "en": "A speech sound formed by obstructing or restricting airflow with lips, tongue, or teeth.",
        "tr": "Dudak, dil veya dişlerin hava akımını kısmen veya tamamen engellemesiyle oluşan sesler."
    },
    "umlaut": {
        "en": "A vowel sound modification marked by two dots (ä, ö, ü) that alters pronunciation.",
        "tr": "Almancada ses değişimini gösteren iki noktalı özel harfler (ä, ö, ü)."
    },
    "sound": {
        "en": "An individual spoken phonetic unit or letter pronunciation value.",
        "tr": "Bir dildeki her bir işitilebilir ses veya fonetik konuşma birimi."
    },
    "syllable": {
        "en": "A unit of spoken pronunciation formed by a single vowel sound, with or without consonants.",
        "tr": "Ağzın tek bir nefes ve ses hamlesiyle çıkardığı ses veya ses öbeği."
    },
    "word": {
        "en": "A single distinct, meaningful linguistic element used to form phrases and sentences.",
        "tr": "Cümle kurmaya yarayan bağımsız ve anlamlı temel dil birimi."
    },
    "letter": {
        "en": "A written character or symbol representing one or more speech sounds in an alphabet.",
        "tr": "Dildeki bir sesi gösteren ve alfabeyi oluşturan yazılı işaret."
    },
    "alphabet": {
        "en": "The complete standardized set of letters representing the sounds of a language.",
        "tr": "Bir dildeki sesleri gösteren, belli bir sıraya göre dizilmiş harflerin tamamı."
    },
    "sentence": {
        "en": "A grammatically complete set of words expressing a statement, question, or thought.",
        "tr": "Bir duyguyu, düşünceyi veya durumu bildiren sözcük dizisi."
    },
    "language": {
        "en": "A structured system of communication used by a community to express thoughts and ideas.",
        "tr": "İnsanların duygu ve düşüncelerini aktarmak için kullandığı kurallı iletişim sistemi."
    },
    "accent": {
        "en": "The vocal emphasis or pitch placed on a specific syllable within a word.",
        "tr": "Bir kelimede belirli bir hecenin diğerlerine göre daha baskılı ve belirgin söylenmesi."
    },
    "stress": {
        "en": "The prominent acoustic emphasis given to a syllable in spoken words.",
        "tr": "Konuşurken bir heceye verilen belirgin ses vurgusu."
    },
    "intonation": {
        "en": "The melodic rise and fall of vocal pitch across phrases and sentences.",
        "tr": "Konuşurken ses perdesinin cümlenin anlamına göre alçalıp yükselmesi."
    },
    "pronunciation": {
        "en": "The conventional articulation and audible speech production of words and sounds.",
        "tr": "Bir dildeki ses ve kelimelerin ağızdan doğru ve anlaşılır biçimde sesletimi."
    },
    "diphthong": {
        "en": "Two adjacent vowel sounds gliding together within the same syllable (e.g., ei, au, eu).",
        "tr": "Tek bir hecede kesintisiz bir kaymayla birleşen iki sesli harf (ör. ei, au, eu)."
    },
    "hiatus": {
        "en": "Two consecutive vowel sounds pronounced in separate, distinct syllables.",
        "tr": "Yan yana gelen iki sesli harfin iki ayrı hecede bölünerek okunması."
    },
    "silent": {
        "en": "A letter written in spelling but omitted from verbal pronunciation.",
        "tr": "Yazıda yer alan fakat telaffuz edilirken sesletilmeyen harf."
    },
    "weak vowel": {
        "en": "In Spanish, the closed vowels (I, U) that readily combine into diphthongs.",
        "tr": "İspanyolcada diftong oluşturan dar sesli harfler (I, U)."
    },
    "strong vowel": {
        "en": "In Spanish, open vowels (A, E, O) that form independent, separated syllables.",
        "tr": "İspanyolcada bağımsız hece oluşturan açık sesli harfler (A, E, O)."
    },
    "accentuation": {
        "en": "The rules governing where vocal stress and written accent marks fall in words.",
        "tr": "Kelimelerdeki vurgu ve aksan işaretlerinin yerini belirleyen kurallar bütünü."
    },
    "rhythm": {
        "en": "The beat, cadence, and timing pattern of spoken syllables in a language.",
        "tr": "Konuşmadaki hecelerin ve vurguların oluşturduğu ahenkli ritim."
    },

    # ── GRAMMAR & PARTS OF SPEECH ──
    "noun": {
        "en": "A word identifying a person, place, physical object, or abstract concept.",
        "tr": "Canlı veya cansız varlıkları, nesneleri ve kavramları adlandıran sözcük türü."
    },
    "verb": {
        "en": "A word expressing an action, event, occurrence, or state of being.",
        "tr": "Bir işi, oluşu, hareketi veya durumu zaman ve kişiye bağlayarak bildiren sözcük."
    },
    "adjective": {
        "en": "A word describing or qualifying the qualities, state, or traits of a noun.",
        "tr": "İsimlerin niteliklerini, durumlarını veya özelliklerini belirten sözcük."
    },
    "adverb": {
        "en": "A word modifying a verb, adjective, or phrase (describing manner, time, or place).",
        "tr": "Fiilleri, sıfatları veya diğer zarfları durum, zaman veya miktar yönünden niteleyen sözcük."
    },
    "pronoun": {
        "en": "A word that substitutes for a noun or noun phrase (e.g., I, you, he, she, they).",
        "tr": "İsmin yerini tutan ve onun yerine kullanılan sözcük (ben, sen, o, biz, siz, onlar)."
    },
    "article": {
        "en": "A grammatical marker accompanying a noun to signal definiteness or grammatical gender.",
        "tr": "İsmin önüne gelerek onun belirli mi yoksa belirsiz mi olduğunu gösteren dilbilgisi birimi."
    },
    "definite article": {
        "en": "Specifies a particular, identifiable person or object (e.g., 'the', German 'der/die/das').",
        "tr": "Bilinen veya belirli bir varlığı niteleyen tanımlık (Almanca 'der/die/das', İspanyolca 'el/la')."
    },
    "indefinite article": {
        "en": "Refers to a non-specific or newly introduced person or object (e.g., 'a/an', 'ein/eine').",
        "tr": "Herhangi bir varlığı genel olarak niteleyen tanımlık (Almanca 'ein/eine', İspanyolca 'un/una')."
    },
    "preposition": {
        "en": "A word showing spatial, directional, temporal, or logical relationships (in, on, at).",
        "tr": "Kelimeler arasında yön, yer, zaman veya ilgi ilişkisi kuran ilgeç."
    },
    "conjunction": {
        "en": "A connecting word linking phrases, clauses, or coordinating elements (and, but, because).",
        "tr": "Kelimeleri veya cümleleri birbirine bağlayan sözcük (ve, ama, çünkü)."
    },
    "gender": {
        "en": "Grammatical categorization of nouns into classes such as masculine, feminine, or neuter.",
        "tr": "Pek çok dilde isimlerin eril, dişil veya nötr olarak sınıflandırılması."
    },
    "masculine": {
        "en": "Grammatical gender category marked with masculine articles (e.g., German 'der', Spanish 'el').",
        "tr": "Eril cinsiyetteki isimler (Almanca 'der', İspanyolca 'el' artikeliyle kullanılır)."
    },
    "feminine": {
        "en": "Grammatical gender category marked with feminine articles (e.g., German 'die', Spanish 'la').",
        "tr": "Dişil cinsiyetteki isimler (Almanca 'die', İspanyolca 'la' artikeliyle kullanılır)."
    },
    "neuter": {
        "en": "Grammatical gender category that is neither masculine nor feminine (e.g., German 'das').",
        "tr": "Ne eril ne de dişil olan cinsiyet kategorisi (Almanca 'das' artikeliyle kullanılır)."
    },
    "singular": {
        "en": "Grammatical form designating a single person, item, or concept.",
        "tr": "Sadece tek bir varlığı veya kişiyi belirten sözcük biçimi."
    },
    "plural": {
        "en": "Grammatical form designating more than one person, item, or concept.",
        "tr": "Birden fazla varlığı veya kişiyi belirten sözcük biçimi."
    },
    "subject": {
        "en": "The actor, person, or entity performing the verb or being described in a sentence.",
        "tr": "Cümlede bildirilen işi yapan veya hakkında bilgi verilen temel öge."
    },
    "object": {
        "en": "The person, item, or entity affected by or receiving the action of a verb.",
        "tr": "Cümlede öznenin yaptığı işten etkilenen varlık veya öge."
    },
    "infinitive": {
        "en": "The base, uninflected dictionary form of a verb before conjugation.",
        "tr": "Fiilin kişi ve zaman eki almamış yalın sözlük hali (mastar)."
    },
    "conjugation": {
        "en": "The inflection and ending changes of a verb corresponding to person, number, and tense.",
        "tr": "Fiilin kişi, zaman ve kipe göre ek alarak değişmesi (fiil çekimi)."
    },
    "regular verb": {
        "en": "A verb that adheres strictly to standard, predictable conjugation patterns.",
        "tr": "Standart kurallara ve kalıplara uygun olarak çekimlenen düzenli fiil."
    },
    "irregular verb": {
        "en": "A verb with idiosyncratic stem changes or non-standard conjugation endings.",
        "tr": "Çekimlenirken kökü veya ekleri standart kuralların dışına çıkan düzensiz fiil."
    },
    "reflexive verb": {
        "en": "A verb where the subject and the direct object are the same entity (acting on oneself).",
        "tr": "Öznenin yaptığı işin yine özneye döndüğü dönüşlü fiil."
    },
    "modal verb": {
        "en": "An auxiliary verb indicating permission, ability, obligation, or necessity.",
        "tr": "Zorunluluk, izin, yetenek veya olasılık bildiren kip yardımcı fiili."
    },
    "cognate": {
        "en": "A word sharing common ancestral origin, meaning, and spelling across languages.",
        "tr": "Farklı dillerde ortak kökenden gelen, yazılışı ve anlamı birbirine çok benzeyen sözcük."
    },
    "false friend": {
        "en": "A deceptive word that looks or sounds like a familiar word but carries a different meaning.",
        "tr": "Yazılışı veya okunuşu tanıdık gelen ancak tamamen farklı anlama sahip yanıltıcı sözcük."
    }
}

# Aliases for cross-language resolution
ALIASES = {
    # German
    "vokal": "vowel", "vokale": "vowel",
    "konsonant": "consonant", "konsonanten": "consonant",
    "laut": "sound", "laute": "sound",
    "silbe": "syllable", "silben": "syllable",
    "wort": "word", "worter": "word",
    "buchstabe": "letter", "buchstaben": "letter",
    "satz": "sentence", "satze": "sentence",
    "sprache": "language", "sprachen": "language",
    "akzent": "accent",
    "betonung": "stress",
    "aussprache": "pronunciation",
    "substantiv": "noun", "nomen": "noun",
    "adjektiv": "adjective",
    "praposition": "preposition",
    "pronomen": "pronoun",
    "genus": "gender",
    "maskulin": "masculine", "feminin": "feminine", "neutrum": "neuter",
    "kognat": "cognate",
    "falscher freund": "false friend",
    "stumm": "silent",

    # Spanish
    "vocal": "vowel", "vocales": "vowel",
    "consonante": "consonant", "consonantes": "consonant",
    "silaba": "syllable", "silabas": "syllable",
    "sonido": "sound", "sonidos": "sound",
    "palabra": "word", "palabras": "word",
    "letra": "letter", "letras": "letter",
    "abecedario": "alphabet",
    "acento": "accent", "acentos": "accent",
    "tonica": "stress",
    "diptongo": "diphthong",
    "hiato": "hiatus",
    "silencio": "silent", "silencioso": "silent", "mudo": "silent",
    "entonacion": "intonation",
    "pronunciacion": "pronunciation",
    "acentuacion": "accentuation",
    "vocal debil": "weak vowel", "debil": "weak vowel",
    "vocal fuerte": "strong vowel", "fuerte": "strong vowel",
    "sustantivo": "noun", "verbo": "verb", "adjetivo": "adjective",
    "adverbio": "adverb", "pronombre": "pronoun", "articulo": "article",
    "preposicion": "preposition", "genero": "gender",
    "cognado": "cognate", "falso amigo": "false friend",

    # Turkish
    "sesli harf": "vowel", "unlu": "vowel", "unluler": "vowel",
    "sessiz harf": "consonant", "unsuz": "consonant", "unsuzler": "consonant",
    "iki noktali unlu": "umlaut",
    "ses": "sound", "fonetik ses": "sound",
    "hece": "syllable", "heceler": "syllable",
    "kelime": "word", "sozcuk": "word",
    "harf": "letter", "harfler": "letter",
    "alfabe": "alphabet",
    "cumle": "sentence",
    "dil": "language",
    "vurgu": "accent", "aksan": "accent",
    "diftong": "diphthong", "cift unlu": "diphthong",
    "hiat": "hiatus", "ayri unluler": "hiatus",
    "okunmayan harf": "silent",
    "tonlama": "intonation", "ezgi": "intonation",
    "telaffuz": "pronunciation", "sesletim": "pronunciation",
    "isim": "noun", "ad": "noun", "fiil": "verb", "eylem": "verb",
    "sifat": "adjective", "zarf": "adverb", "zamir": "pronoun",
    "tanimlik": "article", "artikel": "article", "edat": "preposition",
    "cinsiyet": "gender", "eril": "masculine", "disil": "feminine", "notr": "neuter",
    "ortak kokenli": "cognate", "yaniltici benzer": "false friend"
}

def resolve_concept_key(text: str) -> str:
    """Finds matching canonical concept key for a term or translation string."""
    if not text or not isinstance(text, str):
        return ""
    norm = _normalize(text)
    if not norm:
        return ""
    if norm in CONCEPT_EXPLANATIONS:
        return norm
    if norm in ALIASES:
        return ALIASES[norm]
    # Check word combinations
    words = norm.split()
    for w in words:
        if w in CONCEPT_EXPLANATIONS:
            return w
        if w in ALIASES:
            return ALIASES[w]
    return ""

def get_concept_explanation(term: str = "", translation: str = "", lang: str = "en") -> str:
    """
    Returns a brief, CEFR-aligned explanation for a concept term or translation.
    Returns empty string if the item is not a recognized grammatical/phonetic concept.
    """
    key = resolve_concept_key(term) or resolve_concept_key(translation)
    if not key or key not in CONCEPT_EXPLANATIONS:
        return ""
    expl_dict = CONCEPT_EXPLANATIONS[key]
    target_lang = "tr" if lang == "tr" else "en"
    return expl_dict.get(target_lang, expl_dict.get("en", ""))
