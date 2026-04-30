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
