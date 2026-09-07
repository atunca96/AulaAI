# Standard Reference Data for Alphabets and Phonemes
# Used to "teach" the AI exactly what to include for foundational lessons.
import json

ALPHABETS = {
    "Chinese": {
        "type": "Pinyin Initials and Finals",
        "sets": [
            {
                "title": "Pinyin Initials (Consonants)",
                "items": [
                    {"term": "b - 播", "translation": "bō"},
                    {"term": "p - 泼", "translation": "pō"},
                    {"term": "m - 摸", "translation": "mō"},
                    {"term": "f - 佛", "translation": "fó"},
                    {"term": "d - 得", "translation": "de"},
                    {"term": "t - 特", "translation": "te"},
                    {"term": "n - 呢", "translation": "ne"},
                    {"term": "l - 勒", "translation": "le"},
                    {"term": "g - 哥", "translation": "gē"},
                    {"term": "k - 科", "translation": "kē"},
                    {"term": "h - 喝", "translation": "hē"},
                    {"term": "j - 鸡", "translation": "jī"},
                    {"term": "q - 七", "translation": "qī"},
                    {"term": "x - 西", "translation": "xī"},
                    {"term": "zh - 知", "translation": "zhī"},
                    {"term": "ch - 吃", "translation": "chī"},
                    {"term": "sh - 狮", "translation": "shī"},
                    {"term": "r - 日", "translation": "rì"},
                    {"term": "z - 资", "translation": "zī"},
                    {"term": "c - 刺", "translation": "cì"},
                    {"term": "s - 丝", "translation": "sī"},
                    {"term": "y - 衣", "translation": "yī"},
                    {"term": "w - 屋", "translation": "wū"}
                ]
            },
            {
                "title": "Pinyin Finals (Vowels)",
                "items": [
                    {"term": "啊", "translation": "ā"},
                    {"term": "哦", "translation": "ō"},
                    {"term": "饿", "translation": "ē"},
                    {"term": "衣", "translation": "ī"},
                    {"term": "五", "translation": "ū"},
                    {"term": "鱼", "translation": "ǘ"}
                ]
            }
        ]
    },
    "Japanese": {
        "type": "Hiragana",
        "sets": [
            {
                "title": "Hiragana: Vowels & K-Group",
                "items": [
                    {"term": "あ", "translation": "a"},
                    {"term": "い", "translation": "i"},
                    {"term": "う", "translation": "u"},
                    {"term": "え", "translation": "e"},
                    {"term": "お", "translation": "o"},
                    {"term": "か", "translation": "ka"}, {"term": "き", "translation": "ki"}, {"term": "く", "translation": "ku"}, {"term": "け", "translation": "ke"}, {"term": "こ", "translation": "ko"}
                ]
            },
            {
                "title": "Hiragana: S, T, N Groups",
                "items": [
                    {"term": "さ", "translation": "sa"}, {"term": "し", "translation": "shi"}, {"term": "す", "translation": "su"}, {"term": "せ", "translation": "se"}, {"term": "そ", "translation": "so"},
                    {"term": "た", "translation": "ta"}, {"term": "ち", "translation": "chi"}, {"term": "つ", "translation": "tsu"}, {"term": "て", "translation": "te"}, {"term": "と", "translation": "to"},
                    {"term": "な", "translation": "na"}, {"term": "に", "translation": "ni"}, {"term": "ぬ", "translation": "nu"}, {"term": "ね", "translation": "ne"}, {"term": "の", "translation": "no"}
                ]
            },
            {
                "title": "Hiragana: H, M, Y, R, W Groups",
                "items": [
                    {"term": "は", "translation": "ha"}, {"term": "ひ", "translation": "hi"}, {"term": "ふ", "translation": "fu"}, {"term": "へ", "translation": "he"}, {"term": "ほ", "translation": "ho"},
                    {"term": "ま", "translation": "ma"}, {"term": "み", "translation": "mi"}, {"term": "む", "translation": "mu"}, {"term": "め", "translation": "me"}, {"term": "も", "translation": "mo"},
                    {"term": "や", "translation": "ya"}, {"term": "ゆ", "translation": "yu"}, {"term": "よ", "translation": "yo"},
                    {"term": "ら", "translation": "ra"}, {"term": "り", "translation": "ri"}, {"term": "る", "translation": "ru"}, {"term": "れ", "translation": "re"}, {"term": "ろ", "translation": "ro"},
                    {"term": "わ", "translation": "wa"}, {"term": "を", "translation": "wo"}, {"term": "ん", "translation": "n"}
                ]
            }
        ]
    },
    "Spanish": {
        "type": "Alfabeto",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "be"}, {"term": "C", "translation": "ce"}, {"term": "D", "translation": "de"}, {"term": "E", "translation": "e"}, 
            {"term": "F", "translation": "efe"}, {"term": "G", "translation": "ge"}, {"term": "H", "translation": "hache"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "jota"},
            {"term": "K", "translation": "ka"}, {"term": "L", "translation": "ele"}, {"term": "M", "translation": "eme"}, {"term": "N", "translation": "ene"}, {"term": "Ñ", "translation": "eñe"},
            {"term": "O", "translation": "o"}, {"term": "P", "translation": "pe"}, {"term": "Q", "translation": "cu"}, {"term": "R", "translation": "ere"}, {"term": "S", "translation": "ese"},
            {"term": "T", "translation": "te"}, {"term": "U", "translation": "u"}, {"term": "V", "translation": "uve"}, {"term": "W", "translation": "uve doble"}, {"term": "X", "translation": "equis"},
            {"term": "Y", "translation": "i griega"}, {"term": "Z", "translation": "zeta"}
        ]
    },
    "Russian": {
        "type": "Alphabet",
        "items": [
            {"term": "А", "translation": "а"}, {"term": "Б", "translation": "бэ"}, {"term": "В", "translation": "вэ"}, {"term": "Г", "translation": "гэ"}, {"term": "Д", "translation": "дэ"},
            {"term": "Е", "translation": "е"}, {"term": "Ё", "translation": "ё"}, {"term": "Ж", "translation": "жэ"}, {"term": "З", "translation": "зэ"}, {"term": "И", "translation": "и"},
            {"term": "Й", "translation": "ий"}, {"term": "К", "translation": "ка"}, {"term": "Л", "translation": "эль"}, {"term": "М", "translation": "эм"}, {"term": "Н", "translation": "эн"},
            {"term": "О", "translation": "о"}, {"term": "П", "translation": "пэ"}, {"term": "Р", "translation": "эр"}, {"term": "С", "translation": "эс"}, {"term": "Т", "translation": "тэ"},
            {"term": "У", "translation": "у"}, {"term": "Ф", "translation": "эф"}, {"term": "Х", "translation": "ха"}, {"term": "Ц", "translation": "цэ"}, {"term": "Ч", "translation": "че"},
            {"term": "Ш", "translation": "ша"}, {"term": "Щ", "translation": "ща"}, {"term": "Ъ", "translation": "ъ"}, {"term": "Ы", "translation": "ы"}, {"term": "Ь", "translation": "ь"},
            {"term": "Э", "translation": "э"}, {"term": "Ю", "translation": "ю"}, {"term": "Я", "translation": "я"}
        ]
    },
    "Turkish": {
        "type": "Alfabe",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "be"}, {"term": "C", "translation": "ce"}, {"term": "Ç", "translation": "çe"}, {"term": "D", "translation": "de"},
            {"term": "E", "translation": "e"}, {"term": "F", "translation": "fe"}, {"term": "G", "translation": "ge"}, {"term": "Ğ", "translation": "yumuşak ge"}, {"term": "H", "translation": "he"},
            {"term": "I", "translation": "ı"}, {"term": "İ", "translation": "i"}, {"term": "J", "translation": "je"}, {"term": "K", "translation": "ke"}, {"term": "L", "translation": "le"},
            {"term": "M", "translation": "me"}, {"term": "N", "translation": "ne"}, {"term": "O", "translation": "o"}, {"term": "Ö", "translation": "ö"}, {"term": "P", "translation": "pe"},
            {"term": "R", "translation": "re"}, {"term": "S", "translation": "se"}, {"term": "Ş", "translation": "şe"}, {"term": "T", "translation": "te"}, {"term": "U", "translation": "u"},
            {"term": "Ü", "translation": "ü"}, {"term": "V", "translation": "ve"}, {"term": "Y", "translation": "ye"}, {"term": "Z", "translation": "ze"}
        ]
    },
    "Arabic": {
        "type": "Alphabet",
        "items": [
            {"term": "ا", "translation": "Alif"}, {"term": "ب", "translation": "Ba"}, {"term": "ت", "translation": "Ta"}, {"term": "ث", "translation": "Tha"}, {"term": "ج", "translation": "Jim"},
            {"term": "ح", "translation": "Ha"}, {"term": "خ", "translation": "Kha"}, {"term": "د", "translation": "Dal"}, {"term": "ذ", "translation": "Dhal"}, {"term": "ر", "translation": "Ra"},
            {"term": "ز", "translation": "Zay"}, {"term": "س", "translation": "Sin"}, {"term": "ش", "translation": "Shin"}, {"term": "ص", "translation": "Sad"}, {"term": "ض", "translation": "Dad"},
            {"term": "ط", "translation": "Ta"}, {"term": "ظ", "translation": "Za"}, {"term": "ع", "translation": "Ayn"}, {"term": "غ", "translation": "Ghayn"}, {"term": "ف", "translation": "Fa"},
            {"term": "ق", "translation": "Qaf"}, {"term": "ك", "translation": "Kaf"}, {"term": "ل", "translation": "Lam"}, {"term": "م", "translation": "Mim"}, {"term": "ن", "translation": "Nun"},
            {"term": "ه", "translation": "Ha"}, {"term": "و", "translation": "Waw"}, {"term": "ي", "translation": "Ya"}
        ]
    },
    "German": {
        "type": "Alphabet",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "be"}, {"term": "C", "translation": "ce"}, {"term": "D", "translation": "de"}, {"term": "E", "translation": "e"},
            {"term": "F", "translation": "ef"}, {"term": "G", "translation": "ge"}, {"term": "H", "translation": "ha"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "jot"},
            {"term": "K", "translation": "ka"}, {"term": "L", "translation": "el"}, {"term": "M", "translation": "em"}, {"term": "N", "translation": "en"}, {"term": "O", "translation": "o"},
            {"term": "P", "translation": "pe"}, {"term": "Q", "translation": "ku"}, {"term": "R", "translation": "er"}, {"term": "S", "translation": "es"}, {"term": "T", "translation": "te"},
            {"term": "U", "translation": "u"}, {"term": "V", "translation": "vau"}, {"term": "W", "translation": "we"}, {"term": "X", "translation": "ix"}, {"term": "Y", "translation": "ypsilon"}, {"term": "Z", "translation": "zett"},
            {"term": "Ä", "translation": "a-umlaut"}, {"term": "Ö", "translation": "o-umlaut"}, {"term": "Ü", "translation": "u-umlaut"}, {"term": "ß", "translation": "eszett"}
        ]
    },
    "French": {
        "type": "Alphabet",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "bé"}, {"term": "C", "translation": "cé"}, {"term": "D", "translation": "dé"}, {"term": "E", "translation": "e"},
            {"term": "F", "translation": "effe"}, {"term": "G", "translation": "gé"}, {"term": "H", "translation": "hache"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "ji"},
            {"term": "K", "translation": "ka"}, {"term": "L", "translation": "elle"}, {"term": "M", "translation": "emme"}, {"term": "N", "translation": "enne"}, {"term": "O", "translation": "o"},
            {"term": "P", "translation": "pé"}, {"term": "Q", "translation": "qu"}, {"term": "R", "translation": "erre"}, {"term": "S", "translation": "esse"}, {"term": "T", "translation": "té"},
            {"term": "U", "translation": "u"}, {"term": "V", "translation": "vé"}, {"term": "W", "translation": "double vé"}, {"term": "X", "translation": "ics"}, {"term": "Y", "translation": "i grec"}, {"term": "Z", "translation": "zède"}
        ]
    },
    "Italian": {
        "type": "Alfabeto",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "bi"}, {"term": "C", "translation": "ci"}, {"term": "D", "translation": "di"}, {"term": "E", "translation": "e"},
            {"term": "F", "translation": "effe"}, {"term": "G", "translation": "gi"}, {"term": "H", "translation": "acca"}, {"term": "I", "translation": "i"}, {"term": "L", "translation": "elle"},
            {"term": "M", "translation": "emme"}, {"term": "N", "translation": "enne"}, {"term": "O", "translation": "o"}, {"term": "P", "translation": "pi"}, {"term": "Q", "translation": "cu"},
            {"term": "R", "translation": "erre"}, {"term": "S", "translation": "esse"}, {"term": "T", "translation": "te"}, {"term": "U", "translation": "u"}, {"term": "V", "translation": "vi/vu"}, {"term": "Z", "translation": "zeta"}
        ]
    },
    "Portuguese": {
        "type": "Alfabeto",
        "items": [
            {"term": "A", "translation": "á"}, {"term": "B", "translation": "bê"}, {"term": "C", "translation": "cê"}, {"term": "D", "translation": "dê"}, {"term": "E", "translation": "é"},
            {"term": "F", "translation": "éfe"}, {"term": "G", "translation": "gê"}, {"term": "H", "translation": "agá"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "jota"},
            {"term": "K", "translation": "capa"}, {"term": "L", "translation": "éle"}, {"term": "M", "translation": "éme"}, {"term": "N", "translation": "éne"}, {"term": "O", "translation": "ó"},
            {"term": "P", "translation": "pê"}, {"term": "Q", "translation": "quê"}, {"term": "R", "translation": "ére"}, {"term": "S", "translation": "ésse"}, {"term": "T", "translation": "tê"},
            {"term": "U", "translation": "u"}, {"term": "V", "translation": "vê"}, {"term": "W", "translation": "dáblio"}, {"term": "X", "translation": "xis"}, {"term": "Y", "translation": "ípsilon"}, {"term": "Z", "translation": "zê"}
        ]
    },
    "Dutch": {
        "type": "Alfabet",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "be"}, {"term": "C", "translation": "ce"}, {"term": "D", "translation": "de"}, {"term": "E", "translation": "e"},
            {"term": "F", "translation": "ef"}, {"term": "G", "translation": "ge"}, {"term": "H", "translation": "ha"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "jee"},
            {"term": "K", "translation": "ka"}, {"term": "L", "translation": "el"}, {"term": "M", "translation": "em"}, {"term": "N", "translation": "en"}, {"term": "O", "translation": "o"},
            {"term": "P", "translation": "pe"}, {"term": "Q", "translation": "ku"}, {"term": "R", "translation": "er"}, {"term": "S", "translation": "es"}, {"term": "T", "translation": "te"},
            {"term": "U", "translation": "u"}, {"term": "V", "translation": "vee"}, {"term": "W", "translation": "wee"}, {"term": "X", "translation": "iks"}, {"term": "Y", "translation": "ij/ypsilon"}, {"term": "Z", "translation": "zet"}
        ]
    },
    "Swedish": {
        "type": "Alfabet",
        "items": [
            {"term": "A", "translation": "a"}, {"term": "B", "translation": "be"}, {"term": "C", "translation": "se"}, {"term": "D", "translation": "de"}, {"term": "E", "translation": "e"},
            {"term": "F", "translation": "eff"}, {"term": "G", "translation": "ge"}, {"term": "H", "translation": "hå"}, {"term": "I", "translation": "i"}, {"term": "J", "translation": "ji"},
            {"term": "K", "translation": "kå"}, {"term": "L", "translation": "ell"}, {"term": "M", "translation": "emm"}, {"term": "N", "translation": "enn"}, {"term": "O", "translation": "o"},
            {"term": "P", "translation": "pe"}, {"term": "Q", "translation": "ku"}, {"term": "R", "translation": "ärr"}, {"term": "S", "translation": "ess"}, {"term": "T", "translation": "te"},
            {"term": "U", "translation": "u"}, {"term": "V", "translation": "ve"}, {"term": "W", "translation": "dubbel-ve"}, {"term": "X", "translation": "eks"}, {"term": "Y", "translation": "y"}, {"term": "Z", "translation": "säta"},
            {"term": "Å", "translation": "å"}, {"term": "Ä", "translation": "ä"}, {"term": "Ö", "translation": "ö"}
        ]
    },
    "Korean": {
        "type": "Hangul",
        "items": [
            {"term": "ㄱ", "translation": "giyeok"}, {"term": "ㄴ", "translation": "nieun"}, {"term": "ㄷ", "translation": "digeut"}, {"term": "ㄹ", "translation": "rieul"}, {"term": "ㅁ", "translation": "mieun"},
            {"term": "ㅂ", "translation": "bieup"}, {"term": "ㅅ", "translation": "siot"}, {"term": "ㅇ", "translation": "ieung"}, {"term": "ㅈ", "translation": "jieut"}, {"term": "ㅊ", "translation": "chieut"},
            {"term": "ㅋ", "translation": "kieuk"}, {"term": "ㅌ", "translation": "tieut"}, {"term": "ㅍ", "translation": "pieup"}, {"term": "ㅎ", "translation": "hieut"},
            {"term": "ㅏ", "translation": "a"}, {"term": "ㅑ", "translation": "ya"}, {"term": "ㅓ", "translation": "eo"}, {"term": "ㅕ", "translation": "yeo"}, {"term": "ㅗ", "translation": "o"},
            {"term": "ㅛ", "translation": "yo"}, {"term": "ㅜ", "translation": "u"}, {"term": "ㅠ", "translation": "yu"}, {"term": "ㅡ", "translation": "eu"}, {"term": "ㅣ", "translation": "i"}
        ]
    },
    "Greek": {
        "type": "Alphabet",
        "items": [
            {"term": "Α", "translation": "Alpha"}, {"term": "Β", "translation": "Beta"}, {"term": "Γ", "translation": "Gamma"}, {"term": "Δ", "translation": "Delta"}, {"term": "Ε", "translation": "Epsilon"},
            {"term": "Ζ", "translation": "Zeta"}, {"term": "Η", "translation": "Eta"}, {"term": "Θ", "translation": "Theta"}, {"term": "Ι", "translation": "Iota"}, {"term": "Κ", "translation": "Kappa"},
            {"term": "Λ", "translation": "Lambda"}, {"term": "Μ", "translation": "Mu"}, {"term": "Ν", "translation": "Nu"}, {"term": "Ξ", "translation": "Xi"}, {"term": "Ο", "translation": "Omicron"},
            {"term": "Π", "translation": "Pi"}, {"term": "Ρ", "translation": "Rho"}, {"term": "Σ", "translation": "Sigma"}, {"term": "Τ", "translation": "Tau"}, {"term": "Υ", "translation": "Upsilon"},
            {"term": "Φ", "translation": "Phi"}, {"term": "Χ", "translation": "Chi"}, {"term": "Ψ", "translation": "Psi"}, {"term": "Ω", "translation": "Omega"}
        ]
    }
}

