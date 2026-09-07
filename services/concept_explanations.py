"""
Pedagogical Concept Explanations Dictionary & Resolver.
Provides rich, brief, CEFR-aligned explanations for linguistic, phonetic,
and grammatical concepts in both English and Turkish.
Includes automatic semantic conflict detection and self-healing across languages.
"""

import re
import unicodedata

def _normalize(text: str) -> str:
    if not text:
        return ""
    # Lowercase & trim
    t = text.lower().strip()
    # Strip common articles / markers
    for prefix in ["der ", "die ", "das ", "el ", "la ", "los ", "las ", "the ", "a ", "an ", "ein ", "eine ", "un ", "una ", "le ", "les ", "il ", "lo ", "gli "]:
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    # Remove accents for relaxed matching
    nfkd = unicodedata.normalize('NFKD', t)
    t_clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Remove non-alphanumeric except spaces
    t_clean = re.sub(r'[^a-z0-9\s]', '', t_clean).strip()
    return t_clean

# Canonical display names for concepts in each target language
CANONICAL_CONCEPT_NAMES = {
    "vowel": { "en": "Vowel", "tr": "Ünlü" },
    "consonant": { "en": "Consonant", "tr": "Ünsüz" },
    "umlaut": { "en": "Umlaut", "tr": "İki Noktalı Ünlü (Umlaut)" },
    "sound": { "en": "Sound", "tr": "Ses" },
    "syllable": { "en": "Syllable", "tr": "Hece" },
    "word": { "en": "Word", "tr": "Kelime" },
    "letter": { "en": "Letter", "tr": "Harf" },
    "alphabet": { "en": "Alphabet", "tr": "Alfabe" },
    "sentence": { "en": "Sentence", "tr": "Cümle" },
    "language": { "en": "Language", "tr": "Dil" },
    "accent": { "en": "Accent", "tr": "Vurgu" },
    "stress": { "en": "Stress", "tr": "Vurgu" },
    "intonation": { "en": "Intonation", "tr": "Tonlama" },
    "pronunciation": { "en": "Pronunciation", "tr": "Telaffuz" },
    "diphthong": { "en": "Diphthong", "tr": "Diftong (Çift Ünlü)" },
    "hiatus": { "en": "Hiatus", "tr": "Hiyat (Ayrı Ünlüler)" },
    "silent": { "en": "Silent Letter", "tr": "Okunmayan Harf" },
    "weak vowel": { "en": "Weak Vowel", "tr": "Dar Ünlü" },
    "strong vowel": { "en": "Strong Vowel", "tr": "Açık Ünlü" },
    "accentuation": { "en": "Accentuation", "tr": "Aksan Kuralları" },
    "rhythm": { "en": "Rhythm", "tr": "Ritim" },
    "noun": { "en": "Noun", "tr": "İsim" },
    "verb": { "en": "Verb", "tr": "Fiil" },
    "adjective": { "en": "Adjective", "tr": "Sıfat" },
    "adverb": { "en": "Adverb", "tr": "Zarf" },
    "pronoun": { "en": "Pronoun", "tr": "Zamir" },
    "article": { "en": "Article", "tr": "Tanımlık (Artikel)" },
    "definite article": { "en": "Definite Article", "tr": "Belirli Tanımlık" },
    "indefinite article": { "en": "Indefinite Article", "tr": "Belirsiz Tanımlık" },
    "preposition": { "en": "Preposition", "tr": "Edat" },
    "conjunction": { "en": "Conjunction", "tr": "Bağlaç" },
    "gender": { "en": "Gender", "tr": "Dilbilgisel Cinsiyet" },
    "masculine": { "en": "Masculine", "tr": "Eril" },
    "feminine": { "en": "Feminine", "tr": "Dişil" },
    "neuter": { "en": "Neuter", "tr": "Nötr" },
    "singular": { "en": "Singular", "tr": "Tekil" },
    "plural": { "en": "Plural", "tr": "Çoğul" },
    "subject": { "en": "Subject", "tr": "Özne" },
    "object": { "en": "Object", "tr": "Nesne" },
    "infinitive": { "en": "Infinitive", "tr": "Mastar" },
    "conjugation": { "en": "Conjugation", "tr": "Fiil Çekimi" },
    "regular verb": { "en": "Regular Verb", "tr": "Düzenli Fiil" },
    "irregular verb": { "en": "Irregular Verb", "tr": "Düzensiz Fiil" },
    "reflexive verb": { "en": "Reflexive Verb", "tr": "Dönüşlü Fiil" },
    "modal verb": { "en": "Modal Verb", "tr": "Modal Yardımcı Fiil" },
    "cognate": { "en": "Cognate", "tr": "Ortak Kökenli Sözcük" },
    "false friend": { "en": "False Friend", "tr": "Yanıltıcı Benzer" },
    "case": { "en": "Grammatical Case", "tr": "İsmin Hali" },
    "nominative": { "en": "Nominative Case", "tr": "Yalın Hal" },
    "accusative": { "en": "Accusative Case", "tr": "Belirtme Hali (-i)" },
    "dative": { "en": "Dative Case", "tr": "Yönelme Hali (-e)" },
    "genitive": { "en": "Genitive Case", "tr": "İlgi / Tamlayan Hali (-in)" },
    "tense": { "en": "Tense", "tr": "Zaman" },
    "present tense": { "en": "Present Tense", "tr": "Geniş / Şimdiki Zaman" },
    "past tense": { "en": "Past Tense", "tr": "Geçmiş Zaman" },
    "future tense": { "en": "Future Tense", "tr": "Gelecek Zaman" },
    "imperative": { "en": "Imperative", "tr": "Emir Kipi" },
    "subjunctive": { "en": "Subjunctive", "tr": "Dilek / İstek Kipi" },
    "synonym": { "en": "Synonym", "tr": "Eş Anlamlı" },
    "antonym": { "en": "Antonym", "tr": "Zıt Anlamlı" }
}

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
    },

    # ── CASES & TENSES ──
    "case": {
        "en": "A grammatical category determining the grammatical role of a noun in a sentence.",
        "tr": "İsmin cümlede üstlendiği dilbilgisel görevi belirleyen çekim hali."
    },
    "nominative": {
        "en": "The base grammatical case identifying the subject of a sentence.",
        "tr": "Cümlenin öznesi olan ismin ek almamış yalın hali."
    },
    "accusative": {
        "en": "The case marking the direct object directly receiving the action of a transitive verb.",
        "tr": "Geçişli fiilin doğrudan etkilediği nesneyi belirten -i hali."
    },
    "dative": {
        "en": "The case marking the indirect recipient, beneficiary, or directional target of an action.",
        "tr": "Eylemin yöneldiği veya yararlandığı dolaylı tümleci belirten -e hali."
    },
    "genitive": {
        "en": "The case expressing possession, belonging, origin, or close relationship between nouns.",
        "tr": "Aitlik, iyelik veya tamlama ilişkisi bildiren ilgi / tamlayan hali (-in)."
    },
    "tense": {
        "en": "The grammatical inflection of a verb showing the time of an action relative to speaking.",
        "tr": "Eylemin gerçekleştiği zaman dilimini belirten fiil çekim kategorisi."
    },
    "present tense": {
        "en": "The verb tense used for present actions, habitual facts, and general truths.",
        "tr": "Şu anda gerçekleşen veya genel geçer durumları bildiren şimdiki/geniş zaman."
    },
    "past tense": {
        "en": "The verb tense expressing actions that occurred and completed before the present moment.",
        "tr": "Geçmişte tamamlanmış veya yaşanmış olayları bildiren geçmiş zaman."
    },
    "future tense": {
        "en": "The verb tense expressing actions that are expected to happen after the present time.",
        "tr": "Gelecekte gerçekleşmesi beklenen veya planlanan eylemleri bildiren gelecek zaman."
    },
    "imperative": {
        "en": "The grammatical mood used to express direct commands, instructions, or requests.",
        "tr": "Doğrudan emir, talimat veya rica bildiren fiil kipi."
    },
    "subjunctive": {
        "en": "The grammatical mood expressing wishes, doubts, hypotheticals, or possibilities.",
        "tr": "Dilek, istek, şüphe, varsayım veya temenni bildiren kip biçimi."
    },
    "synonym": {
        "en": "A word with identical or very similar meaning to another word in the same language.",
        "tr": "Yazılışları farklı ancak anlamları aynı veya birbirine çok yakın olan sözcük."
    },
    "antonym": {
        "en": "A word with opposite meaning to another word in the same language.",
        "tr": "Anlamca birbiriyle çelişen ve karşıt anlam taşıyan sözcük."
    }
}

