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
                    {"term": "b (爸)", "translation": "sounds like 'b' in boy (Ex: bà - father)"},
                    {"term": "p (婆)", "translation": "sounds like 'p' in pan (Ex: pó - grandmother)"},
                    {"term": "m (妈)", "translation": "sounds like 'm' in mother (Ex: mā - mother)"},
                    {"term": "f (父)", "translation": "sounds like 'f' in fan (Ex: fù - father)"},
                    {"term": "d (大)", "translation": "sounds like 'd' in dog (Ex: dà - big)"},
                    {"term": "t (他)", "translation": "sounds like 't' in top (Ex: tā - he)"},
                    {"term": "n (你)", "translation": "sounds like 'n' in no (Ex: nǐ - you)"},
                    {"term": "l (六)", "translation": "sounds like 'l' in love (Ex: liù - six)"},
                    {"term": "g (哥)", "translation": "sounds like 'g' in go (Ex: gē - older brother)"},
                    {"term": "k (口)", "translation": "sounds like 'k' in kite (Ex: kǒu - mouth)"},
                    {"term": "h (好)", "translation": "sounds like 'h' in hay (Ex: hǎo - good)"},
                    {"term": "j (几)", "translation": "sounds like 'j' in jeep (Ex: jǐ - how many)"},
                    {"term": "q (七)", "translation": "sounds like 'ch' in cheese (Ex: qī - seven)"},
                    {"term": "x (下)", "translation": "sounds like 'sh' in she (Ex: xià - down)"},
                    {"term": "zh (中)", "translation": "sounds like 'j' in judge (Ex: zhōng - middle)"},
                    {"term": "ch (吃)", "translation": "sounds like 'ch' in church (Ex: chī - eat)"},
                    {"term": "sh (是)", "translation": "sounds like 'sh' in shoe (Ex: shì - to be)"},
                    {"term": "r (人)", "translation": "sounds like 'r' in measure (Ex: rén - person)"},
                    {"term": "z (子)", "translation": "sounds like 'ds' in kids (Ex: zǐ - child)"},
                    {"term": "c (才)", "translation": "sounds like 'ts' in cats (Ex: cái - talent)"},
                    {"term": "s (三)", "translation": "sounds like 's' in sun (Ex: sān - three)"},
                    {"term": "y (一)", "translation": "sounds like 'y' in yes (Ex: yī - one)"},
                    {"term": "w (五)", "translation": "sounds like 'w' in way (Ex: wǔ - five)"}
                ]
            },
            {
                "title": "Pinyin Finals (Vowels)",
                "items": [
                    {"term": "a", "translation": "sounds like 'ah'"},
                    {"term": "o", "translation": "sounds like 'oh'"},
                    {"term": "e", "translation": "sounds like 'uh'"},
                    {"term": "i", "translation": "sounds like 'ee'"},
                    {"term": "u", "translation": "sounds like 'oo'"},
                    {"term": "ü", "translation": "sounds like 'yu' (rounded lips)"}
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
                    {"term": "あ (a)", "translation": "sounds like 'ah'"},
                    {"term": "い (i)", "translation": "sounds like 'ee'"},
                    {"term": "う (u)", "translation": "sounds like 'oo'"},
                    {"term": "え (e)", "translation": "sounds like 'eh'"},
                    {"term": "お (o)", "translation": "sounds like 'oh'"},
                    {"term": "か (ka)", "translation": "ka"},
                    {"term": "き (ki)", "translation": "ki"},
                    {"term": "く (ku)", "translation": "ku"},
                    {"term": "け (ke)", "translation": "ke"},
                    {"term": "こ (ko)", "translation": "ko"}
                ]
            },
            {
                "title": "Hiragana: S, T, N Groups",
                "items": [
                    {"term": "さ (sa)", "translation": "sa"}, {"term": "し (shi)", "translation": "shi"}, {"term": "す (su)", "translation": "su"}, {"term": "せ (se)", "translation": "se"}, {"term": "そ (so)", "translation": "so"},
                    {"term": "た (ta)", "translation": "ta"}, {"term": "ち (chi)", "translation": "chi"}, {"term": "つ (tsu)", "translation": "tsu"}, {"term": "て (te)", "translation": "te"}, {"term": "と (to)", "translation": "to"},
                    {"term": "な (na)", "translation": "na"}, {"term": "に (ni)", "translation": "ni"}, {"term": "ぬ (nu)", "translation": "nu"}, {"term": "ね (ne)", "translation": "ne"}, {"term": "の (no)", "translation": "no"}
                ]
            },
            {
                "title": "Hiragana: H, M, Y, R, W Groups",
                "items": [
                    {"term": "は (ha)", "translation": "ha"}, {"term": "ひ (hi)", "translation": "hi"}, {"term": "ふ (fu)", "translation": "fu"}, {"term": "へ (he)", "translation": "he"}, {"term": "ほ (ho)", "translation": "ho"},
                    {"term": "ま (ma)", "translation": "ma"}, {"term": "み (mi)", "translation": "mi"}, {"term": "む (mu)", "translation": "mu"}, {"term": "め (me)", "translation": "me"}, {"term": "も (mo)", "translation": "mo"},
                    {"term": "や (ya)", "translation": "ya"}, {"term": "ゆ (yu)", "translation": "yu"}, {"term": "よ (yo)", "translation": "yo"},
                    {"term": "ら (ra)", "translation": "ra"}, {"term": "り (ri)", "translation": "ri"}, {"term": "る (ru)", "translation": "ru"}, {"term": "れ (re)", "translation": "re"}, {"term": "ろ (ro)", "translation": "ro"},
                    {"term": "わ (wa)", "translation": "wa"}, {"term": "を (wo)", "translation": "wo"}, {"term": "ん (n)", "translation": "n"}
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
