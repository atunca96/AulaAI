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
    "antonym": { "en": "Antonym", "tr": "Zıt Anlamlı" },
    "first": { "en": "First", "tr": "Birinci" },
    "second": { "en": "Second", "tr": "İkinci" },
    "third": { "en": "Third", "tr": "Üçüncü" },
    "fourth": { "en": "Fourth", "tr": "Dördüncü" },
    "fifth": { "en": "Fifth", "tr": "Beşinci" },
    "sixth": { "en": "Sixth", "tr": "Altıncı" },
    "seventh": { "en": "Seventh", "tr": "Yedinci" },
    "eighth": { "en": "Eighth", "tr": "Sekizinci" },
    "ninth": { "en": "Ninth", "tr": "Dokuzuncu" },
    "tenth": { "en": "Tenth", "tr": "Onuncu" },
    "primero": { "en": "First", "tr": "Birinci" },
    "segundo": { "en": "Second", "tr": "İkinci" },
    "tercero": { "en": "Third", "tr": "Üçüncü" },
    "cuarto": { "en": "Fourth", "tr": "Dördüncü" },
    "quinto": { "en": "Fifth", "tr": "Beşinci" },
    "sexto": { "en": "Sixth", "tr": "Altıncı" },
    "septimo": { "en": "Seventh", "tr": "Yedinci" },
    "octavo": { "en": "Eighth", "tr": "Sekizinci" },
    "noveno": { "en": "Ninth", "tr": "Dokuzuncu" },
    "decimo": { "en": "Tenth", "tr": "Onuncu" }
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
    },
    "first": {
        "en": "Precedes all others in order, sequence, or series.",
        "tr": "Bir dizideki ilk pozisyonu veya konumu belirtmek için kullanılır."
    },
    "second": {
        "en": "Coming next after the first in order.",
        "tr": "Bir dizideki ikinci sırayı veya konumu belirtir."
    },
    "third": {
        "en": "Coming next after the second in order.",
        "tr": "Üçüncü pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "fourth": {
        "en": "Coming next after the third in order.",
        "tr": "Dördüncü pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "fifth": {
        "en": "Coming next after the fourth in order.",
        "tr": "Beşinci pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "sixth": {
        "en": "Coming next after the fifth in order.",
        "tr": "Altıncı pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "seventh": {
        "en": "Coming next after the sixth in order.",
        "tr": "Yedinci pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "eighth": {
        "en": "Coming next after the seventh in order.",
        "tr": "Sekizinci pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "ninth": {
        "en": "Coming next after the eighth in order.",
        "tr": "Dokuzuncu pozisyonu veya sırayı belirtmek için kullanılır."
    },
    "tenth": {
        "en": "Coming next after the ninth in order.",
        "tr": "Onuncu pozisyonu veya sırayı belirtmek için kullanılır."
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
    "singolare": "singular", "plurale": "plural",

    # Ordinals
    "primero": "first", "primera": "first",
    "segundo": "second", "segunda": "second",
    "tercero": "third", "tercera": "third",
    "cuarto": "fourth", "cuarta": "fourth",
    "quinto": "fifth", "quinta": "fifth",
    "sexto": "sixth", "sexta": "sixth",
    "septimo": "seventh", "séptimo": "seventh", "septima": "seventh",
    "octavo": "eighth", "octava": "eighth",
    "noveno": "ninth", "novena": "ninth",
    "decimo": "tenth", "décimo": "tenth", "decima": "tenth",
    "birinci": "first", "ikinci": "second", "üçüncü": "third", "ucuncu": "third",
    "dördüncü": "fourth", "dorduncu": "fourth", "beşinci": "fifth", "besinci": "fifth",
    "altıncı": "sixth", "altinci": "sixth", "yedinci": "seventh", "sekizinci": "eighth",
    "dokuzuncu": "ninth", "onuncu": "tenth"
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
    # Word-level fallback ONLY for very short phrases (<= 3 words), NEVER for sentences
    if len(words) <= 3:
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

PRAGMATIC_DICTIONARY = {
    # Greetings & Salutations
    "buenas tardes": {
        "en": "Good afternoon",
        "tr": "Tünaydın",
        "desc_en": "Standard polite greeting used from midday until dusk.",
        "desc_tr": "Öğleden gün batımına kadar kullanılan kibar ve doğal selamlaşma ifadesi."
    },
    "buenos dias": {
        "en": "Good morning",
        "tr": "Günaydın",
        "desc_en": "Standard greeting used in the morning until noon.",
        "desc_tr": "Sabah saatlerinde öğleye kadar kullanılan standart karşılama ifadesi."
    },
    "buenas noches": {
        "en": "Good evening / Good night",
        "tr": "İyi akşamlar / İyi geceler",
        "desc_en": "Greeting used in the evening, also used as farewell at night.",
        "desc_tr": "Akşam saatlerinde selamlaşırken veya gece ayrılırken kullanılır."
    },
    "hola": {
        "en": "Hello / Hi",
        "tr": "Merhaba",
        "desc_en": "Universal, all-purpose greeting suitable for any time of day.",
        "desc_tr": "Günün her saatinde kullanılabilen genel ve samimi selamlaşma sözcüğü."
    },
    "adios": {
        "en": "Goodbye",
        "tr": "Hoşça kal",
        "desc_en": "Standard farewell expression.",
        "desc_tr": "Ayrılırken söylenen temel veda sözü."
    },
    "hasta luego": {
        "en": "See you later",
        "tr": "Sonra görüşürüz",
        "desc_en": "Common parting phrase: until later / see you later.",
        "desc_tr": "Ayrılırken 'sonra görüşmek üzere' anlamında kullanılan yaygın veda ifadesi."
    },
    "hasta pronto": {
        "en": "See you soon",
        "tr": "Yakında görüşürüz",
        "desc_en": "Parting phrase used when expecting to see someone again soon.",
        "desc_tr": "Kısa bir süre içinde yeniden bir araya gelineceğini bildiren veda ifadesi."
    },
    "nos vemos": {
        "en": "See you",
        "tr": "Görüşmek üzere",
        "desc_en": "Friendly parting expression: we will see each other.",
        "desc_tr": "Samimi ve günlük vedalaşmalarda kullanılan 'görüşmek üzere' ifadesi."
    },
    "hasta manana": {
        "en": "See you tomorrow",
        "tr": "Yarın görüşürüz",
        "desc_en": "Parting phrase specifically for the following day.",
        "desc_tr": "Ertesi gün yeniden bir araya gelineceğini bildiren veda ifadesi."
    },
    "mucho gusto": {
        "en": "Nice to meet you",
        "tr": "Tanıştığımıza memnun oldum",
        "desc_en": "Polite formula when introduced to someone for the first time.",
        "desc_tr": "Biriyle ilk kez tanışıldığında nezaket gereği söylenen kalıp."
    },
    "me llamo": {
        "en": "My name is",
        "tr": "Benim adım...",
        "desc_en": "Reflexive verb phrase used to state one's own name.",
        "desc_tr": "Kendi ismini söylerken kullanılan dönüşlü kalıp (Adım...)."
    },
    "como estas": {
        "en": "How are you?",
        "tr": "Nasılsın?",
        "desc_en": "Informal inquiry about someone's well-being.",
        "desc_tr": "Yakınlara ve akranlara yöneltilen samimi hal hatır sorusu."
    },
    "como esta usted": {
        "en": "How are you? (formal)",
        "tr": "Nasılsınız?",
        "desc_en": "Formal, respectful inquiry about well-being.",
        "desc_tr": "Resmi veya saygı gerektiren durumlarda sorulan hal hatır kalıbı."
    },

    # Spanish Ordinals
    "primero": {
        "en": "First",
        "tr": "Birinci",
        "desc_en": "Precedes all others in order or position.",
        "desc_tr": "Bir dizideki ilk konumu veya sırayı belirtir."
    },
    "segundo": {
        "en": "Second",
        "tr": "İkinci",
        "desc_en": "Coming next after the first in order.",
        "desc_tr": "Bir dizideki ikinci konumu veya sırayı belirtir."
    },
    "tercero": {
        "en": "Third",
        "tr": "Üçüncü",
        "desc_en": "Coming next after the second in order.",
        "desc_tr": "Bir dizideki üçüncü konumu veya sırayı belirtir."
    },
    "cuarto": {
        "en": "Fourth",
        "tr": "Dördüncü",
        "desc_en": "Coming next after the third in order.",
        "desc_tr": "Bir dizideki dördüncü konumu veya sırayı belirtir."
    },
    "quinto": {
        "en": "Fifth",
        "tr": "Beşinci",
        "desc_en": "Coming next after the fourth in order.",
        "desc_tr": "Beşinci sırayı veya konumu belirtmek için kullanılır."
    },
    "sexto": {
        "en": "Sixth",
        "tr": "Altıncı",
        "desc_en": "Coming next after the fifth in order.",
        "desc_tr": "Altıncı sırayı veya konumu belirtir."
    },
    "septimo": {
        "en": "Seventh",
        "tr": "Yedinci",
        "desc_en": "Coming next after the sixth in order.",
        "desc_tr": "Yedinci sırayı veya konumu belirtir."
    },
    "octavo": {
        "en": "Eighth",
        "tr": "Sekizinci",
        "desc_en": "Coming next after the seventh in order.",
        "desc_tr": "Sekizinci sırayı veya konumu belirtir."
    },
    "noveno": {
        "en": "Ninth",
        "tr": "Dokuzuncu",
        "desc_en": "Coming next after the eighth in order.",
        "desc_tr": "Dokuzuncu sırayı veya konumu belirtir."
    },
    "decimo": {
        "en": "Tenth",
        "tr": "Onuncu",
        "desc_en": "Coming next after the ninth in order.",
        "desc_tr": "Onuncu sırayı veya konumu belirtir."
    },

    # Subject Pronouns vs Auxiliary Verbs
    "yo": {
        "en": "I",
        "tr": "Ben",
        "desc_en": "First-person singular subject pronoun.",
        "desc_tr": "1. tekil şahıs zamiri (eylemi yapan konuşan kişi)."
    },
    "soy": {
        "en": "I am",
        "tr": "(Ben) ...yim / ...yım",
        "desc_en": "First-person singular present of 'ser' (to be: identity, origin, traits).",
        "desc_tr": "'Ser' (olmak) fiilinin 1. tekil şahıs çekimi (kimlik, milliyet, meslek bildirir)."
    },
    "tu": {
        "en": "You",
        "tr": "Sen",
        "desc_en": "Second-person informal singular subject pronoun.",
        "desc_tr": "2. tekil şahıs zamiri (samimi hitap)."
    },
    "eres": {
        "en": "You are",
        "tr": "(Sen) ...sin / ...sın",
        "desc_en": "Second-person singular present of 'ser'.",
        "desc_tr": "'Ser' fiilinin 2. tekil şahıs çekimi."
    },
    "el": {
        "en": "He",
        "tr": "O (erkek)",
        "desc_en": "Third-person singular masculine pronoun.",
        "desc_tr": "3. tekil şahıs eril zamiri."
    },
    "ella": {
        "en": "She",
        "tr": "O (kadın)",
        "desc_en": "Third-person singular feminine pronoun.",
        "desc_tr": "3. tekil şahıs dişil zamiri."
    },
    "usted": {
        "en": "You (formal)",
        "tr": "Siz (resmi)",
        "desc_en": "Second-person formal singular pronoun (conjugates with 3rd person).",
        "desc_tr": "Nezaket ve resmiyet bildiren 2. tekil şahıs hitabı."
    },
    "es": {
        "en": "He/she/it is",
        "tr": "(O) ...dir / ...dır",
        "desc_en": "Third-person singular present of 'ser'.",
        "desc_tr": "'Ser' fiilinin 3. tekil şahıs çekimi."
    },
    "nosotros": {
        "en": "We",
        "tr": "Biz",
        "desc_en": "First-person plural subject pronoun.",
        "desc_tr": "1. çoğul şahıs zamiri."
    },
    "nosotras": {
        "en": "We (feminine)",
        "tr": "Biz (kadınlar)",
        "desc_en": "First-person plural feminine subject pronoun.",
        "desc_tr": "1. çoğul şahıs dişil zamiri."
    },
    "somos": {
        "en": "We are",
        "tr": "(Biz) ...yiz / ...yız",
        "desc_en": "First-person plural present of 'ser'.",
        "desc_tr": "'Ser' fiilinin 1. çoğul şahıs çekimi."
    },
    "vosotros": {
        "en": "You all (informal)",
        "tr": "Sizler (samimi)",
        "desc_en": "Second-person plural informal pronoun (used in Spain).",
        "desc_tr": "İspanya'da kullanılan 2. çoğul şahıs zamiri."
    },
    "vosotras": {
        "en": "You all (feminine)",
        "tr": "Sizler (kadınlar)",
        "desc_en": "Second-person plural feminine informal pronoun (Spain).",
        "desc_tr": "İspanya'da kullanılan 2. çoğul şahıs dişil zamiri."
    },
    "sois": {
        "en": "You all are",
        "tr": "(Sizler) ...siniz / ...sınız",
        "desc_en": "Second-person plural present of 'ser'.",
        "desc_tr": "'Ser' fiilinin 2. çoğul şahıs çekimi (İspanya)."
    },
    "ellos": {
        "en": "They (masculine / mixed)",
        "tr": "Onlar (eril)",
        "desc_en": "Third-person plural masculine pronoun.",
        "desc_tr": "3. çoğul şahıs eril / genel zamiri."
    },
    "ellas": {
        "en": "They (feminine)",
        "tr": "Onlar (dişil)",
        "desc_en": "Third-person plural feminine pronoun.",
        "desc_tr": "3. çoğul şahıs dişil zamiri."
    },
    "ustedes": {
        "en": "You all",
        "tr": "Sizler",
        "desc_en": "Second-person plural pronoun (universal in Latin America).",
        "desc_tr": "2. çoğul şahıs hitabı (Latin Amerika'da genel, İspanya'da resmi)."
    },
    "son": {
        "en": "They are / You all are",
        "tr": "(Onlar) ...dirler / ...dırlar",
        "desc_en": "Third-person plural present of 'ser'.",
        "desc_tr": "'Ser' fiilinin 3. çoğul şahıs çekimi."
    },

    # ── GERMAN (Deutsch) ──
    "guten morgen": {
        "en": "Good morning", "tr": "Günaydın",
        "desc_en": "Standard German morning greeting used until midday.",
        "desc_tr": "Almancada sabah saatlerinde öğleye kadar kullanılan standart karşılama."
    },
    "guten tag": {
        "en": "Good day / Hello", "tr": "İyi günler / Merhaba",
        "desc_en": "Standard polite daytime greeting in German.",
        "desc_tr": "Almancada gün içinde yaygın olarak kullanılan resmi ve genel selamlaşma."
    },
    "guten abend": {
        "en": "Good evening", "tr": "İyi akşamlar",
        "desc_en": "Polite German greeting used in the evening hours.",
        "desc_tr": "Almancada akşam saatlerinde kullanılan kibar selamlaşma."
    },
    "gute nacht": {
        "en": "Good night", "tr": "İyi geceler",
        "desc_en": "German parting expression specifically used before bedtime.",
        "desc_tr": "Almancada uyumadan önce veya gece ayrılırken söylenen veda ifadesi."
    },
    "auf wiedersehen": {
        "en": "Goodbye", "tr": "Görüşmek üzere / Hoşça kalın",
        "desc_en": "Formal German farewell expression.",
        "desc_tr": "Almancada resmi ve kibar veda sözü."
    },
    "tschuss": {
        "en": "Bye", "tr": "Hoşça kal",
        "desc_en": "Informal German farewell among friends and peers.",
        "desc_tr": "Almancada arkadaşlar arasında kullanılan samimi veda ifadesi."
    },
    "ich": {
        "en": "I", "tr": "Ben",
        "desc_en": "German first-person singular subject pronoun.",
        "desc_tr": "Almanca 1. tekil şahıs zamiri."
    },
    "bin": {
        "en": "I am", "tr": "(Ben) ...yim / ...yım",
        "desc_en": "First-person singular present of German 'sein' (to be).",
        "desc_tr": "Almancada 'sein' (olmak) fiilinin 1. tekil şahıs çekimi (asla sadece zamir değil)."
    },
    "du": {
        "en": "You", "tr": "Sen",
        "desc_en": "German second-person informal singular subject pronoun.",
        "desc_tr": "Almanca 2. tekil şahıs zamiri (samimi hitap)."
    },
    "bist": {
        "en": "You are", "tr": "(Sen) ...sin / ...sın",
        "desc_en": "Second-person singular present of German 'sein'.",
        "desc_tr": "Almancada 'sein' (olmak) fiilinin 2. tekil şahıs çekimi."
    },
    "er": {
        "en": "He", "tr": "O (erkek)",
        "desc_en": "German third-person singular masculine pronoun.",
        "desc_tr": "Almanca 3. tekil şahıs eril zamiri."
    },
    "sie": {
        "en": "She / They / You (formal)", "tr": "O (kadın) / Onlar / Siz",
        "desc_en": "German third-person feminine pronoun, plural pronoun, or formal 'You'.",
        "desc_tr": "Almancada dişil 'O', çoğul 'Onlar' veya büyük harfle resmi 'Siz'."
    },
    "ist": {
        "en": "He/she/it is", "tr": "(O) ...dir / ...dır",
        "desc_en": "Third-person singular present of German 'sein'.",
        "desc_tr": "Almancada 'sein' (olmak) fiilinin 3. tekil şahıs çekimi."
    },
    "wir": {
        "en": "We", "tr": "Biz",
        "desc_en": "German first-person plural subject pronoun.",
        "desc_tr": "Almanca 1. çoğul şahıs zamiri."
    },
    "sind": {
        "en": "We are / They are", "tr": "(Biz) ...yiz / ...yız",
        "desc_en": "First and third person plural present of German 'sein'.",
        "desc_tr": "Almancada 'sein' fiilinin çoğul çekimi."
    },

    # ── FRENCH (Français) ──
    "bonjour": {
        "en": "Hello / Good morning", "tr": "Günaydın / Merhaba",
        "desc_en": "Universal French daytime greeting.",
        "desc_tr": "Fransızcada gün boyu kullanılan standart selamlaşma."
    },
    "bonsoir": {
        "en": "Good evening", "tr": "İyi akşamlar",
        "desc_en": "French greeting used from late afternoon through the evening.",
        "desc_tr": "Fransızcada akşam saatlerinde kullanılan selamlaşma."
    },
    "bonne nuit": {
        "en": "Good night", "tr": "İyi geceler",
        "desc_en": "French parting wish before sleeping.",
        "desc_tr": "Fransızcada gece yatarken veya ayrılırken söylenen iyi geceler dileği."
    },
    "au revoir": {
        "en": "Goodbye", "tr": "Görüşmek üzere / Hoşça kalın",
        "desc_en": "Standard French farewell expression.",
        "desc_tr": "Fransızcada temel ve saygılı veda ifadesi."
    },
    "salut": {
        "en": "Hi / Bye", "tr": "Selam / Hoşça kal",
        "desc_en": "Informal French greeting and parting phrase among friends.",
        "desc_tr": "Fransızcada hem merhaba hem hoşça kal anlamında samimi hitap."
    },
    "je": {
        "en": "I", "tr": "Ben",
        "desc_en": "French first-person singular subject pronoun.",
        "desc_tr": "Fransızca 1. tekil şahıs zamiri."
    },
    "suis": {
        "en": "I am", "tr": "(Ben) ...yim / ...yım",
        "desc_en": "First-person singular present of French 'être' (to be).",
        "desc_tr": "Fransızcada 'être' (olmak) fiilinin 1. tekil şahıs çekimi (asla sadece zamir değil)."
    },
    "tu": {
        "en": "You", "tr": "Sen",
        "desc_en": "Second-person informal singular subject pronoun.",
        "desc_tr": "2. tekil şahıs zamiri (samimi hitap)."
    },
    "il": {
        "en": "He", "tr": "O (erkek)",
        "desc_en": "French third-person singular masculine pronoun.",
        "desc_tr": "Fransızca 3. tekil şahıs eril zamiri."
    },
    "elle": {
        "en": "She", "tr": "O (kadın)",
        "desc_en": "French third-person singular feminine pronoun.",
        "desc_tr": "Fransızca 3. tekil şahıs dişil zamiri."
    },
    "est": {
        "en": "He/she is", "tr": "(O) ...dir / ...dır",
        "desc_en": "Third-person singular present of French 'être'.",
        "desc_tr": "Fransızcada 'être' (olmak) fiilinin 3. tekil şahıs çekimi."
    },
    "nous": {
        "en": "We", "tr": "Biz",
        "desc_en": "French first-person plural subject pronoun.",
        "desc_tr": "Fransızca 1. çoğul şahıs zamiri."
    },
    "sommes": {
        "en": "We are", "tr": "(Biz) ...yiz / ...yız",
        "desc_en": "First-person plural present of French 'être'.",
        "desc_tr": "Fransızcada 'être' fiilinin 1. çoğul şahıs çekimi."
    },
    "vous": {
        "en": "You (formal/plural)", "tr": "Siz / Sizler",
        "desc_en": "French polite singular or general plural second-person pronoun.",
        "desc_tr": "Fransızcada kibar tekil veya genel çoğul hitap zamiri."
    },

    # ── ITALIAN (Italiano) ──
    "buongiorno": {
        "en": "Good morning / Good day", "tr": "Günaydın / İyi günler",
        "desc_en": "Standard Italian polite daytime greeting.",
        "desc_tr": "İtalyancada sabah ve gündüz kullanılan kibar karşılama."
    },
    "buonasera": {
        "en": "Good evening", "tr": "İyi akşamlar",
        "desc_en": "Italian greeting used in the late afternoon and evening.",
        "desc_tr": "İtalyancada akşam saatlerinde söylenen selamlaşma."
    },
    "buonanotte": {
        "en": "Good night", "tr": "İyi geceler",
        "desc_en": "Italian parting expression before sleeping.",
        "desc_tr": "İtalyancada uyumadan önce söylenen veda kalıbı."
    },
    "arrivederci": {
        "en": "Goodbye", "tr": "Görüşmek üzere",
        "desc_en": "Standard Italian polite farewell expression.",
        "desc_tr": "İtalyancada kibar ve yaygın veda sözü."
    },
    "ciao": {
        "en": "Hello / Bye", "tr": "Merhaba / Hoşça kal",
        "desc_en": "Universal informal Italian greeting and parting word.",
        "desc_tr": "İtalyancada hem karşılama hem veda için kullanılan samimi sözcük."
    },
    "io": {
        "en": "I", "tr": "Ben",
        "desc_en": "Italian first-person singular subject pronoun.",
        "desc_tr": "İtalyanca 1. tekil şahıs zamiri."
    },
    "sono": {
        "en": "I am / They are", "tr": "(Ben) ...yim / ...yım",
        "desc_en": "First-person singular (or 3rd-plural) present of Italian 'essere' (to be).",
        "desc_tr": "İtalyancada 'essere' (olmak) fiilinin 1. tekil şahıs çekimi."
    },
    "lui": {
        "en": "He", "tr": "O (erkek)",
        "desc_en": "Italian third-person singular masculine pronoun.",
        "desc_tr": "İtalyanca 3. tekil şahıs eril zamiri."
    },
    "lei": {
        "en": "She / You (formal)", "tr": "O (kadın) / Siz (resmi)",
        "desc_en": "Italian third-person feminine pronoun or formal 'You'.",
        "desc_tr": "İtalyancada 3. tekil şahıs dişil zamiri veya resmi 'Siz'."
    },
    "noi": {
        "en": "We", "tr": "Biz",
        "desc_en": "Italian first-person plural subject pronoun.",
        "desc_tr": "İtalyanca 1. çoğul şahıs zamiri."
    },
    "siamo": {
        "en": "We are", "tr": "(Biz) ...yiz / ...yız",
        "desc_en": "First-person plural present of Italian 'essere'.",
        "desc_tr": "İtalyancada 'essere' fiilinin 1. çoğul şahıs çekimi."
    },

    # ── ENGLISH ──
    "good morning": {
        "en": "Good morning", "tr": "Günaydın",
        "desc_en": "Standard morning greeting used from dawn until noon.",
        "desc_tr": "Sabah saatlerinde öğleye kadar kullanılan standart karşılama."
    },
    "good afternoon": {
        "en": "Good afternoon", "tr": "Tünaydın",
        "desc_en": "Polite greeting used from midday until evening.",
        "desc_tr": "Öğleden akşama kadar kullanılan kibar ve doğal selamlaşma."
    },
    "good evening": {
        "en": "Good evening", "tr": "İyi akşamlar",
        "desc_en": "Polite greeting used during evening hours.",
        "desc_tr": "Akşam saatlerinde kullanılan kibar karşılama."
    },
    "good night": {
        "en": "Good night", "tr": "İyi geceler",
        "desc_en": "Parting wish spoken before bed or upon leaving late at night.",
        "desc_tr": "Yatmadan önce veya gece ayrılırken söylenen veda ifadesi."
    },
    "i am": {
        "en": "I am", "tr": "(Ben) ...yim / ...yım",
        "desc_en": "First-person singular present of 'to be'.",
        "desc_tr": "'To be' (olmak) fiilinin 1. tekil şahıs çekimi."
    },
    "you are": {
        "en": "You are", "tr": "(Sen) ...sin / ...sın",
        "desc_en": "Second-person present of 'to be'.",
        "desc_tr": "'To be' fiilinin 2. şahıs çekimi."
    },
    "we are": {
        "en": "We are", "tr": "(Biz) ...yiz / ...yız",
        "desc_en": "First-person plural present of 'to be'.",
        "desc_tr": "'To be' fiilinin 1. çoğul şahıs çekimi."
    },
    "they are": {
        "en": "They are", "tr": "(Onlar) ...dirler / ...dırlar",
        "desc_en": "Third-person plural present of 'to be'.",
        "desc_tr": "'To be' fiilinin 3. çoğul şahıs çekimi."
    }
}

def heal_pragmatic_item(item: dict, lang: str = "en") -> dict:
    """
    Validates and heals pragmatic greetings, pronouns, and verbs.
    Ensures natural Turkish equivalents (e.g. 'Tünaydın', 'Ben', '(Ben) ...yim / ...yım').
    """
    if not isinstance(item, dict):
        return item
    
    term = str(item.get("term") or item.get("word") or item.get("key") or "").strip()
    # Single letters or items marked as letters must NEVER be treated as pragmatic greetings or pronouns
    if len(term) <= 1 or item.get("type") == "letter" or item.get("name") or item.get("phonetic_en") or item.get("phonetic_tr"):
        return item
    norm = _normalize(term)
    target_lang = "tr" if lang == "tr" else "en"

    if norm in PRAGMATIC_DICTIONARY:
        entry = PRAGMATIC_DICTIONARY[norm]
        item["translation_en"] = entry["en"]
        item["translation_tr"] = entry["tr"]
        item["explanation_en"] = entry["desc_en"]
        item["explanation_tr"] = entry["desc_tr"]
        item["translation"] = entry[target_lang]
        if "meaning" in item:
            item["meaning"] = entry[target_lang]
        if "turkish" in item:
            item["turkish"] = entry["tr"]
        if "english" in item:
            item["english"] = entry["en"]
        item["explanation"] = entry[f"desc_{target_lang}"]
        return item

    # Self-heal unnatural Turkish calque 'öğleden sonra' in greetings
    for k in ["translation", "meaning", "translation_tr", "turkish"]:
        if k in item and isinstance(item[k], str):
            val = item[k].strip()
            if "öğleden sonra" in val.lower() or "ogleden sonra" in val.lower():
                item[k] = "Tünaydın"

    return item

def heal_concept_item(item: dict, lang: str = "en") -> dict:
    """
    Validates and self-heals a vocabulary/concept dictionary item.
    Ensures that if term is a known pedagogical concept or pragmatic term,
    the translation and explanation strictly match and never contradict it.
    """
    if not isinstance(item, dict):
        return item

    # Run pragmatic healer first
    item = heal_pragmatic_item(item, lang=lang)

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

    # Sanitize tautological definitions (e.g. "... eylemini ifade eder", "refers to the act of...")
    tautology_re = re.compile(
        r'(?i)\b(?:eylemini\s+ifade\s+eder|etkinliğini\s+ifade\s+eder|ifade\s+etmek\s+için\s+kullanılır|'
        r'eylemidir|yapma\s+eylemi|resim\s+yaratmayı|üretme\s+eylemidir|gitmeyi\s+içerir|'
        r'refers?\s+to\s+the\s+act\s+of|means?\s+the\s+act\s+of|is\s+the\s+act\s+of|used\s+to\s+express\s+the\s+action\s+of)\b'
    )
    for expl_k in ["explanation", "explanation_tr", "explanation_en"]:
        if expl_k in item and isinstance(item[expl_k], str) and tautology_re.search(item[expl_k]):
            item[expl_k] = ""

    return item