# Mutually exclusive concept clusters for conflict detection
INCOMPATIBLE_CONCEPT_CLUSTERS = [
    # Phonetic categories
    {"vowel", "consonant", "silent"},
    {"weak vowel", "strong vowel"},
    {"diphthong", "hiatus"},
    # Grammatical gender
    {"masculine", "feminine", "neuter"},
    # Number
    {"singular", "plural"},
    # Parts of speech (core)
    {"noun", "verb", "adjective", "adverb", "preposition", "conjunction", "article", "pronoun"},
    # Cases
    {"nominative", "accusative", "dative", "genitive"},
    # Tenses
    {"present tense", "past tense", "future tense"},
    # Relations
    {"synonym", "antonym"}
]

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
    "verb": "verb", "verben": "verb",
    "adjektiv": "adjective", "adjektive": "adjective",
    "adverb": "adverb", "adverbien": "adverb",
    "praposition": "preposition", "prapositionen": "preposition",
    "pronomen": "pronoun",
    "artikel": "article",
    "genus": "gender",
    "maskulin": "masculine", "feminin": "feminine", "neutrum": "neuter",
    "einzahl": "singular", "mehrzahl": "plural", "singular": "singular", "plural": "plural",
    "kognat": "cognate",
    "falscher freund": "false friend",
    "stumm": "silent",
    "fall": "case", "kasus": "case",
    "nominativ": "nominative", "akkusativ": "accusative", "dativ": "dative", "genitiv": "genitive",
    "zeitform": "tense", "tempus": "tense",
    "prasens": "present tense", "prateritum": "past tense", "perfekt": "past tense", "futur": "future tense",
    "imperativ": "imperative", "konjunktiv": "subjunctive",
    "synonym": "synonym", "antonym": "antonym",

    # Spanish
    "vocal": "vowel", "vocales": "vowel",
    "consonante": "consonant", "consonantes": "consonant",
    "silaba": "syllable", "silabas": "syllable",
    "sonido": "sound", "sonidos": "sound",
    "palabra": "word", "palabras": "word",
    "letra": "letter", "letras": "letter",
    "abecedario": "alphabet", "alfabeto": "alphabet",
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
    "sustantivo": "noun", "sustantivos": "noun", "nombre": "noun",
    "verbo": "verb", "verbos": "verb",
    "adjetivo": "adjective", "adjetivos": "adjective",
    "adverbio": "adverb", "adverbios": "adverb",
    "pronombre": "pronoun", "pronombres": "pronoun",
    "articulo": "article", "articulos": "article",
    "preposicion": "preposition", "preposiciones": "preposition",
    "conjuncion": "conjunction", "conjunciones": "conjunction",
    "genero": "gender",
    "masculino": "masculine", "femenino": "feminine", "neutro": "neuter",
    "singular": "singular", "plural": "plural",
    "sujeto": "subject", "objeto": "object",
    "infinitivo": "infinitive", "conjugacion": "conjugation",
    "cognado": "cognate", "falso amigo": "false friend",
    "caso": "case", "nominativo": "nominative", "acusativo": "accusative", "dativo": "dative", "genitivo": "genitive",
    "tiempo verbal": "tense", "presente": "present tense", "pasado": "past tense", "preterito": "past tense", "imperfecto": "past tense", "futuro": "future tense",
    "imperativo": "imperative", "subjuntivo": "subjunctive",
    "sinonimo": "synonym", "antonimo": "antonym",

    # Turkish
    "sesli harf": "vowel", "unlu": "vowel", "unluler": "vowel", "sesli": "vowel",
    "sessiz harf": "consonant", "unsuz": "consonant", "unsuzler": "consonant", "sessiz": "consonant",
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
    "isim": "noun", "ad": "noun",
    "fiil": "verb", "eylem": "verb",
    "sifat": "adjective", "onad": "adjective",
    "zarf": "adverb", "belirtec": "adverb",
    "zamir": "pronoun", "adıl": "pronoun",
    "tanimlik": "article", "artikel": "article",
    "edat": "preposition", "ilgec": "preposition",
    "baglac": "conjunction",
    "cinsiyet": "gender", "eril": "masculine", "disil": "feminine", "notr": "neuter",
    "tekil": "singular", "cogul": "plural",
    "ozne": "subject", "nesne": "object", "tumlec": "object",
    "mastar": "infinitive", "fiil cekimi": "conjugation", "cekim": "conjugation",
    "ortak kokenli": "cognate", "yaniltici benzer": "false friend",
    "hal": "case", "ismin hali": "case", "durum": "case",
    "yalin hal": "nominative", "belirtme hali": "accusative", "yonelme hali": "dative", "tamlayan hali": "genitive",
    "zaman": "tense", "simdiki zaman": "present tense", "genis zaman": "present tense",
    "gecmis zaman": "past tense", "gelecek zaman": "future tense",
    "emir kipi": "imperative", "istek kipi": "subjunctive",
    "es anlamli": "synonym", "anlamdas": "synonym", "zit anlamli": "antonym", "karsit": "antonym",

    # French
    "voyelle": "vowel", "voyelles": "vowel",
    "consonne": "consonant", "consonnes": "consonant",
    "syllabe": "syllable", "mot": "word", "lettre": "letter",
    "nom": "noun", "verbe": "verb", "adjectif": "adjective", "adverbe": "adverb",
    "pronom": "pronoun", "article": "article", "preposition": "preposition",
    "genre": "gender", "masculin": "masculine", "feminin": "feminine",
    "singulier": "singular", "pluriel": "plural",

    # Italian
    "vocale": "vowel", "vocali": "vowel",
    "consonante": "consonant", "consonanti": "consonant",
    "sillaba": "syllable", "parola": "word", "lettera": "letter",
    "sostantivo": "noun", "nome": "noun", "verbo": "verb", "aggettivo": "adjective",
    "avverbio": "adverb", "pronome": "pronoun", "articolo": "article", "preposizione": "preposition",
    "genere": "gender", "maschile": "masculine", "femminile": "feminine",
    "singolare": "singular", "plurale": "plural"
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
    # Check individual words or phrases inside
    words = norm.split()
    for w in words:
        if w in CONCEPT_EXPLANATIONS:
            return w
        if w in ALIASES:
            return ALIASES[w]
    return ""

