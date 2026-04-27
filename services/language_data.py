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
    }
}

def get_reference_prompt(language):
    data = ALPHABETS.get(language)
    if not data:
        return ""
    
    return f"\nREFERENCE DATA for {language} {data['type']}:\n{json.dumps(data, ensure_ascii=False)}\nUse this data as the absolute ground truth for your vocabulary pages. Do not skip any entries."