# Language-Specific Special Characters, Accent Marks, and Pronunciation Notes
# Used for topics like "Accent Marks and Special Characters", "Vowel Sounds", etc.
# This prevents the AI from generating a generic European accent list for languages that don't use those characters.
SPECIAL_CHARACTERS = {
    "Dutch": {
        "title": "Dutch Special Characters & Diacritics",
        "notes": (
            "Dutch uses the standard 26-letter Latin alphabet. It does NOT have ç, ñ, ß, or other Romance/Germanic special letters. "
            "The digraph IJ/ij is considered a single unit and is sometimes treated as the 27th letter. "
            "Dutch uses a limited set of diacritical marks, primarily: "
            "1. Trema/diaeresis (¨) to indicate vowel separation: ë, ï, ü (e.g., geïnteresseerd, reünie, coördinatie). "
            "2. Acute accent (´) for emphasis or disambiguation: é (e.g., één = one, vs. een = a/an; hé! = hey!). "
            "Dutch does NOT use grave accents (à, è) in standard orthography. "
            "Dutch does NOT use ç, ñ, ã, õ, or other characters from Spanish/Portuguese/French."
        ),
        "items": [
            {"term": "IJ / ij", "translation": "Digraph treated as a single letter, sounds like 'ay' in 'say'"},
            {"term": "ë", "translation": "Trema: marks vowel separation (e.g., geë̈rriteerd)"},
            {"term": "ï", "translation": "Trema: separates vowels (e.g., naïef = naive)"},
            {"term": "ü", "translation": "Trema: separates vowels (e.g., reünie = reunion)"},
            {"term": "é", "translation": "Acute accent: emphasis or disambiguation (e.g., één = one)"},
            {"term": "ö", "translation": "Trema: separates vowels (e.g., coöperatie = cooperation)"},
        ]
    },
    "German": {
        "title": "German Special Characters (Sonderzeichen)",
        "notes": (
            "German uses the 26-letter Latin alphabet plus 4 additional characters: Ä/ä, Ö/ö, Ü/ü (umlauts) and ß (eszett/sharp S). "
            "Umlauts change vowel pronunciation and meaning. ß represents a voiceless 's' sound after long vowels. "
            "German does NOT use ç, ñ, or accent marks from other languages."
        ),
        "items": [
            {"term": "Ä / ä", "translation": "A-umlaut: sounds like 'e' in 'bed' (e.g., Mädchen = girl)"},
            {"term": "Ö / ö", "translation": "O-umlaut: rounded front vowel (e.g., schön = beautiful)"},
            {"term": "Ü / ü", "translation": "U-umlaut: rounded front close vowel (e.g., über = over)"},
            {"term": "ß", "translation": "Eszett/sharp S: voiceless 's' after long vowels (e.g., Straße = street)"},
        ]
    },
    "Spanish": {
        "title": "Spanish Special Characters & Accents",
        "notes": (
            "Spanish uses the 27-letter alphabet (including Ñ). "
            "Accent marks: á, é, í, ó, ú indicate stress or disambiguation. ü (diaeresis) appears in güe/güi to pronounce the 'u'. "
            "¿ and ¡ are used for inverted question and exclamation marks."
        ),
        "items": [
            {"term": "Ñ / ñ", "translation": "Eñe: palatal nasal, like 'ny' in canyon (e.g., España)"},
            {"term": "á, é, í, ó, ú", "translation": "Acute accents: mark stressed syllables or distinguish homophones"},
            {"term": "ü", "translation": "Diaeresis: 'u' is pronounced in güe/güi (e.g., pingüino)"},
            {"term": "¿ ¡", "translation": "Inverted punctuation: used at the start of questions/exclamations"},
        ]
    },
    "French": {
        "title": "French Special Characters & Accents",
        "notes": (
            "French uses the 26-letter Latin alphabet with several diacritical marks: "
            "é (acute), è/à/ù (grave), ê/â/î/ô/û (circumflex), ë/ï/ü (trema), and ç (cedilla). "
            "Ligatures: æ (rare), œ (e.g., cœur = heart)."
        ),
        "items": [
            {"term": "é", "translation": "Acute accent: closed 'e' sound (e.g., café)"},
            {"term": "è, à, ù", "translation": "Grave accents: open 'e' or distinguishes homophones"},
            {"term": "ê, â, î, ô, û", "translation": "Circumflex: historical/phonetic marker"},
            {"term": "ë, ï, ü", "translation": "Trema: vowel separation (e.g., Noël)"},
            {"term": "ç", "translation": "Cedilla: 'c' sounds like 's' before a/o/u (e.g., français)"},
            {"term": "œ", "translation": "Ligature: (e.g., cœur = heart, sœur = sister)"},
        ]
    },
    "Italian": {
        "title": "Italian Special Characters & Accents",
        "notes": (
            "Italian uses the 21-letter core alphabet (no J, K, W, X, Y in native words). "
            "Accent marks: à, è/é, ì, ò/ó, ù mark stressed final syllables. "
            "Italian does NOT use ç, ñ, ü, or ß."
        ),
        "items": [
            {"term": "à", "translation": "Grave accent on 'a' (e.g., città = city)"},
            {"term": "è / é", "translation": "Open/closed 'e' (e.g., è = is, perché = why)"},
            {"term": "ì", "translation": "Accent on 'i' (e.g., così = so)"},
            {"term": "ò / ó", "translation": "Open/closed 'o' (e.g., però = but)"},
            {"term": "ù", "translation": "Accent on 'u' (e.g., più = more)"},
        ]
    },
    "Portuguese": {
        "title": "Portuguese Special Characters & Accents",
        "notes": (
            "Portuguese uses the 26-letter Latin alphabet with: "
            "á, â, ã, à, é, ê, í, ó, ô, õ, ú (accents), and ç (cedilla). "
            "Tildes (ã, õ) indicate nasal vowels, unique to Portuguese/Spanish."
        ),
        "items": [
            {"term": "ã, õ", "translation": "Tilde: nasal vowels (e.g., não = no, coração = heart)"},
            {"term": "á, é, í, ó, ú", "translation": "Acute accents: mark stress"},
            {"term": "â, ê, ô", "translation": "Circumflex: closed vowel sounds"},
            {"term": "à", "translation": "Grave accent: contraction of preposition+article (e.g., à = a + a)"},
            {"term": "ç", "translation": "Cedilla: 'c' sounds like 's' (e.g., coração)"},
        ]
    },
    "Turkish": {
        "title": "Turkish Special Characters",
        "notes": (
            "Turkish uses a 29-letter Latin alphabet with: Ç/ç, Ğ/ğ, I/ı, İ/i, Ö/ö, Ş/ş, Ü/ü. "
            "The dotless ı and dotted İ are critical: they are DIFFERENT letters with different sounds. "
            "Turkish does NOT use ñ, ß, W, X, Q, or accent marks."
        ),
        "items": [
            {"term": "Ç / ç", "translation": "Like 'ch' in 'church' (e.g., çay = tea)"},
            {"term": "Ğ / ğ", "translation": "Yumuşak ge: lengthens the preceding vowel (e.g., dağ = mountain)"},
            {"term": "I / ı", "translation": "Dotless I: 'uh' sound, like 'i' in 'cousin'"},
            {"term": "İ / i", "translation": "Dotted İ: like 'ee' in 'see'"},
            {"term": "Ö / ö", "translation": "Rounded front vowel (e.g., göz = eye)"},
            {"term": "Ş / ş", "translation": "Like 'sh' in 'ship' (e.g., şeker = sugar)"},
            {"term": "Ü / ü", "translation": "Rounded close front vowel (e.g., gül = rose)"},
        ]
    },
    "Russian": {
        "title": "Russian Special Characters",
        "notes": (
            "Russian uses the 33-letter Cyrillic alphabet. Special features include: "
            "Ё/ё (always stressed), Ъ (hard sign), Ь (soft sign), and Й (short I). "
            "Russian does NOT use any Latin diacritical marks."
        ),
        "items": [
            {"term": "Ё / ё", "translation": "Stressed 'yo' sound (e.g., ёлка = fir tree)"},
            {"term": "Й / й", "translation": "Short I: semivowel 'y' (e.g., чай = tea)"},
            {"term": "Ъ / ъ", "translation": "Hard sign: separates prefix from root"},
            {"term": "Ь / ь", "translation": "Soft sign: softens the preceding consonant"},
        ]
    },
    "Arabic": {
        "title": "Arabic Diacritical Marks (Tashkeel)",
        "notes": (
            "Arabic uses short vowel marks (harakat) written above/below consonants: "
            "Fatha (◌َ), Kasra (◌ِ), Damma (◌ُ), Sukun (◌ْ), Shadda (◌ّ), and Tanween markers. "
            "The Hamza (ء) and Taa Marbuta (ة) are also special characters."
        ),
        "items": [
            {"term": "◌َ (Fatha)", "translation": "Short 'a' vowel above the consonant"},
            {"term": "◌ِ (Kasra)", "translation": "Short 'i' vowel below the consonant"},
            {"term": "◌ُ (Damma)", "translation": "Short 'u' vowel above the consonant"},
            {"term": "◌ّ (Shadda)", "translation": "Doubles/emphasizes the consonant"},
            {"term": "◌ْ (Sukun)", "translation": "No vowel: consonant is 'silent'"},
            {"term": "ء (Hamza)", "translation": "Glottal stop"},
            {"term": "ة (Taa Marbuta)", "translation": "Feminine ending marker"},
        ]
    },
    "Swedish": {
        "title": "Swedish Special Characters",
        "notes": (
            "Swedish uses the 29-letter alphabet with 3 extra vowels: Å/å, Ä/ä, Ö/ö. "
            "These are full letters, NOT decorative accents. They appear at the end of the alphabet. "
            "Swedish does NOT use ç, ñ, ß, or accent marks from other languages."
        ),
        "items": [
            {"term": "Å / å", "translation": "Like 'o' in 'or' (e.g., år = year)"},
            {"term": "Ä / ä", "translation": "Like 'e' in 'bed' (e.g., äpple = apple)"},
            {"term": "Ö / ö", "translation": "Rounded front vowel (e.g., öl = beer)"},
        ]
    },
    "Korean": {
        "title": "Korean Special Features (Hangul)",
        "notes": (
            "Korean Hangul is an alphabetic syllabary. Special features include: "
            "Double consonants (ㄲ, ㄸ, ㅃ, ㅆ, ㅉ) for tense sounds, "
            "compound vowels (ㅐ, ㅔ, ㅘ, ㅙ, ㅚ, ㅝ, ㅞ, ㅟ, ㅢ), "
            "and batchim (final consonant) rules."
        ),
        "items": [
            {"term": "ㄲ, ㄸ, ㅃ, ㅆ, ㅉ", "translation": "Double/tense consonants: stronger, unaspirated"},
            {"term": "ㅐ, ㅔ", "translation": "Compound vowels: ae, e"},
            {"term": "ㅘ, ㅙ, ㅚ", "translation": "W-compound vowels: wa, wae, oe"},
            {"term": "ㅝ, ㅞ, ㅟ, ㅢ", "translation": "W/Y-compound vowels: wo, we, wi, ui"},
            {"term": "받침 (Batchim)", "translation": "Final consonant position in a syllable block"},
        ]
    },
    "Greek": {
        "title": "Greek Special Characters & Diacritics",
        "notes": (
            "Modern Greek uses the tonos (΄) accent mark to indicate stressed syllables. "
            "The diaeresis (¨) is used on ϊ and ϋ to prevent diphthongs. "
            "Greek does NOT use ç, ñ, ß, or any Latin diacritical marks."
        ),
        "items": [
            {"term": "΄ (tonos)", "translation": "Accent mark indicating stress (e.g., μητέρα = mother)"},
            {"term": "ϊ / ϋ", "translation": "Diaeresis: prevents diphthong (e.g., ρολόι = watch)"},
            {"term": "ς", "translation": "Final sigma: used at end of words (vs. σ mid-word)"},
        ]
    },
    "Chinese": {
        "title": "Chinese Pinyin Tone Marks",
        "notes": (
            "Mandarin Chinese uses 4 tones + neutral tone, marked on Pinyin vowels: "
            "1st tone (ā, ē, ī, ō, ū), 2nd (á, é, í, ó, ú), 3rd (ǎ, ě, ǐ, ǒ, ǔ), 4th (à, è, ì, ò, ù). "
            "Tone marks always go on the main vowel. ü (with umlaut) appears after j, q, x, y."
        ),
        "items": [
            {"term": "ā á ǎ à", "translation": "Four tones of 'a': flat, rising, dipping, falling"},
            {"term": "ē é ě è", "translation": "Four tones of 'e'"},
            {"term": "ī í ǐ ì", "translation": "Four tones of 'i'"},
            {"term": "ō ó ǒ ò", "translation": "Four tones of 'o'"},
            {"term": "ū ú ǔ ù", "translation": "Four tones of 'u'"},
            {"term": "ǖ ǘ ǚ ǜ", "translation": "Four tones of 'ü' (after j, q, x, y)"},
        ]
    },
    "Japanese": {
        "title": "Japanese Special Marks (Dakuten & Handakuten)",
        "notes": (
            "Japanese uses dakuten (゛) and handakuten (゜) to modify kana sounds: "
            "Dakuten voices consonants (か→が, ka→ga), handakuten creates 'p' sounds (は→ぱ, ha→pa). "
            "Small kana (っ, ゃ, ゅ, ょ) modify pronunciation. The chōon (ー) extends vowels in katakana."
        ),
        "items": [
            {"term": "゛ (Dakuten/Tenten)", "translation": "Voices consonants: k→g, s→z, t→d, h→b"},
            {"term": "゜ (Handakuten/Maru)", "translation": "Changes h-row to p: は→ぱ (ha→pa)"},
            {"term": "っ (Small tsu)", "translation": "Geminate: doubles the next consonant"},
            {"term": "ゃ ゅ ょ", "translation": "Combination kana: modify preceding consonant"},
            {"term": "ー (Chōon)", "translation": "Long vowel mark in katakana"},
        ]
    }
}