def are_concepts_incompatible(key1: str, key2: str) -> bool:
    """Checks whether two concept keys belong to the same mutually exclusive cluster."""
    if not key1 or not key2 or key1 == key2:
        return False
    for cluster in INCOMPATIBLE_CONCEPT_CLUSTERS:
        if key1 in cluster and key2 in cluster:
            return True
    return False

def get_canonical_concept_translation(concept_key: str, lang: str = "en") -> str:
    """Returns canonical name for a concept in the requested language."""
    target_lang = "tr" if lang == "tr" else "en"
    return CANONICAL_CONCEPT_NAMES.get(concept_key, {}).get(target_lang, "")

def get_concept_explanation(term: str = "", translation: str = "", lang: str = "en") -> str:
    """
    Returns a brief, CEFR-aligned explanation for a concept term or translation.
    Gives priority to term (ground truth).
    """
    term_key = resolve_concept_key(term)
    trans_key = resolve_concept_key(translation)

    # Ground truth is term
    key = term_key
    if not key:
        key = trans_key

    if not key or key not in CONCEPT_EXPLANATIONS:
        return ""
    expl_dict = CONCEPT_EXPLANATIONS[key]
    target_lang = "tr" if lang == "tr" else "en"
    return expl_dict.get(target_lang, expl_dict.get("en", ""))

