# Standard Reference Data for Alphabets and Phonemes
# Used to "teach" the AI exactly what to include for foundational lessons.

ALPHABETS = {
    "Chinese": {
        "type": "Pinyin Initials and Finals",
        "sets": [
            {
                "title": "Pinyin Initials (Consonants)",
                "items": [
                    {"term": "b", "translation": "sounds like 'b' in boy"},
                    {"term": "p", "translation": "sounds like 'p' in pan (aspirated)"},
                    {"term": "m", "translation": "sounds like 'm' in mother"},
                    {"term": "f", "translation": "sounds like 'f' in fan"},
                    {"term": "d", "translation": "sounds like 'd' in dog"},
                    {"term": "t", "translation": "sounds like 't' in top (aspirated)"},
                    {"term": "n", "translation": "sounds like 'n' in no"},
                    {"term": "l", "translation": "sounds like 'l' in love"},
                    {"term": "g", "translation": "sounds like 'g' in go"},
                    {"term": "k", "translation": "sounds like 'k' in kite (aspirated)"},
                    {"term": "h", "translation": "sounds like 'h' in hay"},
                    {"term": "j", "translation": "sounds like 'j' in jeep"},
                    {"term": "q", "translation": "sounds like 'ch' in cheese (aspirated)"},
                    {"term": "x", "translation": "sounds like 'sh' in she"},
                    {"term": "zh", "translation": "sounds like 'j' in judge (retroflex)"},
                    {"term": "ch", "translation": "sounds like 'ch' in church (retroflex, aspirated)"},
                    {"term": "sh", "translation": "sounds like 'sh' in shoe (retroflex)"},
                    {"term": "r", "translation": "sounds like 'r' in measure (retroflex)"},
                    {"term": "z", "translation": "sounds like 'ds' in kids"},
                    {"term": "c", "translation": "sounds like 'ts' in cats (aspirated)"},
                    {"term": "s", "translation": "sounds like 's' in sun"},
                    {"term": "y", "translation": "sounds like 'y' in yes"},
                    {"term": "w", "translation": "sounds like 'w' in way"}
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
    }
}

def get_reference_prompt(language):
    data = ALPHABETS.get(language)
    if not data:
        return ""
    
    return f"\nREFERENCE DATA for {language} {data['type']}:\n{json.dumps(data, ensure_ascii=False)}\nUse this data as the absolute ground truth for your vocabulary pages. Do not skip any entries."