def get_reference_prompt(language):
    data = ALPHABETS.get(language)
    if not data:
        return ""
    
    return f"\nREFERENCE DATA for {language} {data['type']}:\n{json.dumps(data, ensure_ascii=False)}\nUse this data as the absolute ground truth for your vocabulary pages. Do not skip any entries."

def get_special_chars_prompt(language):
    """Returns a language-specific constraint prompt for accent/special character topics."""
    data = SPECIAL_CHARACTERS.get(language)
    if not data:
        return ""
    
    return (
        f"\nLANGUAGE-SPECIFIC SPECIAL CHARACTER REFERENCE for {language}:\n"
        f"Title: {data['title']}\n"
        f"RULES: {data['notes']}\n"
        f"VERIFIED DATA:\n{json.dumps(data['items'], ensure_ascii=False)}\n"
        f"CRITICAL: Use ONLY the characters and diacritics listed above. "
        f"Do NOT include characters from other languages (e.g., do not put ç in Dutch, ñ in German, ß in Dutch). "
        f"If a character is NOT in this reference list, it does NOT belong in {language}."
    )


# ── UNIVERSAL CEFR PEDAGOGICAL ASSESSMENT FRAMEWORK (A1 - C2) ──

LANGUAGE_PEDAGOGY = {
    "Spanish": {
        "phonetics": (
            "Test authentic phonetic discrimination: b/v sound identity, c before e/i (/θ/ or /s/) vs a/o/u (/k/), "
            "g before e/i (/x/) vs a/o/u (/g/), silent h (hijo, hora), jota (/x/), qu- only before e/i (queso, quince), "
            "r (flap) vs rr (trill), ll/y, and ñ (/ɲ/). "
            "NEVER ask what word is inside a letter name (e.g., do NOT ask 'which letter has doble in its name'). "
            "Instead test spelling of real words, identifying silent letters, or distinguishing sounds in minimal pairs."
        ),
        "grammar_traps": [
            "ser vs. estar (essence/identity vs. state/location)",
            "por vs. para (cause/medium vs. destination/purpose)",
            "gustar-type verbs (A mí me gusta / gustan)",
            "direct vs. indirect object pronouns (lo/la vs. le)",
            "gender exceptions (el problema, el tema, el día, la mano, el agua fría)",
            "preterite vs. imperfect aspectual difference (completed vs. habitual/background)"
        ]
    },
    "German": {
        "phonetics": (
            "Test authentic phonetic discrimination: umlauts (ä, ö, ü) contrasting with a, o, u; "
            "ch1 (ich-Laut after front vowels e, i, ä, ö, ü) vs ch2 (ach-Laut after back vowels a, o, u); "
            "sp- and st- at start of syllable sounding like /ʃp/ and /ʃt/; v sounding like /f/ in native words (Vogel, Vater); "
            "s before vowel sounding like /z/ (Sonne); ß representing unvoiced /s/ after long vowels/diphthongs."
        ),
        "grammar_traps": [
            "der, die, das grammatical genders",
            "four cases: Nominativ, Akkusativ, Dativ, Genitiv",
            "two-way prepositions (Wechselpräpositionen): Dativ for location (Wo?), Akkusativ for motion (Wohin?)",
            "word order: Verb-second (V2) in main clauses, verb-final in subordinate clauses (weil, dass, wenn)",
            "separable prefix verbs (anrufen -> ruft an)",
            "Perfekt auxiliary selection: haben vs. sein (change of place/state)"
        ]
    },
    "French": {
        "phonetics": (
            "Test authentic phonetic discrimination: nasal vowels (an/en, in/ain, on, un), "
            "silent final consonants (t, s, d, p, x in chat, lit, trop, prix), liaisons (les amis -> /lezami/), "
            "u (/y/) vs ou (/u/), é (/e/) vs è/ê (/ɛ/), c with cedilla (ç) before a/o/u sounding like /s/."
        ),
        "grammar_traps": [
            "passé composé with avoir vs. être (DR & MRS VANDERTRAMP and reflexive verbs)",
            "passé composé vs. imparfait",
            "partitive articles (du, de la, des) becoming 'de' in negative sentences",
            "pronoun placement before the conjugated verb or auxiliary",
            "subjunctive triggers (il faut que, bien que, vouloir que)"
        ]
    },
    "Italian": {
        "phonetics": (
            "Test authentic phonetic discrimination: c and g before e/i are soft (ch/dzh), before a/o/u are hard; "
            "ch and gh make c/g hard before e/i (chiesa, spaghetti); gn (/ɲ/), gli (/ʎ/), double consonants (gemination: fatto vs fato)."
        ),
        "grammar_traps": [
            "essere vs. avere in passato prossimo with past participle agreement",
            "pronominal particles ci (there/about it) and ne (of it/them)",
            "piacere agreement (mi piace il libro vs mi piacciono i libri)",
            "articulated prepositions (di + il = del, a + la = alla)",
            "congiuntivo (subjunctive) in expressions of opinion and emotion"
        ]
    },
    "Turkish": {
        "phonetics": (
            "Test authentic phonetic discrimination: ı (dotless i) vs i (dotted i), ö vs o, ü vs u, "
            "ğ (soft g - lengthens preceding vowel, never starts a word), c (/dʒ/) vs ç (/tʃ/), s vs ş (/ʃ/)."
        ),
        "grammar_traps": [
            "2-way vowel harmony (-ler/-lar, -e/-a) and 4-way vowel harmony (-i/-ı/-u/-ü)",
            "consonant mutation (p/ç/t/k -> b/c/d/ğ before a vowel, e.g. kitap -> kitabı)",
            "consonant assimilation (f, s, t, k, ç, ş, h, p + d -> t, c -> ç)",
            "agglutinative suffix ordering (noun + plural + possessive + case)",
            "SOV sentence structure and postpositions (için, ile, gibi)"
        ]
    },
    "Greek": {
        "phonetics": (
            "Test authentic phonetic discrimination: vowel digraphs (αι=/e/, ει/οι/υι=/i/, ου=/u/), "
            "consonant digraphs (μπ=/b/ or /mb/, ντ=/d/ or /nd/, γκ=/g/ or /ŋg/, τσ=/ts/, τζ=/dz/), tonos accentuation."
        ),
        "grammar_traps": [
            "3 genders (masculine, feminine, neuter) with articles (o, η, το)",
            "4 cases (Nominative, Genitive, Accusative, Vocative)",
            "verbal aspect: continuous (imperfective) vs. simple (aorist/perfective)"
        ]
    },
    "Russian": {
        "phonetics": (
            "Test authentic phonetic discrimination: hard vs soft consonants (palatalization via ь and soft vowels), "
            "vowel reduction (akanie: unstressed 'o' pronounced as /a/; ikanie: unstressed 'e/я' pronounced as /i/), "
            "voiced/voiceless consonant assimilation (e.g. в -> /f/ before unvoiced)."
        ),
        "grammar_traps": [
            "6 cases (Nominative, Genitive, Dative, Accusative, Instrumental, Prepositional)",
            "verbal aspects: imperfective (process, repetition) vs. perfective (result, single completed action)",
            "verbs of motion (unidirectional vs multidirectional: идти/ходить, ехать/ездить)"
        ]
    },
    "Arabic": {
        "phonetics": (
            "Test authentic phonetic discrimination: emphatic consonants (ص, ض, ط, ظ) vs plain counterparts (س, د, ت, ذ), "
            "pharyngeal sounds (ع, ح) vs (ء, هـ), velar/uvular sounds (خ, غ, ق), long vs short vowels."
        ),
        "grammar_traps": [
            "root-and-pattern (triconsonantal) morphological derivations",
            "nominal sentences (jumla ismiyya) without a present tense copula",
            "non-human plural agreement treated as feminine singular",
            "idaafa (construct state) possessive construction"
        ]
    }
}