def heal_concept_item(item: dict, lang: str = "en") -> dict:
    """
    Validates and self-heals a vocabulary/concept dictionary item.
    Ensures that if term is a known pedagogical concept, the translation
    and explanation strictly match that concept and never contradict it.
    """
    if not isinstance(item, dict):
        return item

    term = str(item.get("term") or item.get("word") or item.get("key") or "").strip()
    trans = str(item.get("translation") or item.get("meaning") or item.get("value") or "").strip()
    expl = str(item.get("explanation") or item.get("desc") or "").strip()

    term_key = resolve_concept_key(term)
    trans_key = resolve_concept_key(trans)

    target_lang = "tr" if lang == "tr" else "en"

    if term_key:
        # Term is ground truth concept!
        # 1. Check for semantic incompatibility with translation
        if trans_key and are_concepts_incompatible(term_key, trans_key):
            # Contradiction detected! Correct translation
            canonical_name = CANONICAL_CONCEPT_NAMES.get(term_key, {}).get(target_lang, "")
            if canonical_name:
                item["translation"] = canonical_name
                if "meaning" in item:
                    item["meaning"] = canonical_name
            # Overwrite explanation with the true concept explanation
            canonical_expl = CONCEPT_EXPLANATIONS.get(term_key, {}).get(target_lang, "")
            if canonical_expl:
                item["explanation"] = canonical_expl
        elif not trans or len(trans) <= 1:
            # Missing translation
            canonical_name = CANONICAL_CONCEPT_NAMES.get(term_key, {}).get(target_lang, "")
            if canonical_name:
                item["translation"] = canonical_name

        # 2. Check explanation compatibility
        expl_key = resolve_concept_key(expl)
        if not expl or len(expl) <= 2 or (expl_key and are_concepts_incompatible(term_key, expl_key)):
            item["explanation"] = CONCEPT_EXPLANATIONS.get(term_key, {}).get(target_lang, expl)

        # 3. Always enforce bilingual fields
        item["explanation_en"] = CONCEPT_EXPLANATIONS.get(term_key, {}).get("en", item.get("explanation_en", item["explanation"]))
        item["explanation_tr"] = CONCEPT_EXPLANATIONS.get(term_key, {}).get("tr", item.get("explanation_tr", item["explanation"]))

        if not item.get("translation_en") or are_concepts_incompatible(term_key, resolve_concept_key(item.get("translation_en"))):
            item["translation_en"] = CANONICAL_CONCEPT_NAMES.get(term_key, {}).get("en", item.get("translation"))
        if not item.get("translation_tr") or are_concepts_incompatible(term_key, resolve_concept_key(item.get("translation_tr"))):
            item["translation_tr"] = CANONICAL_CONCEPT_NAMES.get(term_key, {}).get("tr", item.get("translation"))

    elif trans_key:
        # Term is not a special concept, but translation is a concept
        if not expl or len(expl) <= 2:
            item["explanation"] = CONCEPT_EXPLANATIONS.get(trans_key, {}).get(target_lang, "")
            item["explanation_en"] = CONCEPT_EXPLANATIONS.get(trans_key, {}).get("en", "")
            item["explanation_tr"] = CONCEPT_EXPLANATIONS.get(trans_key, {}).get("tr", "")

    return item

