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
            {"term": "P", "translation": "pe"}, {"term": "Q", "translation": "qu"}, {"term": "R", "translation": "er"}, {"term": "S", "translation": "es"}, {"term": "T", "translation": "te"},
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

def get_reference_prompt(language):
    data = ALPHABETS.get(language)
    if not data:
        return ""
    
    return f"\nREFERENCE DATA for {language} {data['type']}:\n{json.dumps(data, ensure_ascii=False)}\nUse this data as the absolute ground truth for your vocabulary pages. Do not skip any entries."