CEFR_COMPETENCY_FRAMEWORK = {
    "A1": (
        "CEFR A1 (Breakthrough / Beginner):\n"
        "- Focus on basic phonetic-orthographic mapping (sound-to-letter, silent letters, spelling of high-frequency words).\n"
        "- High-frequency routine expressions, formal vs informal address (tú vs usted, du vs Sie).\n"
        "- Gender and number concord in simple noun phrases (el libro nuevo, las casas blancas).\n"
        "- Basic present tense indicative of regular and core irregular verbs (ser, estar, tener, ir, hacer).\n"
        "- Authentic situational dialogues in everyday settings (café, airport, classroom, introductions).\n"
        "- NEVER ask giveaway questions (e.g. prompt contains the answer word) or meta-trivia about letter names."
    ),
    "A2": (
        "CEFR A2 (Waystage / Elementary):\n"
        "- Narrative past tenses: aspectual contrast between completed punctual actions and background/routine descriptions.\n"
        "- Pronominal syntax: direct and indirect object pronouns (placement before conjugated verbs, enclisis with infinitives/gerunds).\n"
        "- Everyday prepositions and directional connectors (por vs para, desde, hasta, hacia).\n"
        "- Reflexive verbs in daily routine contexts with temporal markers (normalmente, de repente, ayer, mientras).\n"
        "- Functional problem-solving scenarios: shopping, asking for directions, making plans, expressing simple opinions."
    ),
    "B1": (
        "CEFR B1 (Threshold / Intermediate):\n"
        "- Mood distinction: Indicative vs Subjunctive in subordinate noun clauses (wishes, doubts, emotions, recommendations).\n"
        "- Purpose and temporal clauses with subjunctive (para que, antes de que, cuando + subjuntivo for future).\n"
        "- Hypothetical conditional sentences (real vs unreal conditionals: si tuviera..., compraría...).\n"
        "- Indirect speech reporting and discourse connectors (sin embargo, por lo tanto, a pesar de que).\n"
        "- Distinguishing between near-synonymous verbs and idiomatic collocations."
    ),
    "B2": (
        "CEFR B2 (Vantage / Upper-Intermediate):\n"
        "- Advanced Subjunctive nuances (concessive clauses, modal restrictions, hypothetical past).\n"
        "- Passive voice, passive reflexive (se pasivo), and impersonal constructions.\n"
        "- Nuances in register (formal vs informal, journalistic vs colloquial).\n"
        "- Complex discourse markers and cohesive devices.\n"
        "- False friends (faux amis), deceptive cognates, and prepositions governed by specific verbs."
    ),
    "C1": (
        "CEFR C1 (Effective Operational Proficiency / Advanced):\n"
        "- Complex argumentation, broad lexical repertoire with idiomatic expressions, flexible communication for professional/academic contexts.\n"
        "- Stylistic and rhetorical subtlety, figurative language, polysemy, and cultural collocations.\n"
        "- Advanced grammatical structures (literary tenses, subjunctive nuances in concessions/hypotheticals, syntactic inversions).\n"
        "- Pragmatic inference, subtext analysis, detecting implicit tone, irony, and speaker stance.\n"
        "- Specialized academic and professional domain discourse."
    ),
    "C2": (
        "CEFR C2 (Mastery / Near-Native Proficiency):\n"
        "- Effortless comprehension of virtually everything heard or read, reconstructing arguments from diverse spoken/written sources into coherent presentations.\n"
        "- Spontaneous, fluent, and precise expression, conveying fine shades of meaning even in highly complex or contentious scenarios.\n"
        "- Deep cultural and literary mastery: historical idioms, proverbs, regional colloquialisms vs elevated academic/philosophical register.\n"
        "- Nuanced rhetorical devices: sarcasm, irony, hyperbole, litotes, subtle hedging, dialectal variations.\n"
        "- Native-level syntactic dexterity, spontaneous repartee, and critical synthesis of dense academic texts."
    )
}

