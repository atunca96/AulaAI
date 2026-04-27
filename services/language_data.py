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
                    {"term": "爸", "translation": "b - sounds like 'b' in boy (Father)"},
                    {"term": "婆", "translation": "p - sounds like 'p' in pan (Grandmother)"},
                    {"term": "妈", "translation": "m - sounds like 'm' in mother (Mother)"},
                    {"term": "父", "translation": "f - sounds like 'f' in fan (Father)"},
                    {"term": "大", "translation": "d - sounds like 'd' in dog (Big)"},
                    {"term": "他", "translation": "t - sounds like 't' in top (He)"},
                    {"term": "你", "translation": "n - sounds like 'n' in no (You)"},
                    {"term": "六", "translation": "l - sounds like 'l' in love (Six)"},
                    {"term": "哥", "translation": "g - sounds like 'g' in go (Older brother)"},
                    {"term": "口", "translation": "k - sounds like 'k' in kite (Mouth)"},
                    {"term": "好", "translation": "h - sounds like 'h' in hay (Good)"},
                    {"term": "几", "translation": "j - sounds like 'j' in jeep (How many)"},
                    {"term": "七", "translation": "q - sounds like 'ch' in cheese (Seven)"},
                    {"term": "下", "translation": "x - sounds like 'sh' in she (Down)"},
                    {"term": "中", "translation": "zh - sounds like 'j' in judge (Middle)"},
                    {"term": "吃", "translation": "ch - sounds like 'ch' in church (Eat)"},
                    {"term": "是", "translation": "sh - sounds like 'sh' in shoe (To be)"},
                    {"term": "人", "translation": "r - sounds like 'r' in measure (Person)"},
                    {"term": "子", "translation": "z - sounds like 'ds' in kids (Child)"},
                    {"term": "才", "translation": "c - sounds like 'ts' in cats (Talent)"},
                    {"term": "三", "translation": "s - sounds like 's' in sun (Three)"},
                    {"term": "一", "translation": "y - sounds like 'y' in yes (One)"},
                    {"term": "五", "translation": "w - sounds like 'w' in way (Five)"}
                ]
            },
            {
                "title": "Pinyin Finals (Vowels)",
                "items": [
                    {"term": "啊", "translation": "a - sounds like 'ah'"},
                    {"term": "哦", "translation": "o - sounds like 'oh'"},
                    {"term": "饿", "translation": "e - sounds like 'uh'"},
                    {"term": "衣", "translation": "i - sounds like 'ee'"},
                    {"term": "五", "translation": "u - sounds like 'oo'"},
                    {"term": "鱼", "translation": "ü - sounds like 'yu' (rounded lips)"}
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
                    {"term": "あ", "translation": "a - sounds like 'ah'"},
                    {"term": "い", "translation": "i - sounds like 'ee'"},
                    {"term": "う", "translation": "u - sounds like 'oo'"},
                    {"term": "え", "translation": "e - sounds like 'eh'"},
                    {"term": "お", "translation": "o - sounds like 'oh'"},
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
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "beh"}, {"term": "C", "translation": "ceh"}, {"term": "D", "translation": "deh"}, {"term": "E", "translation": "eh"}, 
            {"term": "F", "translation": "eh-feh"}, {"term": "G", "translation": "heh"}, {"term": "H", "translation": "ah-cheh"}, {"term": "I", "translation": "ee"}, {"term": "J", "translation": "ho-tah"},
            {"term": "K", "translation": "kah"}, {"term": "L", "translation": "eh-leh"}, {"term": "M", "translation": "eh-meh"}, {"term": "N", "translation": "eh-neh"}, {"term": "Ñ", "translation": "eh-nyeh"},
            {"term": "O", "translation": "oh"}, {"term": "P", "translation": "peh"}, {"term": "Q", "translation": "koo"}, {"term": "R", "translation": "eh-reh"}, {"term": "S", "translation": "eh-seh"},
            {"term": "T", "translation": "teh"}, {"term": "U", "translation": "oo"}, {"term": "V", "translation": "veh"}, {"term": "W", "translation": "oobleh-veh"}, {"term": "X", "translation": "eh-kees"},
            {"term": "Y", "translation": "ee-gryeh-gah"}, {"term": "Z", "translation": "seh-tah"}
        ]
    },
    "French": {
        "type": "Alphabet",
        "items": [
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "beh"}, {"term": "C", "translation": "seh"}, {"term": "D", "translation": "deh"}, {"term": "E", "translation": "uh"}, 
            {"term": "F", "translation": "eff"}, {"term": "G", "translation": "zheh"}, {"term": "H", "translation": "ash"}, {"term": "I", "translation": "ee"}, {"term": "J", "translation": "zhee"},
            {"term": "K", "translation": "kah"}, {"term": "L", "translation": "ell"}, {"term": "M", "translation": "emm"}, {"term": "N", "translation": "enn"}, {"term": "O", "translation": "oh"},
            {"term": "P", "translation": "peh"}, {"term": "Q", "translation": "ku"}, {"term": "R", "translation": "air"}, {"term": "S", "translation": "ess"}, {"term": "T", "translation": "teh"},
            {"term": "U", "translation": "u (rounded lips)"}, {"term": "V", "translation": "veh"}, {"term": "W", "translation": "doobleh-veh"}, {"term": "X", "translation": "eeks"},
            {"term": "Y", "translation": "ee-greck"}, {"term": "Z", "translation": "zed"}
        ]
    },
    "German": {
        "type": "Alphabet",
        "items": [
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "beh"}, {"term": "C", "translation": "tseh"}, {"term": "D", "translation": "deh"}, {"term": "E", "translation": "eh"}, 
            {"term": "F", "translation": "eff"}, {"term": "G", "translation": "geh"}, {"term": "H", "translation": "hah"}, {"term": "I", "translation": "ee"}, {"term": "J", "translation": "yot"},
            {"term": "K", "translation": "kah"}, {"term": "L", "translation": "ell"}, {"term": "M", "translation": "emm"}, {"term": "N", "translation": "enn"}, {"term": "O", "translation": "oh"},
            {"term": "P", "translation": "peh"}, {"term": "Q", "translation": "koo"}, {"term": "R", "translation": "err"}, {"term": "S", "translation": "ess"}, {"term": "T", "translation": "teh"},
            {"term": "U", "translation": "oo"}, {"term": "V", "translation": "fow"}, {"term": "W", "translation": "veh"}, {"term": "X", "translation": "iks"}, {"term": "Y", "translation": "ypsilon"}, {"term": "Z", "translation": "tset"},
            {"term": "Ä", "translation": "ae"}, {"term": "Ö", "translation": "oe"}, {"term": "Ü", "translation": "ue"}, {"term": "ß", "translation": "ess-tset"}
        ]
    },
    "Turkish": {
        "type": "Alfabe",
        "items": [
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "beh"}, {"term": "C", "translation": "djeh"}, {"term": "Ç", "translation": "cheh"}, {"term": "D", "translation": "deh"},
            {"term": "E", "translation": "eh"}, {"term": "F", "translation": "feh"}, {"term": "G", "translation": "geh"}, {"term": "Ğ", "translation": "yumuşak geh (silent)"}, {"term": "H", "translation": "heh"},
            {"term": "I", "translation": "uh"}, {"term": "İ", "translation": "ee"}, {"term": "J", "translation": "zheh"}, {"term": "K", "translation": "keh"}, {"term": "L", "translation": "leh"},
            {"term": "M", "translation": "meh"}, {"term": "N", "translation": "neh"}, {"term": "O", "translation": "oh"}, {"term": "Ö", "translation": "ur (rounded)"}, {"term": "P", "translation": "peh"},
            {"term": "R", "translation": "reh"}, {"term": "S", "translation": "seh"}, {"term": "Ş", "translation": "sheh"}, {"term": "T", "translation": "teh"}, {"term": "U", "translation": "oo"},
            {"term": "Ü", "translation": "ew (rounded)"}, {"term": "V", "translation": "veh"}, {"term": "Y", "translation": "yeh"}, {"term": "Z", "translation": "zeh"}
        ]
    },
    "Italian": {
        "type": "Alfabeto",
        "items": [
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "bee"}, {"term": "C", "translation": "chee"}, {"term": "D", "translation": "dee"}, {"term": "E", "translation": "eh"},
            {"term": "F", "translation": "effe"}, {"term": "G", "translation": "dzhee"}, {"term": "H", "translation": "akka"}, {"term": "I", "translation": "ee"}, {"term": "L", "translation": "elle"},
            {"term": "M", "translation": "emme"}, {"term": "N", "translation": "enne"}, {"term": "O", "translation": "oh"}, {"term": "P", "translation": "pee"}, {"term": "Q", "translation": "koo"},
            {"term": "R", "translation": "erre"}, {"term": "S", "translation": "esse"}, {"term": "T", "translation": "tee"}, {"term": "U", "translation": "oo"}, {"term": "V", "translation": "voo"}, {"term": "Z", "translation": "dzeta"}
        ]
    },
    "Portuguese": {
        "type": "Alfabeto",
        "items": [
            {"term": "A", "translation": "ah"}, {"term": "B", "translation": "beh"}, {"term": "C", "translation": "seh"}, {"term": "D", "translation": "deh"}, {"term": "E", "translation": "eh"},
            {"term": "F", "translation": "eh-feh"}, {"term": "G", "translation": "zheh"}, {"term": "H", "translation": "ah-gah"}, {"term": "I", "translation": "ee"}, {"term": "J", "translation": "zho-tah"},
            {"term": "K", "translation": "kah"}, {"term": "L", "translation": "eh-leh"}, {"term": "M", "translation": "eh-meh"}, {"term": "N", "translation": "eh-neh"}, {"term": "O", "translation": "oh"},
            {"term": "P", "translation": "peh"}, {"term": "Q", "translation": "keh"}, {"term": "R", "translation": "eh-heh"}, {"term": "S", "translation": "eh-seh"}, {"term": "T", "translation": "teh"},
            {"term": "U", "translation": "oo"}, {"term": "V", "translation": "veh"}, {"term": "W", "translation": "dah-bli-oo"}, {"term": "X", "translation": "shis"}, {"term": "Y", "translation": "ip-si-lon"}, {"term": "Z", "translation": "zeh"}
        ]
    },
    "Russian": {
        "type": "Cyrillic Alphabet",
        "items": [
            {"term": "А", "translation": "ah"}, {"term": "Б", "translation": "beh"}, {"term": "В", "translation": "veh"}, {"term": "Г", "translation": "geh"}, {"term": "Д", "translation": "deh"},
            {"term": "Е", "translation": "yeh"}, {"term": "Ё", "translation": "yo"}, {"term": "Ж", "translation": "zheh"}, {"term": "З", "translation": "zeh"}, {"term": "И", "translation": "ee"},
            {"term": "Й", "translation": "ee-kratkoye"}, {"term": "К", "translation": "kah"}, {"term": "Л", "translation": "ell"}, {"term": "М", "translation": "emm"}, {"term": "Н", "translation": "enn"},
            {"term": "О", "translation": "oh"}, {"term": "П", "translation": "peh"}, {"term": "Р", "translation": "err"}, {"term": "С", "translation": "ess"}, {"term": "Т", "translation": "teh"},
            {"term": "У", "translation": "oo"}, {"term": "Ф", "translation": "eff"}, {"term": "Х", "translation": "hah"}, {"term": "Ц", "translation": "tseh"}, {"term": "Ч", "translation": "cheh"},
            {"term": "Ш", "translation": "shah"}, {"term": "Щ", "translation": "sh-chah"}, {"term": "Ъ", "translation": "tvyordiy znak (hard sign)"}, {"term": "Ы", "translation": "ih"}, {"term": "Ь", "translation": "myagkiy znak (soft sign)"},
            {"term": "Э", "translation": "eh"}, {"term": "Ю", "translation": "yoo"}, {"term": "Я", "translation": "yah"}
        ]
    }
}

def get_reference_prompt(language):
    data = ALPHABETS.get(language)
    if not data:
        return ""
    
    return f"\nREFERENCE DATA for {language} {data['type']}:\n{json.dumps(data, ensure_ascii=False)}\nUse this data as the absolute ground truth for your vocabulary pages. Do not skip any entries."