def get_pedagogical_guidelines(language: str, level: str = "A1") -> str:
    """Generates authoritative CEFR-level and language-specific pedagogical criteria."""
    lvl_key = "A1"
    u_lvl = (level or "A1").upper()
    for k in ["C2", "C1", "B2", "B1", "A2", "A1"]:
        if k in u_lvl:
            lvl_key = k
            break
    
    cefr_text = CEFR_COMPETENCY_FRAMEWORK.get(lvl_key, CEFR_COMPETENCY_FRAMEWORK["A1"])
    lang_info = LANGUAGE_PEDAGOGY.get(language, {})
    
    lang_guidance = ""
    if lang_info:
        phon = lang_info.get("phonetics", "")
        traps = lang_info.get("grammar_traps", [])
        traps_str = "\n".join([f"  • {t}" for t in traps])
        lang_guidance = f"\nTARGET LANGUAGE SPECIFICS ({language}):\nPhonetic Principles: {phon}\nKey Pedagogical Traps & Competencies to test:\n{traps_str}\n"
    
    return f"\n--- PEDAGOGICAL ASSESSMENT STANDARDS ({lvl_key}) ---\n{cefr_text}\n{lang_guidance}"

import os
import re

_BM_TITLE_MAP = None

def _get_bm_title_map():
    global _BM_TITLE_MAP
    if _BM_TITLE_MAP is not None:
        return _BM_TITLE_MAP
    _BM_TITLE_MAP = {}
    bm_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bilingual_materials.json")
    if os.path.exists(bm_path):
        try:
            with open(bm_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                _BM_TITLE_MAP = d.get("title_pairs", {})
        except Exception:
            pass
    return _BM_TITLE_MAP

LANGUAGE_NAMES_TR = {
    "spanish": "İspanyolcada",
    "english": "İngilizcede",
    "german": "Almancada",
    "french": "Fransızcada",
    "italian": "İtalyancada",
    "portuguese": "Portekizcede",
    "russian": "Rusçada",
    "chinese": "Çincede",
    "japanese": "Japoncada",
    "korean": "Korecede",
    "arabic": "Arapçada",
    "turkish": "Türkçede",
    "greek": "Yunancada",
    "dutch": "Felemenkçede",
    "swedish": "İsveççede",
}

class UniversalCurriculumTranslator:
    """
    Universal Pedagogical Curriculum Title Translator.
    Decomposes and translates ANY educational curriculum title (units, chapters, topics)
    into natural, professional, grammatically correct Turkish.
    Supports German, Spanish, French, Italian, English, Russian, Japanese, Chinese,
    Korean, Arabic, Portuguese, Dutch, Greek, Swedish, Turkish, and arbitrary pedagogical terms.
    """

    LANGUAGES = {
        "german": ("Almanca", "Alman", "Almancada"),
        "spanish": ("İspanyolca", "İspanyol", "İspanyolcada"),
        "french": ("Fransızca", "Fransız", "Fransızcada"),
        "italian": ("İtalyanca", "İtalyan", "İtalyancada"),
        "english": ("İngilizce", "İngiliz", "İngilizcede"),
        "russian": ("Rusça", "Rus", "Rusçada"),
        "chinese": ("Çince", "Çin", "Çincede"),
        "japanese": ("Japonca", "Japon", "Japoncada"),
        "korean": ("Korece", "Kore", "Korecede"),
        "arabic": ("Arapça", "Arap", "Arapçada"),
        "portuguese": ("Portekizce", "Portekiz", "Portekizcede"),
        "dutch": ("Felemenkçe", "Felemenk", "Felemenkçede"),
        "greek": ("Yunanca", "Yunan", "Yunancada"),
        "swedish": ("İsveççe", "İsveç", "İsveççede"),
        "turkish": ("Türkçe", "Türk", "Türkçede"),
    }

    QUOTED_EXPRESSIONS = {
        "who are you": "Sen Kimsin",
        "who are you?": "Sen Kimsin?",
        "what is your name": "Adın Ne",
        "what is your name?": "Adın Ne?",
        "where are you from": "Nerelisin",
        "where are you from?": "Nerelisin?",
        "how are you": "Nasılsın",
        "how are you?": "Nasılsın?",
        "hello": "Merhaba",
        "goodbye": "Hoşça Kal",
        "please": "Lütfen",
        "thank you": "Teşekkür Ederim",
        "yes": "Evet",
        "no": "Hayır",
        "doler": "Doler",
        "gustar": "Gustar",
        "ser": "Ser",
        "estar": "Estar",
        "haben": "Haben",
        "sein": "Sein",
        "avoir": "Avoir",
        "être": "Être",
    }

    PHRASES = {
        # Getting acquainted / greetings
        "getting acquainted with the german language": "Almanca ile Tanışma",
        "getting acquainted with the spanish language": "İspanyolca ile Tanışma",
        "getting acquainted with the french language": "Fransızca ile Tanışma",
        "getting acquainted with the italian language": "İtalyanca ile Tanışma",
        "getting acquainted with the english language": "İngilizce ile Tanışma",
        "getting acquainted": "Tanışma",
        "basic greetings and farewells": "Temel Selamlaşmalar ve Vedalaşmalar",
        "greetings and farewells": "Selamlaşmalar ve Vedalaşmalar",
        "greetings and introductions": "Selamlaşmalar ve Tanıtımlar",
        "basic greetings": "Temel Selamlaşmalar",
        "farewells": "Vedalaşmalar",
        "saying hello and goodbye": "Merhaba ve Hoşça Kal Deme",
        
        # Personal information & introductions
        "sharing personal information": "Kişisel Bilgileri Paylaşma",
        "personal information": "Kişisel Bilgiler",
        "personal info": "Kişisel Bilgiler",
        "introducing yourself and others": "Kendini ve Başkalarını Tanıtma",
        "introducing yourself": "Kendini Tanıtma",
        "introducing others": "Başkalarını Tanıtma",
        "name, age, and origin": "İsim, Yaş ve Memleket",
        "name, age and origin": "İsim, Yaş ve Memleket",
        "age and origin": "Yaş ve Memleket",
        "name and age": "İsim ve Yaş",
        
        # Numbers & quantities
        "numbers and essential quantities": "Sayılar ve Temel Miktarlar",
        "numbers and basic math": "Sayılar ve Temel Matematik",
        "numbers and quantities": "Sayılar ve Miktarlar",
        "essential quantities": "Temel Miktarlar",
        "basic quantities": "Temel Miktarlar",
        "counting and numbers": "Sayma ve Sayılar",
        "telling time": "Zamanı Söyleme",
        "prices and time": "Fiyatlar ve Zaman",
        "days, months, and seasons": "Günler, Aylar ve Mevsimler",
        "days of the week": "Haftanın Günleri",
        "months of the year": "Yılın Ayları",
        
        # Questions & sentences
        "formulating simple questions": "Basit Sorular Oluşturma",
        "formulating questions": "Soru Cümleleri Oluşturma",
        "formulating yes/no questions": "Evet/Hayır Soruları Oluşturma",
        "yes/no and wh- questions": "Evet/Hayır ve Wh- Soruları",
        "yes/no questions": "Evet/Hayır Soruları",
        "wh- questions": "Wh- Soruları (Soru Kelimeleri)",
        "asking questions and seeking clarifications": "Soru Sorma ve Açıklama İsteme",
        "asking questions": "Soru Sorma",
        "seeking clarifications": "Açıklama İsteme",
        "question words": "Soru Kelimeleri",
        "who, what, where, when, why": "Kim, Ne, Nerede, Ne Zaman, Neden",
        "constructing simple sentences": "Basit Cümleler Kurma",
        "simple sentences": "Basit Cümleler",
        
        # Politeness & help
        "polite ways to ask for help or information": "Yardım veya Bilgi İstemek İçin Nezaket İfadeleri",
        "polite ways to ask for help": "Yardım İstemek İçin Nezaket İfadeleri",
        "ask for help or information": "Yardım veya Bilgi İsteme",
        "asking for help": "Yardım İsteme",
        "polite expressions": "Nezaket İfadeleri",
        
        # Culture
        "cultural contexts": "Kültürel Bağlamlar",
        "cultural insights": "Kültürel İçgörüler",
        "cultural perspective": "Kültürel Bakış Açısı",
        "cultural perspectives": "Kültürel Bakış Açıları",
        "spanish-speaking countries": "İspanyolca Konuşulan Ülkeler",
        "spanish-speaking world": "İspanyolca Konuşulan Dünya",
        "german-speaking countries": "Almanca Konuşulan Ülkeler",
        "german-speaking world": "Almanca Konuşulan Dünya",
        "french-speaking countries": "Fransızca Konuşulan Ülkeler",
        "geography and major cities": "Coğrafya ve Başlıca Şehirler",
        "celebrations and traditions": "Kutlamalar ve Gelenekler",
        "traditions and customs": "Gelenekler ve Görenekler",
        "festivals and holidays": "Festivaller ve Tatiller",
        
        # Grammar & verbs
        "alphabet and foundations": "Alfabe ve Temeller",
        "the alphabet and foundations": "Alfabe ve Temeller",
        "the alphabet": "Alfabe",
        "vowels and consonants": "Sesli ve Sessiz Harfler",
        "pronunciation and phonetics": "Telaffuz ve Fonetik",
        "present tense": "Geniş Zaman",
        "present tense conjugation": "Geniş Zaman Çekimi",
        "past tense": "Geçmiş Zaman",
        "future tense": "Gelecek Zaman",
        "regular verbs": "Düzenli Fiiller",
        "irregular verbs": "Düzensiz Fiiller",
        "common irregular verbs": "Yaygın Düzensiz Fiiller",
        "stem-changing verbs": "Kök Değiştiren Fiiller",
        "reflexive verbs": "Dönüşlü Fiiller",
        "subject-verb agreement": "Özne-Yüklem Uyumu",
        
        # Situations & survival
        "everyday survival vocabulary": "Günlük Hayatta Kalma Kelimeleri",
        "survival vocabulary": "Hayatta Kalma Kelimeleri",
        "daily routines": "Günlük Rutinler",
        "food and dining": "Yiyecek ve Yemek",
        "shopping essentials": "Alışveriş Temelleri",
        "emergency situations": "Acil Durumlar",
        "public transportation": "Toplu Taşıma",
        "directions and transportation": "Yol Tarifi ve Ulaşım",
        "weather and seasons": "Hava Durumu ve Mevsimler",
    }

    VOCABULARY = {
        # Nouns
        "alphabet": "Alfabe",
        "vowels": "Sesli Harfler",
        "consonants": "Sessiz Harfler",
        "pronunciation": "Telaffuz",
        "phonetics": "Fonetik",
        "numbers": "Sayılar",
        "quantities": "Miktarlar",
        "quantity": "Miktar",
        "greetings": "Selamlaşmalar",
        "farewells": "Vedalaşmalar",
        "introductions": "Tanıtımlar",
        "information": "Bilgiler",
        "name": "İsim",
        "age": "Yaş",
        "origin": "Memleket / Köken",
        "nationality": "Milliyet",
        "questions": "Sorular",
        "question": "Soru",
        "answers": "Cevaplar",
        "answer": "Cevap",
        "sentences": "Cümleler",
        "sentence": "Cümle",
        "words": "Kelimeler",
        "word": "Kelime",
        "vocabulary": "Kelime Bilgisi",
        "phrases": "İfadeler",
        "phrase": "İfade",
        "expressions": "İfadeler",
        "grammar": "Dilbilgisi",
        "verbs": "Fiiller",
        "verb": "Fiil",
        "nouns": "İsimler",
        "noun": "İsim",
        "adjectives": "Sıfatlar",
        "adjective": "Sıfat",
        "adverbs": "Zarflar",
        "pronouns": "Zamirler",
        "prepositions": "Edatlar",
        "tenses": "Zamanlar",
        "tense": "Zaman",
        "conjugation": "Çekim",
        "days": "Günler",
        "months": "Aylar",
        "seasons": "Mevsimler",
        "weather": "Hava Durumu",
        "time": "Zaman",
        "prices": "Fiyatlar",
        "price": "Fiyat",
        "family": "Aile",
        "routines": "Rutinler",
        "routine": "Rutin",
        "activities": "Aktiviteler",
        "food": "Yiyecek",
        "drinks": "İçecekler",
        "meals": "Öğünler",
        "restaurant": "Restoran",
        "shopping": "Alışveriş",
        "clothes": "Kıyafetler",
        "clothing": "Giyim",
        "colors": "Renkler",
        "places": "Yerler",
        "cities": "Şehirler",
        "city": "Şehir",
        "countries": "Ülkeler",
        "country": "Ülke",
        "world": "Dünya",
        "geography": "Coğrafya",
        "traditions": "Gelenekler",
        "celebrations": "Kutlamalar",
        "customs": "Görenekler",
        "culture": "Kültür",
        "contexts": "Bağlamlar",
        "context": "Bağlam",
        "health": "Sağlık",
        "doctor": "Doktor",
        "body": "Vücut",
        "emergency": "Acil Durum",
        "emergencies": "Acil Durumlar",
        "directions": "Yol Tarifi",
        "transportation": "Ulaşım",
        "travel": "Seyahat",
        "hotel": "Otel",
        "airport": "Havalimanı",
        "hobbies": "Hobiler",
        "work": "İş",
        "jobs": "Meslekler",
        
        # Adjectives
        "basic": "Temel",
        "essential": "Temel",
        "simple": "Basit",
        "common": "Yaygın",
        "regular": "Düzenli",
        "irregular": "Düzensiz",
        "polite": "Kibar / Nezaket",
        "personal": "Kişisel",
        "daily": "Günlük",
        "cultural": "Kültürel",
        "practical": "Pratik",
        "structural": "Yapısal",
        "major": "Başlıca",
        "traditional": "Geleneksel",
        "new": "Yeni",
        "important": "Önemli",
        "useful": "Yararlı",
        "key": "Temel / Anahtar",
        "everyday": "Günlük",
        "general": "Genel",
        "elementary": "Başlangıç",
        "advanced": "İleri",
        "intermediate": "Orta Düzey",
        "occupation": "Meslek",
        "occupations": "Meslekler",
        "profession": "Meslek",
        "professions": "Meslekler",
        "festivals": "Festivaller",
        "festival": "Festival",
        "case": "İsmin Hâli",
        "cases": "İsmin Halleri",
        "nominative": "Yalın Hâl (Nominativ)",
        "accusative": "Belirtme Hâli (Akkusativ)",
        "dative": "Yönelme Hâli (Dativ)",
        "genitive": "Tamlayan Hâli (Genitiv)",
        
        # Verbs / Actions
        "asking": "Sorma",
        "answering": "Cevaplama",
        "sharing": "Paylaşma",
        "formulating": "Oluşturma",
        "constructing": "Kurma",
        "building": "Oluşturma",
        "introducing": "Tanıtma",
        "describing": "Tanımlama",
        "expressing": "İfade Etme",
        "navigating": "Yol Bulma",
        "ordering": "Sipariş Verme",
        "shopping": "Alışveriş Yapma",
        "talking": "Konuşma",
        "using": "Kullanma",
        "exploring": "Keşfetme",
        "mastering": "Uzmanlaşma",
        "understanding": "Anlama",
        "practicing": "Pratik Yapma",
        "reviewing": "Tekrar Etme",
        "counting": "Sayma",
        "making": "Yapma",
        "giving": "Verme",
    }

    @classmethod
    def clean_hybrids(cls, text: str) -> str:
        if not text:
            return ""
        t = str(text).strip()
        hybrids = [
            (r'Dünya\s+Around\s+Us', 'Çevremizdeki Dünya'),
            (r'the\s+world\s+around\s+us', 'Çevremizdeki Dünya'),
            (r'world\s+around\s+us', 'Çevremizdeki Dünya'),
            (r'around\s+us', 'Çevremizdeki'),
            (r'\bDaily\s+Objects\b', 'Günlük Eşyalar'),
            (r'\bGünlük\s+Objects\b', 'Günlük Eşyalar'),
            (r'\bobjects\b', 'Eşyalar'),
            (r'\bAile\s+ve\s+Friends\s+ve\s+(?:ve\s+)?Relationships\b', 'Aile, Arkadaşlar ve İlişkiler'),
            (r'\bFamily[,\s]+Friends[,\s]+(?:and\s+)?Relationships\b', 'Aile, Arkadaşlar ve İlişkiler'),
            (r'\bfriends\b', 'Arkadaşlar'),
            (r'\brelationships\b', 'İlişkiler'),
            (r'Temel\s+Social\s+Situations[\'’]?de\s+Yol\s+Bulma', 'Temel Sosyal Durumlarda İletişim'),
            (r'Social\s+Situations[\'’]?de\s+Yol\s+Bulma', 'Sosyal Durumlarda İletişim'),
            (r'\bNavigating\s+Basic\s+Social\s+Situations\b', 'Temel Sosyal Durumlarda İletişim'),
            (r'\bBasic\s+Social\s+Situations\b', 'Temel Sosyal Durumlar'),
            (r'\bSocial\s+Situations\b', 'Sosyal Durumlar'),
            (r'\bTraveling\s+Basics\b', 'Seyahat Temelleri'),
            (r'\bTravel\s+Basics\b', 'Seyahat Temelleri'),
            (r'Dışarıda\s+Yemek\s+Yeme', 'Dışarıda Yemek'),
            (r'\bDining\s+Out\b', 'Dışarıda Yemek'),
            (r'\bEating\s+Out\b', 'Dışarıda Yemek'),
        ]
        for pat, repl in hybrids:
            t = re.sub(pat, repl, t, flags=re.IGNORECASE)
        t = re.sub(r'\bve\s+ve\b', 've', t, flags=re.IGNORECASE)
        t = re.sub(r'\bve\s+ve\b', 've', t, flags=re.IGNORECASE)
        t = re.sub(r'\bveya\s+veya\b', 'veya', t, flags=re.IGNORECASE)
        t = re.sub(r',\s*ve\b', ' ve', t, flags=re.IGNORECASE)
        t = re.sub(r'\s{2,}', ' ', t).strip()
        return t

    @classmethod
    def translate(cls, title: str) -> str:
        if not title:
            return ""
        
        t = str(title).strip()
        # Clean prefix: "Unit 1: ", "Ünite 2: ", etc.
        clean = re.sub(r'^(unit|chapter|topic|tema|lektion|item|ünite|unite|bölüm|bolum|c\.|l\.)\s*\d+\s*[:\-]\s*', '', t, flags=re.IGNORECASE).strip()
        
        # Clean hybrid fragments immediately
        clean = cls.clean_hybrids(clean)
        low = clean.lower()

        # Check if already pure Turkish (must not have remaining English keywords)
        english_words = r'\b(around|us|objects?|friends?|relationships?|social|situations?|traveling|basics?|getting|acquainted|with|greetings?|farewells?|who|are|you|sharing|personal|information|formulating|simple|questions?|essential|quantities|numbers?|present|tense|asking|seeking|clarifications?|cultural|contexts?|countries|world|geography|major|cities|celebrations?|traditions?|polite|ways?|dining|eating|out)\b'
        if re.search(r'[çğıöşüÇĞİÖŞÜ]', clean) and not re.search(english_words, clean, re.IGNORECASE):
            m_half = re.match(r"^(\d+)'den\s+(\d+)'(?:ye|e)\s+sayma\s*[:\-]\s*(.*)$", clean, re.IGNORECASE)
            if m_half:
                n1, n2, rest = m_half.group(1), m_half.group(2), m_half.group(3).strip()
                return cls.clean_hybrids(f"{n1}'den {n2}'e Sayma: {cls.translate(rest)}")
            return cls.clean_hybrids(clean)

        # Check title map from bilingual_materials.json
        tmap = _get_bm_title_map()
        if t in tmap:
            return tmap[t]
        if clean in tmap:
            return tmap[clean]
        for k, v in tmap.items():
            if k.lower() == low:
                return v

        # Direct exact match in phrase dictionary
        if low in cls.PHRASES:
            return cls.PHRASES[low]

        # Handle colon compound "A: B"
        if ":" in clean:
            parts = [p.strip() for p in clean.split(":", 1)]
            p1 = cls.translate(parts[0])
            p2 = cls.translate(parts[1])
            return f"{p1}: {p2}"

        # Handle "A vs. B" or "A versus B"
        m_vs = re.match(r'^(.*?)\s+(?:vs\.?|versus)\s+(.*)$', clean, re.IGNORECASE)
        if m_vs:
            s1 = cls.translate(m_vs.group(1).strip())
            s2 = cls.translate(m_vs.group(2).strip())
            return f"{s1} ve {s2} Karşılaştırması"

        # Handle "Getting Acquainted with (the\s+)?(Language/Topic)"
        m_acq = re.match(r'^getting\s+acquainted\s+with\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_acq:
            sub = m_acq.group(2).strip()
            sub_clean = re.sub(r'\s+language$', '', sub, flags=re.IGNORECASE).strip().lower()
            if sub_clean in cls.LANGUAGES:
                lang_name = cls.LANGUAGES[sub_clean][0]
                return f"{lang_name} ile Tanışma"
            sub_tr = cls.translate(sub)
            return f"{sub_tr} ile Tanışma"

        # Handle "How to Ask and Answer 'X'" or "How to Ask and Answer X"
        m_ask_ans = re.match(r'^how\s+to\s+ask\s+and\s+answer\s+[\'"]?(.*?)[\'"]?$', clean, re.IGNORECASE)
        if m_ask_ans:
            sub = m_ask_ans.group(1).strip()
            sub_low = sub.lower()
            if sub_low in cls.QUOTED_EXPRESSIONS:
                sub_tr = cls.QUOTED_EXPRESSIONS[sub_low]
                return f"'{sub_tr}' Diye Sorma ve Cevaplama"
            return f"'{sub}' Diye Sorma ve Cevaplama"

        # Handle "How to (Verb) (X)"
        m_howto = re.match(r'^how\s+to\s+(.*?)\s+(.*)$', clean, re.IGNORECASE)
        if m_howto:
            verb = m_howto.group(1).strip()
            rest = m_howto.group(2).strip()
            rest_tr = cls.translate(rest)
            verb_tr = cls.VOCABULARY.get(verb.lower(), verb)
            return f"{rest_tr} {verb_tr} Yolları"

        # Handle "Sharing (X)"
        m_sharing = re.match(r'^sharing\s+(.*)$', clean, re.IGNORECASE)
        if m_sharing:
            sub = m_sharing.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Paylaşma"

        # Handle "Exploring (X)"
        m_exp = re.match(r'^exploring\s+(.*)$', clean, re.IGNORECASE)
        if m_exp:
            sub = m_exp.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Keşfetme"

        # Handle "Mastering (X)"
        m_mas = re.match(r'^mastering\s+(.*)$', clean, re.IGNORECASE)
        if m_mas:
            sub = m_mas.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Konusunda Uzmanlaşma"

        # Handle "Formulating (X) Questions"
        m_form_q = re.match(r'^formulating\s+(.*?)\s+questions$', clean, re.IGNORECASE)
        if m_form_q:
            sub = m_form_q.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Soruları Oluşturma"

        # Handle "Formulating (X)"
        m_form = re.match(r'^formulating\s+(.*)$', clean, re.IGNORECASE)
        if m_form:
            sub = m_form.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Oluşturma"

        # Handle "Constructing (X) in (the\s+)?(Y)"
        m_const_in = re.match(r'^constructing\s+(.*?)\s+in\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_const_in:
            s1 = cls.translate(m_const_in.group(1).strip())
            s2 = cls.translate(m_const_in.group(3).strip())
            return f"{s2}'de {s1} Kurma"

        # Handle "Constructing (X)"
        m_const = re.match(r'^constructing\s+(.*)$', clean, re.IGNORECASE)
        if m_const:
            sub = m_const.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Kurma"

        # Handle "Polite Ways to (X)"
        m_polite = re.match(r'^polite\s+ways\s+to\s+(.*)$', clean, re.IGNORECASE)
        if m_polite:
            sub = m_polite.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} İçin Nezaket İfadeleri"

        # Handle "Geography and Major Cities of (the\s+)?(X)"
        m_geo = re.match(r'^geography\s+and\s+major\s+cities\s+of\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_geo:
            sub = m_geo.group(2).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr} Coğrafyası ve Başlıca Şehirleri"

        # Handle "Celebrations and Traditions in (the\s+)?(X)"
        m_cel = re.match(r'^celebrations\s+and\s+traditions\s+in\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_cel:
            sub = m_cel.group(2).strip()
            sub_tr = cls.translate(sub)
            return f"{sub_tr}'de Kutlamalar ve Gelenekler"

        # Handle "Cultural Contexts: (X)" or "Cultural Contexts of (X)"
        m_cult = re.match(r'^cultural\s+contexts?\s*(?:of|in)?\s*(.*)$', clean, re.IGNORECASE)
        if m_cult and m_cult.group(1).strip():
            sub = m_cult.group(1).strip()
            sub_tr = cls.translate(sub)
            return f"Kültürel Bağlamlar: {sub_tr}"

        # Handle "Counting from (N1) to (N2)"
        m_count = re.match(r'^counting\s+from\s+(\d+)\s+to\s+(\d+)(.*)$', clean, re.IGNORECASE)
        if m_count:
            n1, n2, extra = m_count.group(1), m_count.group(2), m_count.group(3).strip()
            suffix = "e" if n2.endswith("00") or n2 in ["1", "3", "4", "5", "8", "70", "80"] else "a"
            res = f"{n1}'den {n2}'{suffix} Sayma"
            extra_clean = re.sub(r'^[:\s\-]+', '', extra).strip()
            if extra_clean:
                res += f": {cls.translate(extra_clean)}"
            return res

        # Handle "Introduction to (X)"
        m_intro = re.match(r'^introduction\s+to\s+(.*)$', clean, re.IGNORECASE)
        if m_intro:
            sub = cls.translate(m_intro.group(1).strip())
            return sub if sub.endswith("Giriş") else f"{sub}'e Giriş"

        # Handle "Using (X) in (Y)"
        m_using_in = re.match(r'^using\s+(.*?)\s+in\s+(.*)$', clean, re.IGNORECASE)
        if m_using_in:
            s1 = cls.translate(m_using_in.group(1).strip())
            s2 = cls.translate(m_using_in.group(2).strip())
            return f"{s2}'de {s1} Kullanımı"

        # Handle "Using (X)"
        m_using = re.match(r'^using\s+(.*)$', clean, re.IGNORECASE)
        if m_using:
            sub = cls.translate(m_using.group(1).strip())
            return f"{sub} Kullanımı"

        # Handle "Talking About (X)"
        m_talking = re.match(r'^talking\s+about\s+(.*)$', clean, re.IGNORECASE)
        if m_talking:
            sub = cls.translate(m_talking.group(1).strip())
            return f"{sub} Hakkında Konuşma"

        # Handle "Navigating (X)"
        m_nav = re.match(r'^navigating\s+(.*)$', clean, re.IGNORECASE)
        if m_nav:
            sub = cls.translate(m_nav.group(1).strip())
            return f"{sub}'de Yol Bulma"

        # Handle "X for Y"
        m_for = re.match(r'^(.*?)\s+for\s+(.*)$', clean, re.IGNORECASE)
        if m_for:
            s1 = cls.translate(m_for.group(1).strip())
            s2 = cls.translate(m_for.group(2).strip())
            if s1.lower() != m_for.group(1).strip().lower() or s2.lower() != m_for.group(2).strip().lower():
                return f"{s2} İçin {s1}"

        # Handle "X in [Language]"
        for lang_en, (lang_nom, lang_adj, lang_loc) in cls.LANGUAGES.items():
            m_lang = re.match(rf'^(.*?)\s+in\s+{lang_en}$', clean, re.IGNORECASE)
            if m_lang:
                sub = m_lang.group(1).strip()
                sub_tr = cls.translate(sub)
                return f"{lang_loc} {sub_tr}"

        # Handle "X and Y" conjunction
        if " and " in clean.lower():
            parts = re.split(r'\s+and\s+', clean, flags=re.IGNORECASE)
            if len(parts) == 2:
                p1 = cls.translate(parts[0].strip())
                p2 = cls.translate(parts[1].strip())
                return f"{p1} ve {p2}"

        # Handle comma-separated list "A, B, and C" or "A, B, C"
        if "," in clean:
            raw_items = re.split(r',\s*(?:and\s+)?', clean)
            if len(raw_items) > 1:
                tr_items = [cls.translate(item.strip()) for item in raw_items]
                if len(tr_items) == 2:
                    return f"{tr_items[0]} ve {tr_items[1]}"
                return ", ".join(tr_items[:-1]) + f" ve {tr_items[-1]}"

        # Check Language + Noun (e.g. "German Language", "Spanish Alphabet")
        for lang_en, (lang_nom, lang_adj, lang_loc) in cls.LANGUAGES.items():
            if low == f"the {lang_en} language" or low == f"{lang_en} language":
                return f"{lang_nom} Dili"
            m_lang_noun = re.match(rf'^{lang_en}\s+(.*)$', clean, re.IGNORECASE)
            if m_lang_noun:
                sub = m_lang_noun.group(1).strip()
                sub_tr = cls.translate(sub)
                return f"{lang_adj} {sub_tr}"

        # Check Adjective + Noun (e.g. "Basic Greetings", "Essential Quantities")
        words = clean.split()
        if len(words) == 2:
            w1 = words[0].lower()
            w2 = words[1].lower()
            if w1 in cls.VOCABULARY and w2 in cls.VOCABULARY:
                return f"{cls.VOCABULARY[w1]} {cls.VOCABULARY[w2]}"

        # Word-by-word tokenized fallback
        translated_words = []
        for w in words:
            w_low = w.lower().strip(".,!?:;")
            if w_low in cls.VOCABULARY:
                translated_words.append(cls.VOCABULARY[w_low])
            elif w_low in cls.LANGUAGES:
                translated_words.append(cls.LANGUAGES[w_low][0])
            elif w_low == "and":
                translated_words.append("ve")
            elif w_low == "or":
                translated_words.append("veya")
            elif w_low == "the":
                continue
            elif w_low == "with":
                translated_words.append("ile")
            else:
                translated_words.append(w)

        res = " ".join(translated_words)
        return res if res else clean


def resolve_curriculum_tr(title: str, current_tr: str = None) -> str:
    """Translates educational curriculum titles (chapters/topics) into natural, grammatically correct Turkish."""
    from services.curriculum_translator import is_clean_turkish, translate_titles_batch

    # If current_tr is already clean Turkish, keep it
    if current_tr and current_tr.strip() and current_tr != "Alfabeyi" and current_tr != title:
        if is_clean_turkish(current_tr):
            return current_tr.strip()

    target = title or current_tr or ""
    if not target or not target.strip():
        return ""

    res = translate_titles_batch([target.strip()], target_lang="tr")
    return res.get(target.strip()) or target.strip()



