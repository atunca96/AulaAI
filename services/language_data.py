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
                    {
                        "term": "b - 播",
                        "translation": "bō"
                    },
                    {
                        "term": "p - 泼",
                        "translation": "pō"
                    },
                    {
                        "term": "m - 摸",
                        "translation": "mō"
                    },
                    {
                        "term": "f - 佛",
                        "translation": "fó"
                    },
                    {
                        "term": "d - 得",
                        "translation": "de"
                    },
                    {
                        "term": "t - 特",
                        "translation": "te"
                    },
                    {
                        "term": "n - 呢",
                        "translation": "ne"
                    },
                    {
                        "term": "l - 勒",
                        "translation": "le"
                    },
                    {
                        "term": "g - 哥",
                        "translation": "gē"
                    },
                    {
                        "term": "k - 科",
                        "translation": "kē"
                    },
                    {
                        "term": "h - 喝",
                        "translation": "hē"
                    },
                    {
                        "term": "j - 鸡",
                        "translation": "jī"
                    },
                    {
                        "term": "q - 七",
                        "translation": "qī"
                    },
                    {
                        "term": "x - 西",
                        "translation": "xī"
                    },
                    {
                        "term": "zh - 知",
                        "translation": "zhī"
                    },
                    {
                        "term": "ch - 吃",
                        "translation": "chī"
                    },
                    {
                        "term": "sh - 狮",
                        "translation": "shī"
                    },
                    {
                        "term": "r - 日",
                        "translation": "rì"
                    },
                    {
                        "term": "z - 资",
                        "translation": "zī"
                    },
                    {
                        "term": "c - 刺",
                        "translation": "cì"
                    },
                    {
                        "term": "s - 丝",
                        "translation": "sī"
                    },
                    {
                        "term": "y - 衣",
                        "translation": "yī"
                    },
                    {
                        "term": "w - 屋",
                        "translation": "wū"
                    }
                ]
            },
            {
                "title": "Pinyin Finals (Vowels)",
                "items": [
                    {
                        "term": "啊",
                        "translation": "ā"
                    },
                    {
                        "term": "哦",
                        "translation": "ō"
                    },
                    {
                        "term": "饿",
                        "translation": "ē"
                    },
                    {
                        "term": "衣",
                        "translation": "ī"
                    },
                    {
                        "term": "五",
                        "translation": "ū"
                    },
                    {
                        "term": "鱼",
                        "translation": "ǘ"
                    }
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
                    {
                        "term": "あ",
                        "translation": "a"
                    },
                    {
                        "term": "い",
                        "translation": "i"
                    },
                    {
                        "term": "う",
                        "translation": "u"
                    },
                    {
                        "term": "え",
                        "translation": "e"
                    },
                    {
                        "term": "お",
                        "translation": "o"
                    },
                    {
                        "term": "か",
                        "translation": "ka"
                    },
                    {
                        "term": "き",
                        "translation": "ki"
                    },
                    {
                        "term": "く",
                        "translation": "ku"
                    },
                    {
                        "term": "け",
                        "translation": "ke"
                    },
                    {
                        "term": "こ",
                        "translation": "ko"
                    }
                ]
            },
            {
                "title": "Hiragana: S, T, N Groups",
                "items": [
                    {
                        "term": "さ",
                        "translation": "sa"
                    },
                    {
                        "term": "し",
                        "translation": "shi"
                    },
                    {
                        "term": "す",
                        "translation": "su"
                    },
                    {
                        "term": "せ",
                        "translation": "se"
                    },
                    {
                        "term": "そ",
                        "translation": "so"
                    },
                    {
                        "term": "た",
                        "translation": "ta"
                    },
                    {
                        "term": "ち",
                        "translation": "chi"
                    },
                    {
                        "term": "つ",
                        "translation": "tsu"
                    },
                    {
                        "term": "て",
                        "translation": "te"
                    },
                    {
                        "term": "と",
                        "translation": "to"
                    },
                    {
                        "term": "な",
                        "translation": "na"
                    },
                    {
                        "term": "に",
                        "translation": "ni"
                    },
                    {
                        "term": "ぬ",
                        "translation": "nu"
                    },
                    {
                        "term": "ね",
                        "translation": "ne"
                    },
                    {
                        "term": "の",
                        "translation": "no"
                    }
                ]
            },
            {
                "title": "Hiragana: H, M, Y, R, W Groups",
                "items": [
                    {
                        "term": "は",
                        "translation": "ha"
                    },
                    {
                        "term": "ひ",
                        "translation": "hi"
                    },
                    {
                        "term": "ふ",
                        "translation": "fu"
                    },
                    {
                        "term": "へ",
                        "translation": "he"
                    },
                    {
                        "term": "ほ",
                        "translation": "ho"
                    },
                    {
                        "term": "ま",
                        "translation": "ma"
                    },
                    {
                        "term": "み",
                        "translation": "mi"
                    },
                    {
                        "term": "む",
                        "translation": "mu"
                    },
                    {
                        "term": "め",
                        "translation": "me"
                    },
                    {
                        "term": "も",
                        "translation": "mo"
                    },
                    {
                        "term": "や",
                        "translation": "ya"
                    },
                    {
                        "term": "ゆ",
                        "translation": "yu"
                    },
                    {
                        "term": "よ",
                        "translation": "yo"
                    },
                    {
                        "term": "ら",
                        "translation": "ra"
                    },
                    {
                        "term": "り",
                        "translation": "ri"
                    },
                    {
                        "term": "る",
                        "translation": "ru"
                    },
                    {
                        "term": "れ",
                        "translation": "re"
                    },
                    {
                        "term": "ろ",
                        "translation": "ro"
                    },
                    {
                        "term": "わ",
                        "translation": "wa"
                    },
                    {
                        "term": "を",
                        "translation": "wo"
                    },
                    {
                        "term": "ん",
                        "translation": "n"
                    }
                ]
            }
        ]
    },
    "Spanish": {
        "type": "Alfabeto",
        "items": [
            {
                "term": "A",
                "translation": "a",
                "name": "a",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "a",
                "translation_tr": "a"
            },
            {
                "term": "B",
                "translation": "be",
                "name": "be",
                "phonetic_en": "[beh]",
                "phonetic_tr": "[be]",
                "translation_en": "be",
                "translation_tr": "be"
            },
            {
                "term": "C",
                "translation": "ce",
                "name": "ce",
                "phonetic_en": "[seh / theh]",
                "phonetic_tr": "[se / peltek se]",
                "translation_en": "ce",
                "translation_tr": "ce"
            },
            {
                "term": "D",
                "translation": "de",
                "name": "de",
                "phonetic_en": "[deh]",
                "phonetic_tr": "[de]",
                "translation_en": "de",
                "translation_tr": "de"
            },
            {
                "term": "E",
                "translation": "e",
                "name": "e",
                "phonetic_en": "[eh]",
                "phonetic_tr": "[e]",
                "translation_en": "e",
                "translation_tr": "e"
            },
            {
                "term": "F",
                "translation": "efe",
                "name": "efe",
                "phonetic_en": "[EH-feh]",
                "phonetic_tr": "[efe]",
                "translation_en": "efe",
                "translation_tr": "efe"
            },
            {
                "term": "G",
                "translation": "ge",
                "name": "ge",
                "phonetic_en": "[heh (e/i) / geh]",
                "phonetic_tr": "[he (e/i önünde) / ge]",
                "translation_en": "ge",
                "translation_tr": "ge"
            },
            {
                "term": "H",
                "translation": "hache",
                "name": "hache",
                "phonetic_en": "[AH-cheh] (silent)",
                "phonetic_tr": "[açe] (sessiz harf, okunmaz)",
                "translation_en": "hache",
                "translation_tr": "hache"
            },
            {
                "term": "I",
                "translation": "i",
                "name": "i",
                "phonetic_en": "[ee]",
                "phonetic_tr": "[i]",
                "translation_en": "i",
                "translation_tr": "i"
            },
            {
                "term": "J",
                "translation": "jota",
                "name": "jota",
                "phonetic_en": "[HOH-tah] (raspy h)",
                "phonetic_tr": "[hota] (boğazdan h)",
                "translation_en": "jota",
                "translation_tr": "jota"
            },
            {
                "term": "K",
                "translation": "ka",
                "name": "ka",
                "phonetic_en": "[kah]",
                "phonetic_tr": "[ka]",
                "translation_en": "ka",
                "translation_tr": "ka"
            },
            {
                "term": "L",
                "translation": "ele",
                "name": "ele",
                "phonetic_en": "[EH-leh]",
                "phonetic_tr": "[ele]",
                "translation_en": "ele",
                "translation_tr": "ele"
            },
            {
                "term": "M",
                "translation": "eme",
                "name": "eme",
                "phonetic_en": "[EH-meh]",
                "phonetic_tr": "[eme]",
                "translation_en": "eme",
                "translation_tr": "eme"
            },
            {
                "term": "N",
                "translation": "ene",
                "name": "ene",
                "phonetic_en": "[EH-neh]",
                "phonetic_tr": "[ene]",
                "translation_en": "ene",
                "translation_tr": "ene"
            },
            {
                "term": "Ñ",
                "translation": "eñe",
                "name": "eñe",
                "phonetic_en": "[EH-nyeh] (like canyon)",
                "phonetic_tr": "[enye]",
                "translation_en": "eñe",
                "translation_tr": "eñe"
            },
            {
                "term": "O",
                "translation": "o",
                "name": "o",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "o",
                "translation_tr": "o"
            },
            {
                "term": "P",
                "translation": "pe",
                "name": "pe",
                "phonetic_en": "[peh]",
                "phonetic_tr": "[pe]",
                "translation_en": "pe",
                "translation_tr": "pe"
            },
            {
                "term": "Q",
                "translation": "cu",
                "name": "cu",
                "phonetic_en": "[koo]",
                "phonetic_tr": "[ku]",
                "translation_en": "cu",
                "translation_tr": "cu"
            },
            {
                "term": "R",
                "translation": "ere",
                "name": "ere",
                "phonetic_en": "[EH-reh] (tapped r)",
                "phonetic_tr": "[ere]",
                "translation_en": "ere",
                "translation_tr": "ere"
            },
            {
                "term": "S",
                "translation": "ese",
                "name": "ese",
                "phonetic_en": "[EH-seh]",
                "phonetic_tr": "[ese]",
                "translation_en": "ese",
                "translation_tr": "ese"
            },
            {
                "term": "T",
                "translation": "te",
                "name": "te",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "te",
                "translation_tr": "te"
            },
            {
                "term": "U",
                "translation": "u",
                "name": "u",
                "phonetic_en": "[oo] (like boot)",
                "phonetic_tr": "[u]",
                "translation_en": "u",
                "translation_tr": "u"
            },
            {
                "term": "V",
                "translation": "uve",
                "name": "uve",
                "phonetic_en": "[OO-beh] (soft b/v)",
                "phonetic_tr": "[uve] (b-v arası yumuşak)",
                "translation_en": "uve",
                "translation_tr": "uve"
            },
            {
                "term": "W",
                "translation": "uve doble",
                "name": "uve doble",
                "phonetic_en": "[OO-beh DOH-bleh]",
                "phonetic_tr": "[uve doble] (çift v)",
                "translation_en": "uve doble",
                "translation_tr": "uve doble"
            },
            {
                "term": "X",
                "translation": "equis",
                "name": "equis",
                "phonetic_en": "[EH-kees]",
                "phonetic_tr": "[ekis]",
                "translation_en": "equis",
                "translation_tr": "equis"
            },
            {
                "term": "Y",
                "translation": "i griega",
                "name": "i griega",
                "phonetic_en": "[ee gryeh-gah / yeh]",
                "phonetic_tr": "[i griega] (ye / yunan i'si)",
                "translation_en": "i griega",
                "translation_tr": "i griega"
            },
            {
                "term": "Z",
                "translation": "zeta",
                "name": "zeta",
                "phonetic_en": "[SEH-tah / THEH-tah]",
                "phonetic_tr": "[seta / peltek s]",
                "translation_en": "zeta",
                "translation_tr": "zeta"
            }
        ]
    },
    "Russian": {
        "type": "Alphabet",
        "items": [
            {
                "term": "А",
                "translation": "а",
                "name": "а",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "а",
                "translation_tr": "а"
            },
            {
                "term": "Б",
                "translation": "бэ",
                "name": "бэ",
                "phonetic_en": "[beh]",
                "phonetic_tr": "[be]",
                "translation_en": "бэ",
                "translation_tr": "бэ"
            },
            {
                "term": "В",
                "translation": "вэ",
                "name": "вэ",
                "phonetic_en": "[veh]",
                "phonetic_tr": "[ve]",
                "translation_en": "вэ",
                "translation_tr": "вэ"
            },
            {
                "term": "Г",
                "translation": "гэ",
                "name": "гэ",
                "phonetic_en": "[geh]",
                "phonetic_tr": "[ge]",
                "translation_en": "гэ",
                "translation_tr": "гэ"
            },
            {
                "term": "Д",
                "translation": "дэ",
                "name": "дэ",
                "phonetic_en": "[deh]",
                "phonetic_tr": "[de]",
                "translation_en": "дэ",
                "translation_tr": "дэ"
            },
            {
                "term": "Е",
                "translation": "е",
                "name": "е",
                "phonetic_en": "[yeh]",
                "phonetic_tr": "[ye]",
                "translation_en": "е",
                "translation_tr": "е"
            },
            {
                "term": "Ё",
                "translation": "ё",
                "name": "ё",
                "phonetic_en": "[yoh]",
                "phonetic_tr": "[yo]",
                "translation_en": "ё",
                "translation_tr": "ё"
            },
            {
                "term": "Ж",
                "translation": "жэ",
                "name": "жэ",
                "phonetic_en": "[zheh] (like measure)",
                "phonetic_tr": "[je] (j sesi)",
                "translation_en": "жэ",
                "translation_tr": "жэ"
            },
            {
                "term": "З",
                "translation": "зэ",
                "name": "зэ",
                "phonetic_en": "[zeh]",
                "phonetic_tr": "[ze]",
                "translation_en": "зэ",
                "translation_tr": "зэ"
            },
            {
                "term": "И",
                "translation": "и",
                "name": "и",
                "phonetic_en": "[ee]",
                "phonetic_tr": "[i]",
                "translation_en": "и",
                "translation_tr": "и"
            },
            {
                "term": "Й",
                "translation": "и краткое",
                "name": "и краткое",
                "phonetic_en": "[ee krat-koye] (short y)",
                "phonetic_tr": "[kısa i] (y sesi)",
                "translation_en": "и краткое",
                "translation_tr": "и краткое"
            },
            {
                "term": "К",
                "translation": "ка",
                "name": "ка",
                "phonetic_en": "[kah]",
                "phonetic_tr": "[ka]",
                "translation_en": "ка",
                "translation_tr": "ка"
            },
            {
                "term": "Л",
                "translation": "эль",
                "name": "эль",
                "phonetic_en": "[ehl]",
                "phonetic_tr": "[el]",
                "translation_en": "эль",
                "translation_tr": "эль"
            },
            {
                "term": "М",
                "translation": "эм",
                "name": "эм",
                "phonetic_en": "[ehm]",
                "phonetic_tr": "[em]",
                "translation_en": "эм",
                "translation_tr": "эм"
            },
            {
                "term": "Н",
                "translation": "эн",
                "name": "эн",
                "phonetic_en": "[ehn]",
                "phonetic_tr": "[en]",
                "translation_en": "эн",
                "translation_tr": "эн"
            },
            {
                "term": "О",
                "translation": "о",
                "name": "о",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "о",
                "translation_tr": "о"
            },
            {
                "term": "П",
                "translation": "пэ",
                "name": "пэ",
                "phonetic_en": "[peh]",
                "phonetic_tr": "[pe]",
                "translation_en": "пэ",
                "translation_tr": "пэ"
            },
            {
                "term": "Р",
                "translation": "эр",
                "name": "эр",
                "phonetic_en": "[ehr] (rolled r)",
                "phonetic_tr": "[er] (titrek r)",
                "translation_en": "эр",
                "translation_tr": "эр"
            },
            {
                "term": "С",
                "translation": "эс",
                "name": "эс",
                "phonetic_en": "[ess]",
                "phonetic_tr": "[es]",
                "translation_en": "эс",
                "translation_tr": "эс"
            },
            {
                "term": "Т",
                "translation": "тэ",
                "name": "тэ",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "тэ",
                "translation_tr": "тэ"
            },
            {
                "term": "У",
                "translation": "у",
                "name": "у",
                "phonetic_en": "[oo]",
                "phonetic_tr": "[u]",
                "translation_en": "у",
                "translation_tr": "у"
            },
            {
                "term": "Ф",
                "translation": "эф",
                "name": "эф",
                "phonetic_en": "[ehf]",
                "phonetic_tr": "[ef]",
                "translation_en": "эф",
                "translation_tr": "эф"
            },
            {
                "term": "Х",
                "translation": "ха",
                "name": "ха",
                "phonetic_en": "[khah] (raspy h)",
                "phonetic_tr": "[ha] (hırıltılı h)",
                "translation_en": "ха",
                "translation_tr": "ха"
            },
            {
                "term": "Ц",
                "translation": "цэ",
                "name": "цэ",
                "phonetic_en": "[tseh]",
                "phonetic_tr": "[tse]",
                "translation_en": "цэ",
                "translation_tr": "цэ"
            },
            {
                "term": "Ч",
                "translation": "че",
                "name": "че",
                "phonetic_en": "[cheh]",
                "phonetic_tr": "[çe]",
                "translation_en": "че",
                "translation_tr": "че"
            },
            {
                "term": "Ш",
                "translation": "ша",
                "name": "ша",
                "phonetic_en": "[shah] (hard sh)",
                "phonetic_tr": "[şa] (kalın ş)",
                "translation_en": "ша",
                "translation_tr": "ша"
            },
            {
                "term": "Щ",
                "translation": "ща",
                "name": "ща",
                "phonetic_en": "[shcha] (soft shch)",
                "phonetic_tr": "[şça] (yumuşak şç)",
                "translation_en": "ща",
                "translation_tr": "ща"
            },
            {
                "term": "Ъ",
                "translation": "твёрдый знак",
                "name": "твёрдый знак",
                "phonetic_en": "[hard sign] (pause)",
                "phonetic_tr": "[sertlik işareti]",
                "translation_en": "твёрдый знак",
                "translation_tr": "твёрдый знак"
            },
            {
                "term": "Ы",
                "translation": "ы",
                "name": "ы",
                "phonetic_en": "[ih] (deep back i)",
                "phonetic_tr": "[ı] (ı sesi)",
                "translation_en": "ы",
                "translation_tr": "ы"
            },
            {
                "term": "Ь",
                "translation": "мягкий знак",
                "name": "мягкий знак",
                "phonetic_en": "[soft sign] (softens)",
                "phonetic_tr": "[inceltme işareti]",
                "translation_en": "мягкий знак",
                "translation_tr": "мягкий знак"
            },
            {
                "term": "Э",
                "translation": "э",
                "name": "э",
                "phonetic_en": "[eh]",
                "phonetic_tr": "[açık e]",
                "translation_en": "э",
                "translation_tr": "э"
            },
            {
                "term": "Ю",
                "translation": "ю",
                "name": "ю",
                "phonetic_en": "[yoo]",
                "phonetic_tr": "[yu]",
                "translation_en": "ю",
                "translation_tr": "ю"
            },
            {
                "term": "Я",
                "translation": "я",
                "name": "я",
                "phonetic_en": "[yah]",
                "phonetic_tr": "[ya]",
                "translation_en": "я",
                "translation_tr": "я"
            }
        ]
    },
    "Turkish": {
        "type": "Alfabe",
        "items": [
            {
                "term": "A",
                "translation": "a",
                "name": "a",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "a",
                "translation_tr": "a"
            },
            {
                "term": "B",
                "translation": "be",
                "name": "be",
                "phonetic_en": "[beh]",
                "phonetic_tr": "[be]",
                "translation_en": "be",
                "translation_tr": "be"
            },
            {
                "term": "C",
                "translation": "ce",
                "name": "ce",
                "phonetic_en": "[jeh] (like j in joy)",
                "phonetic_tr": "[ce]",
                "translation_en": "ce",
                "translation_tr": "ce"
            },
            {
                "term": "Ç",
                "translation": "çe",
                "name": "çe",
                "phonetic_en": "[cheh] (like ch in chair)",
                "phonetic_tr": "[çe]",
                "translation_en": "çe",
                "translation_tr": "çe"
            },
            {
                "term": "D",
                "translation": "de",
                "name": "de",
                "phonetic_en": "[deh]",
                "phonetic_tr": "[de]",
                "translation_en": "de",
                "translation_tr": "de"
            },
            {
                "term": "E",
                "translation": "e",
                "name": "e",
                "phonetic_en": "[eh]",
                "phonetic_tr": "[e]",
                "translation_en": "e",
                "translation_tr": "e"
            },
            {
                "term": "F",
                "translation": "fe",
                "name": "fe",
                "phonetic_en": "[feh]",
                "phonetic_tr": "[fe]",
                "translation_en": "fe",
                "translation_tr": "fe"
            },
            {
                "term": "G",
                "translation": "ge",
                "name": "ge",
                "phonetic_en": "[geh]",
                "phonetic_tr": "[ge]",
                "translation_en": "ge",
                "translation_tr": "ge"
            },
            {
                "term": "Ğ",
                "translation": "yumuşak ge",
                "name": "yumuşak ge",
                "phonetic_en": "[silent / lengthens vowel]",
                "phonetic_tr": "[yumuşak ge] (önceki ünlüyü uzatır)",
                "translation_en": "yumuşak ge",
                "translation_tr": "yumuşak ge"
            },
            {
                "term": "H",
                "translation": "he",
                "name": "he",
                "phonetic_en": "[heh]",
                "phonetic_tr": "[he]",
                "translation_en": "he",
                "translation_tr": "he"
            },
            {
                "term": "I",
                "translation": "ı",
                "name": "ı",
                "phonetic_en": "[uh] (dotless i)",
                "phonetic_tr": "[ı] (noktasız ı)",
                "translation_en": "ı",
                "translation_tr": "ı"
            },
            {
                "term": "İ",
                "translation": "i",
                "name": "i",
                "phonetic_en": "[ee] (dotted i)",
                "phonetic_tr": "[i] (noktalı i)",
                "translation_en": "i",
                "translation_tr": "i"
            },
            {
                "term": "J",
                "translation": "je",
                "name": "je",
                "phonetic_en": "[zheh] (like s in measure)",
                "phonetic_tr": "[je]",
                "translation_en": "je",
                "translation_tr": "je"
            },
            {
                "term": "K",
                "translation": "ke",
                "name": "ke",
                "phonetic_en": "[keh]",
                "phonetic_tr": "[ke]",
                "translation_en": "ke",
                "translation_tr": "ke"
            },
            {
                "term": "L",
                "translation": "le",
                "name": "le",
                "phonetic_en": "[leh]",
                "phonetic_tr": "[le]",
                "translation_en": "le",
                "translation_tr": "le"
            },
            {
                "term": "M",
                "translation": "me",
                "name": "me",
                "phonetic_en": "[meh]",
                "phonetic_tr": "[me]",
                "translation_en": "me",
                "translation_tr": "me"
            },
            {
                "term": "N",
                "translation": "ne",
                "name": "ne",
                "phonetic_en": "[neh]",
                "phonetic_tr": "[ne]",
                "translation_en": "ne",
                "translation_tr": "ne"
            },
            {
                "term": "O",
                "translation": "o",
                "name": "o",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "o",
                "translation_tr": "o"
            },
            {
                "term": "Ö",
                "translation": "ö",
                "name": "ö",
                "phonetic_en": "[er] (like bird)",
                "phonetic_tr": "[ö]",
                "translation_en": "ö",
                "translation_tr": "ö"
            },
            {
                "term": "P",
                "translation": "pe",
                "name": "pe",
                "phonetic_en": "[peh]",
                "phonetic_tr": "[pe]",
                "translation_en": "pe",
                "translation_tr": "pe"
            },
            {
                "term": "R",
                "translation": "re",
                "name": "re",
                "phonetic_en": "[reh]",
                "phonetic_tr": "[re]",
                "translation_en": "re",
                "translation_tr": "re"
            },
            {
                "term": "S",
                "translation": "se",
                "name": "se",
                "phonetic_en": "[seh]",
                "phonetic_tr": "[se]",
                "translation_en": "se",
                "translation_tr": "se"
            },
            {
                "term": "Ş",
                "translation": "şe",
                "name": "şe",
                "phonetic_en": "[sheh] (like sh in shoe)",
                "phonetic_tr": "[şe]",
                "translation_en": "şe",
                "translation_tr": "şe"
            },
            {
                "term": "T",
                "translation": "te",
                "name": "te",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "te",
                "translation_tr": "te"
            },
            {
                "term": "U",
                "translation": "u",
                "name": "u",
                "phonetic_en": "[oo]",
                "phonetic_tr": "[u]",
                "translation_en": "u",
                "translation_tr": "u"
            },
            {
                "term": "Ü",
                "translation": "ü",
                "name": "ü",
                "phonetic_en": "[ew] (like French u)",
                "phonetic_tr": "[ü]",
                "translation_en": "ü",
                "translation_tr": "ü"
            },
            {
                "term": "V",
                "translation": "ve",
                "name": "ve",
                "phonetic_en": "[veh]",
                "phonetic_tr": "[ve]",
                "translation_en": "ve",
                "translation_tr": "ve"
            },
            {
                "term": "Y",
                "translation": "ye",
                "name": "ye",
                "phonetic_en": "[yeh]",
                "phonetic_tr": "[ye]",
                "translation_en": "ye",
                "translation_tr": "ye"
            },
            {
                "term": "Z",
                "translation": "ze",
                "name": "ze",
                "phonetic_en": "[zeh]",
                "phonetic_tr": "[ze]",
                "translation_en": "ze",
                "translation_tr": "ze"
            }
        ]
    },
    "Arabic": {
        "type": "Alphabet",
        "items": [
            {
                "term": "ا",
                "translation": "Alif"
            },
            {
                "term": "ب",
                "translation": "Ba"
            },
            {
                "term": "ت",
                "translation": "Ta"
            },
            {
                "term": "ث",
                "translation": "Tha"
            },
            {
                "term": "ج",
                "translation": "Jim"
            },
            {
                "term": "ح",
                "translation": "Ha"
            },
            {
                "term": "خ",
                "translation": "Kha"
            },
            {
                "term": "د",
                "translation": "Dal"
            },
            {
                "term": "ذ",
                "translation": "Dhal"
            },
            {
                "term": "ر",
                "translation": "Ra"
            },
            {
                "term": "ز",
                "translation": "Zay"
            },
            {
                "term": "س",
                "translation": "Sin"
            },
            {
                "term": "ش",
                "translation": "Shin"
            },
            {
                "term": "ص",
                "translation": "Sad"
            },
            {
                "term": "ض",
                "translation": "Dad"
            },
            {
                "term": "ط",
                "translation": "Ta"
            },
            {
                "term": "ظ",
                "translation": "Za"
            },
            {
                "term": "ع",
                "translation": "Ayn"
            },
            {
                "term": "غ",
                "translation": "Ghayn"
            },
            {
                "term": "ف",
                "translation": "Fa"
            },
            {
                "term": "ق",
                "translation": "Qaf"
            },
            {
                "term": "ك",
                "translation": "Kaf"
            },
            {
                "term": "ل",
                "translation": "Lam"
            },
            {
                "term": "م",
                "translation": "Mim"
            },
            {
                "term": "ن",
                "translation": "Nun"
            },
            {
                "term": "ه",
                "translation": "Ha"
            },
            {
                "term": "و",
                "translation": "Waw"
            },
            {
                "term": "ي",
                "translation": "Ya"
            }
        ]
    },
    "German": {
        "type": "Alphabet",
        "items": [
            {
                "term": "A",
                "translation": "a",
                "name": "a",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "a",
                "translation_tr": "a"
            },
            {
                "term": "B",
                "translation": "be",
                "name": "be",
                "phonetic_en": "[beh]",
                "phonetic_tr": "[be]",
                "translation_en": "be",
                "translation_tr": "be"
            },
            {
                "term": "C",
                "translation": "tse",
                "name": "tse",
                "phonetic_en": "[tseh]",
                "phonetic_tr": "[tse]",
                "translation_en": "tse",
                "translation_tr": "tse"
            },
            {
                "term": "D",
                "translation": "de",
                "name": "de",
                "phonetic_en": "[deh]",
                "phonetic_tr": "[de]",
                "translation_en": "de",
                "translation_tr": "de"
            },
            {
                "term": "E",
                "translation": "e",
                "name": "e",
                "phonetic_en": "[eh]",
                "phonetic_tr": "[e]",
                "translation_en": "e",
                "translation_tr": "e"
            },
            {
                "term": "F",
                "translation": "ef",
                "name": "ef",
                "phonetic_en": "[eff]",
                "phonetic_tr": "[ef]",
                "translation_en": "ef",
                "translation_tr": "ef"
            },
            {
                "term": "G",
                "translation": "ge",
                "name": "ge",
                "phonetic_en": "[geh]",
                "phonetic_tr": "[ge]",
                "translation_en": "ge",
                "translation_tr": "ge"
            },
            {
                "term": "H",
                "translation": "ha",
                "name": "ha",
                "phonetic_en": "[hah]",
                "phonetic_tr": "[ha]",
                "translation_en": "ha",
                "translation_tr": "ha"
            },
            {
                "term": "I",
                "translation": "i",
                "name": "i",
                "phonetic_en": "[ee]",
                "phonetic_tr": "[i]",
                "translation_en": "i",
                "translation_tr": "i"
            },
            {
                "term": "J",
                "translation": "jot",
                "name": "jot",
                "phonetic_en": "[yot] (like y in yes)",
                "phonetic_tr": "[yot] ('y' sesiyle)",
                "translation_en": "jot",
                "translation_tr": "jot"
            },
            {
                "term": "K",
                "translation": "ka",
                "name": "ka",
                "phonetic_en": "[kah]",
                "phonetic_tr": "[ka]",
                "translation_en": "ka",
                "translation_tr": "ka"
            },
            {
                "term": "L",
                "translation": "el",
                "name": "el",
                "phonetic_en": "[ell]",
                "phonetic_tr": "[el]",
                "translation_en": "el",
                "translation_tr": "el"
            },
            {
                "term": "M",
                "translation": "em",
                "name": "em",
                "phonetic_en": "[emm]",
                "phonetic_tr": "[em]",
                "translation_en": "em",
                "translation_tr": "em"
            },
            {
                "term": "N",
                "translation": "en",
                "name": "en",
                "phonetic_en": "[enn]",
                "phonetic_tr": "[en]",
                "translation_en": "en",
                "translation_tr": "en"
            },
            {
                "term": "O",
                "translation": "o",
                "name": "o",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "o",
                "translation_tr": "o"
            },
            {
                "term": "P",
                "translation": "pe",
                "name": "pe",
                "phonetic_en": "[peh]",
                "phonetic_tr": "[pe]",
                "translation_en": "pe",
                "translation_tr": "pe"
            },
            {
                "term": "Q",
                "translation": "ku",
                "name": "ku",
                "phonetic_en": "[koo]",
                "phonetic_tr": "[ku]",
                "translation_en": "ku",
                "translation_tr": "ku"
            },
            {
                "term": "R",
                "translation": "er",
                "name": "er",
                "phonetic_en": "[err] (throat r)",
                "phonetic_tr": "[er] (genizden r)",
                "translation_en": "er",
                "translation_tr": "er"
            },
            {
                "term": "S",
                "translation": "es",
                "name": "es",
                "phonetic_en": "[ess] (or z initial)",
                "phonetic_tr": "[es] (başta z sesi)",
                "translation_en": "es",
                "translation_tr": "es"
            },
            {
                "term": "T",
                "translation": "te",
                "name": "te",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "te",
                "translation_tr": "te"
            },
            {
                "term": "U",
                "translation": "u",
                "name": "u",
                "phonetic_en": "[oo]",
                "phonetic_tr": "[u]",
                "translation_en": "u",
                "translation_tr": "u"
            },
            {
                "term": "V",
                "translation": "vau",
                "name": "vau",
                "phonetic_en": "[fow] (f-sound)",
                "phonetic_tr": "[fau] ('f' sesiyle)",
                "translation_en": "vau",
                "translation_tr": "vau"
            },
            {
                "term": "W",
                "translation": "we",
                "name": "we",
                "phonetic_en": "[veh] (v-sound)",
                "phonetic_tr": "[ve] ('v' sesiyle)",
                "translation_en": "we",
                "translation_tr": "we"
            },
            {
                "term": "X",
                "translation": "ix",
                "name": "ix",
                "phonetic_en": "[iks]",
                "phonetic_tr": "[iks]",
                "translation_en": "ix",
                "translation_tr": "ix"
            },
            {
                "term": "Y",
                "translation": "ypsilon",
                "name": "ypsilon",
                "phonetic_en": "[OOP-si-lon] (ü-sound)",
                "phonetic_tr": "[üpsilon] ('ü' sesiyle)",
                "translation_en": "ypsilon",
                "translation_tr": "ypsilon"
            },
            {
                "term": "Z",
                "translation": "zett",
                "name": "zett",
                "phonetic_en": "[tsett] (ts-sound)",
                "phonetic_tr": "[tset] ('ts' sesiyle)",
                "translation_en": "zett",
                "translation_tr": "zett"
            },
            {
                "term": "Ä",
                "translation": "a-umlaut",
                "name": "ä",
                "phonetic_en": "[eh-umlaut] (open e)",
                "phonetic_tr": "[açık e]",
                "translation_en": "ä",
                "translation_tr": "ä"
            },
            {
                "term": "Ö",
                "translation": "o-umlaut",
                "name": "ö",
                "phonetic_en": "[er-umlaut] (rounded ö)",
                "phonetic_tr": "[ö sesi]",
                "translation_en": "ö",
                "translation_tr": "ö"
            },
            {
                "term": "Ü",
                "translation": "u-umlaut",
                "name": "ü",
                "phonetic_en": "[ew-umlaut] (rounded ü)",
                "phonetic_tr": "[ü sesi]",
                "translation_en": "ü",
                "translation_tr": "ü"
            },
            {
                "term": "ß",
                "translation": "eszett",
                "name": "eszett",
                "phonetic_en": "[ess-tsett] (sharp ss)",
                "phonetic_tr": "[es-tset] (keskin çift s)",
                "translation_en": "eszett",
                "translation_tr": "eszett"
            }
        ]
    },
    "French": {
        "type": "Alphabet",
        "items": [
            {
                "term": "A",
                "translation": "a",
                "name": "a",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "a",
                "translation_tr": "a"
            },
            {
                "term": "B",
                "translation": "bé",
                "name": "bé",
                "phonetic_en": "[beh]",
                "phonetic_tr": "[be]",
                "translation_en": "bé",
                "translation_tr": "bé"
            },
            {
                "term": "C",
                "translation": "cé",
                "name": "cé",
                "phonetic_en": "[seh]",
                "phonetic_tr": "[se]",
                "translation_en": "cé",
                "translation_tr": "cé"
            },
            {
                "term": "D",
                "translation": "dé",
                "name": "dé",
                "phonetic_en": "[deh]",
                "phonetic_tr": "[de]",
                "translation_en": "dé",
                "translation_tr": "dé"
            },
            {
                "term": "E",
                "translation": "e",
                "name": "e",
                "phonetic_en": "[uh]",
                "phonetic_tr": "[ö/e arası ses]",
                "translation_en": "e",
                "translation_tr": "e"
            },
            {
                "term": "F",
                "translation": "effe",
                "name": "effe",
                "phonetic_en": "[eff]",
                "phonetic_tr": "[ef]",
                "translation_en": "effe",
                "translation_tr": "effe"
            },
            {
                "term": "G",
                "translation": "gé",
                "name": "gé",
                "phonetic_en": "[zheh]",
                "phonetic_tr": "[je]",
                "translation_en": "gé",
                "translation_tr": "gé"
            },
            {
                "term": "H",
                "translation": "hache",
                "name": "hache",
                "phonetic_en": "[ahsh] (silent)",
                "phonetic_tr": "[aş] (sessiz harf, okunmaz)",
                "translation_en": "hache",
                "translation_tr": "hache"
            },
            {
                "term": "I",
                "translation": "i",
                "name": "i",
                "phonetic_en": "[ee]",
                "phonetic_tr": "[i]",
                "translation_en": "i",
                "translation_tr": "i"
            },
            {
                "term": "J",
                "translation": "ji",
                "name": "ji",
                "phonetic_en": "[zhee]",
                "phonetic_tr": "[ji]",
                "translation_en": "ji",
                "translation_tr": "ji"
            },
            {
                "term": "K",
                "translation": "ka",
                "name": "ka",
                "phonetic_en": "[kah]",
                "phonetic_tr": "[ka]",
                "translation_en": "ka",
                "translation_tr": "ka"
            },
            {
                "term": "L",
                "translation": "elle",
                "name": "elle",
                "phonetic_en": "[ell]",
                "phonetic_tr": "[el]",
                "translation_en": "elle",
                "translation_tr": "elle"
            },
            {
                "term": "M",
                "translation": "emme",
                "name": "emme",
                "phonetic_en": "[emm]",
                "phonetic_tr": "[em]",
                "translation_en": "emme",
                "translation_tr": "emme"
            },
            {
                "term": "N",
                "translation": "enne",
                "name": "enne",
                "phonetic_en": "[enn]",
                "phonetic_tr": "[en]",
                "translation_en": "enne",
                "translation_tr": "enne"
            },
            {
                "term": "O",
                "translation": "o",
                "name": "o",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "o",
                "translation_tr": "o"
            },
            {
                "term": "P",
                "translation": "pé",
                "name": "pé",
                "phonetic_en": "[peh]",
                "phonetic_tr": "[pe]",
                "translation_en": "pé",
                "translation_tr": "pé"
            },
            {
                "term": "Q",
                "translation": "qu",
                "name": "qu",
                "phonetic_en": "[kew]",
                "phonetic_tr": "[kü]",
                "translation_en": "qu",
                "translation_tr": "qu"
            },
            {
                "term": "R",
                "translation": "erre",
                "name": "erre",
                "phonetic_en": "[ehr] (guttural r)",
                "phonetic_tr": "[er] (boğazdan r)",
                "translation_en": "erre",
                "translation_tr": "erre"
            },
            {
                "term": "S",
                "translation": "esse",
                "name": "esse",
                "phonetic_en": "[ess]",
                "phonetic_tr": "[es]",
                "translation_en": "esse",
                "translation_tr": "esse"
            },
            {
                "term": "T",
                "translation": "té",
                "name": "té",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "té",
                "translation_tr": "té"
            },
            {
                "term": "U",
                "translation": "u",
                "name": "u",
                "phonetic_en": "[ew] (rounded u)",
                "phonetic_tr": "[ü]",
                "translation_en": "u",
                "translation_tr": "u"
            },
            {
                "term": "V",
                "translation": "vé",
                "name": "vé",
                "phonetic_en": "[veh]",
                "phonetic_tr": "[ve]",
                "translation_en": "vé",
                "translation_tr": "vé"
            },
            {
                "term": "W",
                "translation": "double vé",
                "name": "double vé",
                "phonetic_en": "[doobl-veh]",
                "phonetic_tr": "[dubl ve]",
                "translation_en": "double vé",
                "translation_tr": "double vé"
            },
            {
                "term": "X",
                "translation": "ics",
                "name": "ics",
                "phonetic_en": "[eeks]",
                "phonetic_tr": "[iks]",
                "translation_en": "ics",
                "translation_tr": "ics"
            },
            {
                "term": "Y",
                "translation": "i grec",
                "name": "i grec",
                "phonetic_en": "[ee-grek]",
                "phonetic_tr": "[i grek]",
                "translation_en": "i grec",
                "translation_tr": "i grec"
            },
            {
                "term": "Z",
                "translation": "zède",
                "name": "zède",
                "phonetic_en": "[zed]",
                "phonetic_tr": "[zed]",
                "translation_en": "zède",
                "translation_tr": "zède"
            }
        ]
    },
    "Italian": {
        "type": "Alfabeto",
        "items": [
            {
                "term": "A",
                "translation": "a",
                "name": "a",
                "phonetic_en": "[ah]",
                "phonetic_tr": "[a]",
                "translation_en": "a",
                "translation_tr": "a"
            },
            {
                "term": "B",
                "translation": "bi",
                "name": "bi",
                "phonetic_en": "[bee]",
                "phonetic_tr": "[bi]",
                "translation_en": "bi",
                "translation_tr": "bi"
            },
            {
                "term": "C",
                "translation": "ci",
                "name": "ci",
                "phonetic_en": "[chee (e/i) / k (a/o/u)]",
                "phonetic_tr": "[çi (e/i) / k (a/o/u)]",
                "translation_en": "ci",
                "translation_tr": "ci"
            },
            {
                "term": "D",
                "translation": "di",
                "name": "di",
                "phonetic_en": "[dee]",
                "phonetic_tr": "[di]",
                "translation_en": "di",
                "translation_tr": "di"
            },
            {
                "term": "E",
                "translation": "e",
                "name": "e",
                "phonetic_en": "[eh]",
                "phonetic_tr": "[e]",
                "translation_en": "e",
                "translation_tr": "e"
            },
            {
                "term": "F",
                "translation": "effe",
                "name": "effe",
                "phonetic_en": "[EH-feh]",
                "phonetic_tr": "[effe]",
                "translation_en": "effe",
                "translation_tr": "effe"
            },
            {
                "term": "G",
                "translation": "gi",
                "name": "gi",
                "phonetic_en": "[jee (e/i) / g (a/o/u)]",
                "phonetic_tr": "[ci (e/i) / g (a/o/u)]",
                "translation_en": "gi",
                "translation_tr": "gi"
            },
            {
                "term": "H",
                "translation": "acca",
                "name": "acca",
                "phonetic_en": "[AHK-kah] (silent)",
                "phonetic_tr": "[akka] (sessiz harf, okunmaz)",
                "translation_en": "acca",
                "translation_tr": "acca"
            },
            {
                "term": "I",
                "translation": "i",
                "name": "i",
                "phonetic_en": "[ee]",
                "phonetic_tr": "[i]",
                "translation_en": "i",
                "translation_tr": "i"
            },
            {
                "term": "L",
                "translation": "elle",
                "name": "elle",
                "phonetic_en": "[EH-leh]",
                "phonetic_tr": "[elle]",
                "translation_en": "elle",
                "translation_tr": "elle"
            },
            {
                "term": "M",
                "translation": "emme",
                "name": "emme",
                "phonetic_en": "[EH-meh]",
                "phonetic_tr": "[emme]",
                "translation_en": "emme",
                "translation_tr": "emme"
            },
            {
                "term": "N",
                "translation": "enne",
                "name": "enne",
                "phonetic_en": "[EH-neh]",
                "phonetic_tr": "[enne]",
                "translation_en": "enne",
                "translation_tr": "enne"
            },
            {
                "term": "O",
                "translation": "o",
                "name": "o",
                "phonetic_en": "[oh]",
                "phonetic_tr": "[o]",
                "translation_en": "o",
                "translation_tr": "o"
            },
            {
                "term": "P",
                "translation": "pi",
                "name": "pi",
                "phonetic_en": "[pee]",
                "phonetic_tr": "[pi]",
                "translation_en": "pi",
                "translation_tr": "pi"
            },
            {
                "term": "Q",
                "translation": "cu",
                "name": "cu",
                "phonetic_en": "[koo]",
                "phonetic_tr": "[ku]",
                "translation_en": "cu",
                "translation_tr": "cu"
            },
            {
                "term": "R",
                "translation": "erre",
                "name": "erre",
                "phonetic_en": "[EH-rreh] (rolled r)",
                "phonetic_tr": "[erre] (titrek r)",
                "translation_en": "erre",
                "translation_tr": "erre"
            },
            {
                "term": "S",
                "translation": "esse",
                "name": "esse",
                "phonetic_en": "[EH-seh]",
                "phonetic_tr": "[esse]",
                "translation_en": "esse",
                "translation_tr": "esse"
            },
            {
                "term": "T",
                "translation": "te",
                "name": "te",
                "phonetic_en": "[teh]",
                "phonetic_tr": "[te]",
                "translation_en": "te",
                "translation_tr": "te"
            },
            {
                "term": "U",
                "translation": "u",
                "name": "u",
                "phonetic_en": "[oo]",
                "phonetic_tr": "[u]",
                "translation_en": "u",
                "translation_tr": "u"
            },
            {
                "term": "V",
                "translation": "vi",
                "name": "vi",
                "phonetic_en": "[vee]",
                "phonetic_tr": "[vi]",
                "translation_en": "vi",
                "translation_tr": "vi"
            },
            {
                "term": "Z",
                "translation": "zeta",
                "name": "zeta",
                "phonetic_en": "[DZEH-tah / TSEH-tah]",
                "phonetic_tr": "[dzeta / tseta]",
                "translation_en": "zeta",
                "translation_tr": "zeta"
            }
        ]
    },
    "Portuguese": {
        "type": "Alfabeto",
        "items": [
            {
                "term": "A",
                "translation": "á"
            },
            {
                "term": "B",
                "translation": "bê"
            },
            {
                "term": "C",
                "translation": "cê"
            },
            {
                "term": "D",
                "translation": "dê"
            },
            {
                "term": "E",
                "translation": "é"
            },
            {
                "term": "F",
                "translation": "éfe"
            },
            {
                "term": "G",
                "translation": "gê"
            },
            {
                "term": "H",
                "translation": "agá"
            },
            {
                "term": "I",
                "translation": "i"
            },
            {
                "term": "J",
                "translation": "jota"
            },
            {
                "term": "K",
                "translation": "capa"
            },
            {
                "term": "L",
                "translation": "éle"
            },
            {
                "term": "M",
                "translation": "éme"
            },
            {
                "term": "N",
                "translation": "éne"
            },
            {
                "term": "O",
                "translation": "ó"
            },
            {
                "term": "P",
                "translation": "pê"
            },
            {
                "term": "Q",
                "translation": "quê"
            },
            {
                "term": "R",
                "translation": "ére"
            },
            {
                "term": "S",
                "translation": "ésse"
            },
            {
                "term": "T",
                "translation": "tê"
            },
            {
                "term": "U",
                "translation": "u"
            },
            {
                "term": "V",
                "translation": "vê"
            },
            {
                "term": "W",
                "translation": "dáblio"
            },
            {
                "term": "X",
                "translation": "xis"
            },
            {
                "term": "Y",
                "translation": "ípsilon"
            },
            {
                "term": "Z",
                "translation": "zê"
            }
        ]
    },
    "Dutch": {
        "type": "Alfabet",
        "items": [
            {
                "term": "A",
                "translation": "a"
            },
            {
                "term": "B",
                "translation": "be"
            },
            {
                "term": "C",
                "translation": "ce"
            },
            {
                "term": "D",
                "translation": "de"
            },
            {
                "term": "E",
                "translation": "e"
            },
            {
                "term": "F",
                "translation": "ef"
            },
            {
                "term": "G",
                "translation": "ge"
            },
            {
                "term": "H",
                "translation": "ha"
            },
            {
                "term": "I",
                "translation": "i"
            },
            {
                "term": "J",
                "translation": "jee"
            },
            {
                "term": "K",
                "translation": "ka"
            },
            {
                "term": "L",
                "translation": "el"
            },
            {
                "term": "M",
                "translation": "em"
            },
            {
                "term": "N",
                "translation": "en"
            },
            {
                "term": "O",
                "translation": "o"
            },
            {
                "term": "P",
                "translation": "pe"
            },
            {
                "term": "Q",
                "translation": "ku"
            },
            {
                "term": "R",
                "translation": "er"
            },
            {
                "term": "S",
                "translation": "es"
            },
            {
                "term": "T",
                "translation": "te"
            },
            {
                "term": "U",
                "translation": "u"
            },
            {
                "term": "V",
                "translation": "vee"
            },
            {
                "term": "W",
                "translation": "wee"
            },
            {
                "term": "X",
                "translation": "iks"
            },
            {
                "term": "Y",
                "translation": "ij/ypsilon"
            },
            {
                "term": "Z",
                "translation": "zet"
            }
        ]
    },
    "Swedish": {
        "type": "Alfabet",
        "items": [
            {
                "term": "A",
                "translation": "a"
            },
            {
                "term": "B",
                "translation": "be"
            },
            {
                "term": "C",
                "translation": "se"
            },
            {
                "term": "D",
                "translation": "de"
            },
            {
                "term": "E",
                "translation": "e"
            },
            {
                "term": "F",
                "translation": "eff"
            },
            {
                "term": "G",
                "translation": "ge"
            },
            {
                "term": "H",
                "translation": "hå"
            },
            {
                "term": "I",
                "translation": "i"
            },
            {
                "term": "J",
                "translation": "ji"
            },
            {
                "term": "K",
                "translation": "kå"
            },
            {
                "term": "L",
                "translation": "ell"
            },
            {
                "term": "M",
                "translation": "emm"
            },
            {
                "term": "N",
                "translation": "enn"
            },
            {
                "term": "O",
                "translation": "o"
            },
            {
                "term": "P",
                "translation": "pe"
            },
            {
                "term": "Q",
                "translation": "ku"
            },
            {
                "term": "R",
                "translation": "ärr"
            },
            {
                "term": "S",
                "translation": "ess"
            },
            {
                "term": "T",
                "translation": "te"
            },
            {
                "term": "U",
                "translation": "u"
            },
            {
                "term": "V",
                "translation": "ve"
            },
            {
                "term": "W",
                "translation": "dubbel-ve"
            },
            {
                "term": "X",
                "translation": "eks"
            },
            {
                "term": "Y",
                "translation": "y"
            },
            {
                "term": "Z",
                "translation": "säta"
            },
            {
                "term": "Å",
                "translation": "å"
            },
            {
                "term": "Ä",
                "translation": "ä"
            },
            {
                "term": "Ö",
                "translation": "ö"
            }
        ]
    },
    "Korean": {
        "type": "Hangul",
        "items": [
            {
                "term": "ㄱ",
                "translation": "giyeok"
            },
            {
                "term": "ㄴ",
                "translation": "nieun"
            },
            {
                "term": "ㄷ",
                "translation": "digeut"
            },
            {
                "term": "ㄹ",
                "translation": "rieul"
            },
            {
                "term": "ㅁ",
                "translation": "mieun"
            },
            {
                "term": "ㅂ",
                "translation": "bieup"
            },
            {
                "term": "ㅅ",
                "translation": "siot"
            },
            {
                "term": "ㅇ",
                "translation": "ieung"
            },
            {
                "term": "ㅈ",
                "translation": "jieut"
            },
            {
                "term": "ㅊ",
                "translation": "chieut"
            },
            {
                "term": "ㅋ",
                "translation": "kieuk"
            },
            {
                "term": "ㅌ",
                "translation": "tieut"
            },
            {
                "term": "ㅍ",
                "translation": "pieup"
            },
            {
                "term": "ㅎ",
                "translation": "hieut"
            },
            {
                "term": "ㅏ",
                "translation": "a"
            },
            {
                "term": "ㅑ",
                "translation": "ya"
            },
            {
                "term": "ㅓ",
                "translation": "eo"
            },
            {
                "term": "ㅕ",
                "translation": "yeo"
            },
            {
                "term": "ㅗ",
                "translation": "o"
            },
            {
                "term": "ㅛ",
                "translation": "yo"
            },
            {
                "term": "ㅜ",
                "translation": "u"
            },
            {
                "term": "ㅠ",
                "translation": "yu"
            },
            {
                "term": "ㅡ",
                "translation": "eu"
            },
            {
                "term": "ㅣ",
                "translation": "i"
            }
        ]
    },
    "Greek": {
        "type": "Alphabet",
        "items": [
            {
                "term": "Α",
                "translation": "Alpha",
                "name": "Alpha",
                "phonetic_en": "[AH-fah]",
                "phonetic_tr": "[alfa]",
                "translation_en": "Alpha",
                "translation_tr": "Alpha"
            },
            {
                "term": "Β",
                "translation": "Beta",
                "name": "Vita",
                "phonetic_en": "[VEE-tah] (v-sound in modern Greek)",
                "phonetic_tr": "[vita] ('v' sesiyle)",
                "translation_en": "Vita",
                "translation_tr": "Vita"
            },
            {
                "term": "Γ",
                "translation": "Gamma",
                "name": "Gamma",
                "phonetic_en": "[GHAH-mah]",
                "phonetic_tr": "[gama] (boğazdan g/y)",
                "translation_en": "Gamma",
                "translation_tr": "Gamma"
            },
            {
                "term": "Δ",
                "translation": "Delta",
                "name": "Delta",
                "phonetic_en": "[THEL-tah] (like th in the)",
                "phonetic_tr": "[delta] (peltek d/th)",
                "translation_en": "Delta",
                "translation_tr": "Delta"
            },
            {
                "term": "Ε",
                "translation": "Epsilon",
                "name": "Epsilon",
                "phonetic_en": "[EHP-see-lon]",
                "phonetic_tr": "[epsilon]",
                "translation_en": "Epsilon",
                "translation_tr": "Epsilon"
            },
            {
                "term": "Ζ",
                "translation": "Zeta",
                "name": "Zita",
                "phonetic_en": "[ZEE-tah]",
                "phonetic_tr": "[zita]",
                "translation_en": "Zita",
                "translation_tr": "Zita"
            },
            {
                "term": "Η",
                "translation": "Eta",
                "name": "Ita",
                "phonetic_en": "[EE-tah] (ee-sound)",
                "phonetic_tr": "[ita] ('i' sesiyle)",
                "translation_en": "Ita",
                "translation_tr": "Ita"
            },
            {
                "term": "Θ",
                "translation": "Theta",
                "name": "Thita",
                "phonetic_en": "[THEE-tah] (like th in think)",
                "phonetic_tr": "[teta] (peltek t/th)",
                "translation_en": "Thita",
                "translation_tr": "Thita"
            },
            {
                "term": "Ι",
                "translation": "Iota",
                "name": "Iota",
                "phonetic_en": "[ee-OH-tah]",
                "phonetic_tr": "[yota] ('i' sesiyle)",
                "translation_en": "Iota",
                "translation_tr": "Iota"
            },
            {
                "term": "Κ",
                "translation": "Kappa",
                "name": "Kappa",
                "phonetic_en": "[KAH-pah]",
                "phonetic_tr": "[kapa]",
                "translation_en": "Kappa",
                "translation_tr": "Kappa"
            },
            {
                "term": "Λ",
                "translation": "Lambda",
                "name": "Lamda",
                "phonetic_en": "[LAHM-thah]",
                "phonetic_tr": "[lamda]",
                "translation_en": "Lamda",
                "translation_tr": "Lamda"
            },
            {
                "term": "Μ",
                "translation": "Mu",
                "name": "Mi",
                "phonetic_en": "[mee]",
                "phonetic_tr": "[mi]",
                "translation_en": "Mi",
                "translation_tr": "Mi"
            },
            {
                "term": "Ν",
                "translation": "Nu",
                "name": "Ni",
                "phonetic_en": "[nee]",
                "phonetic_tr": "[ni]",
                "translation_en": "Ni",
                "translation_tr": "Ni"
            },
            {
                "term": "Ξ",
                "translation": "Xi",
                "name": "Ksi",
                "phonetic_en": "[ksee]",
                "phonetic_tr": "[ksi]",
                "translation_en": "Ksi",
                "translation_tr": "Ksi"
            },
            {
                "term": "Ο",
                "translation": "Omicron",
                "name": "Omikron",
                "phonetic_en": "[OH-mee-kron]",
                "phonetic_tr": "[omikron]",
                "translation_en": "Omikron",
                "translation_tr": "Omikron"
            },
            {
                "term": "Π",
                "translation": "Pi",
                "name": "Pi",
                "phonetic_en": "[pee]",
                "phonetic_tr": "[pi]",
                "translation_en": "Pi",
                "translation_tr": "Pi"
            },
            {
                "term": "Ρ",
                "translation": "Rho",
                "name": "Ro",
                "phonetic_en": "[roh] (rolled r)",
                "phonetic_tr": "[ro] (titrek r)",
                "translation_en": "Ro",
                "translation_tr": "Ro"
            },
            {
                "term": "Σ",
                "translation": "Sigma",
                "name": "Sigma",
                "phonetic_en": "[SEEG-mah]",
                "phonetic_tr": "[sigma]",
                "translation_en": "Sigma",
                "translation_tr": "Sigma"
            },
            {
                "term": "Τ",
                "translation": "Tau",
                "name": "Taf",
                "phonetic_en": "[tahf]",
                "phonetic_tr": "[taf]",
                "translation_en": "Taf",
                "translation_tr": "Taf"
            },
            {
                "term": "Υ",
                "translation": "Upsilon",
                "name": "Ipsilon",
                "phonetic_en": "[EEP-see-lon] (ee-sound)",
                "phonetic_tr": "[ipsilon] ('i' sesiyle)",
                "translation_en": "Ipsilon",
                "translation_tr": "Ipsilon"
            },
            {
                "term": "Φ",
                "translation": "Phi",
                "name": "Fi",
                "phonetic_en": "[fee]",
                "phonetic_tr": "[fi]",
                "translation_en": "Fi",
                "translation_tr": "Fi"
            },
            {
                "term": "Χ",
                "translation": "Chi",
                "name": "Hi",
                "phonetic_en": "[khee] (raspy h)",
                "phonetic_tr": "[hi] (boğazdan h)",
                "translation_en": "Hi",
                "translation_tr": "Hi"
            },
            {
                "term": "Ψ",
                "translation": "Psi",
                "name": "Psi",
                "phonetic_en": "[psee]",
                "phonetic_tr": "[psi]",
                "translation_en": "Psi",
                "translation_tr": "Psi"
            },
            {
                "term": "Ω",
                "translation": "Omega",
                "name": "Omega",
                "phonetic_en": "[oh-MEH-ghah]",
                "phonetic_tr": "[omega]",
                "translation_en": "Omega",
                "translation_tr": "Omega"
            }
        ]
    }
}

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
        "yes/no and wh- questions": "Evet/Hayır ve Soru Kelimeleri ile Sorular",
        "yes/no questions": "Evet/Hayır Soruları",
        "wh- questions": "Soru Kelimeleri ile Sorular",
        "wh- questions: who, what, where": "Soru Kelimeleri: Kim, Ne, Nerede",
        "wh- questions: who, what, where, when, why": "Soru Kelimeleri: Kim, Ne, Nerede, Ne Zaman, Neden",
        "asking questions and seeking clarifications": "Soru Sorma ve Açıklama İsteme",
        "asking questions": "Soru Sorma",
        "asking questions: wh- questions": "Soru Sorma: Soru Kelimeleri",
        "asking questions: question words": "Soru Sorma: Soru Kelimeleri",
        "seeking clarifications": "Açıklama İsteme",
        "question words": "Soru Kelimeleri",
        "who, what, where": "Kim, Ne, Nerede",
        "who, what, where, when": "Kim, Ne, Nerede, Ne Zaman",
        "who, what, where, when, why": "Kim, Ne, Nerede, Ne Zaman, Neden",
        "constructing simple sentences": "Basit Cümleler Kurma",
        "simple sentences": "Basit Cümleler",
        
        # Politeness & help
        "polite ways to ask for help or information": "Yardım veya Bilgi İstemek İçin Nezaket İfadeleri",
        "polite ways to ask for help": "Yardım İstemek İçin Nezaket İfadeleri",
        "ask for help or information": "Yardım veya Bilgi İsteme",
        "asking for help": "Yardım İsteme",
        "polite expressions and requests": "Nazik İfadeler ve İstekler",
        "polite expressions": "Nazik İfadeler",
        
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
        "everyday survival": "Günlük Hayatta Kalma",
        "survival vocabulary": "Hayatta Kalma Kelimeleri",
        "essential vocabulary for traveling": "Seyahat İçin Temel Kelimeler",
        "essential vocabulary for travel": "Seyahat İçin Temel Kelimeler",
        "essential vocabulary for daily life": "Günlük Yaşam İçin Temel Kelimeler",
        "essential vocabulary for everyday life": "Günlük Yaşam İçin Temel Kelimeler",
        "vocabulary for daily life": "Günlük Yaşam İçin Kelimeler",
        "vocabulary for everyday life": "Günlük Yaşam İçin Kelimeler",
        "daily life": "Günlük Yaşam",
        "everyday life": "Günlük Yaşam",
        "daily life and routines": "Günlük Yaşam ve Rutinler",
        "common objects at home": "Evde Yaygın Nesneler",
        "common objects": "Yaygın Nesneler",
        "objects at home": "Evdeki Nesneler",
        "food and drink words": "Yiyecek ve İçecek Kelimeleri",
        "places in society": "Toplumdaki Yerler",
        "places in the community": "Toplumdaki Yerler",
        "places in community": "Toplumdaki Yerler",
        "vocabulary for traveling": "Seyahat İçin Kelimeler",
        "vocabulary for travel": "Seyahat İçin Kelimeler",
        "essential vocabulary": "Temel Kelimeler",
        "navigating public transportation": "Toplu Taşımada Yol Bulma",
        "navigating public transport": "Toplu Taşımada Yol Bulma",
        "public transportation": "Toplu Taşıma",
        "public transport": "Toplu Taşıma",
        "basic food and drink vocabulary": "Temel Yiyecek ve İçecek Kelimeleri",
        "food and drink vocabulary": "Yiyecek ve İçecek Kelimeleri",
        "food and drink": "Yiyecek ve İçecek",
        "basic food and drinks": "Temel Yiyecek ve İçecekler",
        "daily routines": "Günlük Rutinler",
        "food and dining": "Yiyecek ve Yemek",
        "shopping essentials": "Alışveriş Temelleri",
        "emergency situations": "Acil Durumlar",
        "seeking help: phrases for emergencies": "Yardım İsteme: Acil Durum İfadeleri",
        "seeking help": "Yardım İsteme",
        "phrases for emergencies": "Acil Durum İfadeleri",
        "basic phrases for celebratory situations": "Kutlama Durumları İçin Temel İfadeler",
        "celebratory situations": "Kutlama Durumları",
        "directions and transportation": "Yol Tarifi ve Ulaşım",
        "weather and seasons": "Hava Durumu ve Mevsimler",
        
        # Describing & identity
        "describing yourself and others": "Kendinizi ve Başkalarını Tanımlama",
        "describing yourself": "Kendinizi Tanımlama",
        "describing others": "Başkalarını Tanımlama",
        "basic adjectives for personal description": "Kişisel Tanım İçin Temel Sıfatlar",
        "adjectives for personal description": "Kişisel Tanım İçin Sıfatlar",
        "basic adjectives": "Temel Sıfatlar",
        "personal description": "Kişisel Tanım",
        "personal descriptions": "Kişisel Tanımlar",
        "using 'ser' to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
        "using ser to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
        "talking about age and nationality": "Yaş ve Milliyet Hakkında Konuşma",
        "age and nationality": "Yaş ve Milliyet",
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
        "expression": "İfade",
        "requests": "İstekler",
        "request": "İstek",
        "description": "Tanım",
        "descriptions": "Tanımlar",
        "identity": "Kimlik",
        "identities": "Kimlikler",
        "survival": "Hayatta Kalma",
        "travel": "Seyahat",
        "traveling": "Seyahat",
        "travelling": "Seyahat",
        "transport": "Ulaşım",
        "transportation": "Ulaşım",
        "basics": "Temeller",
        "foundations": "Temeller",
        "celebratory": "Kutlama",
        "celebration": "Kutlama",
        "celebrations": "Kutlamalar",
        "seeking": "İsteme",
        "others": "Başkaları",
        "yourself": "Kendiniz",
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
        "polite": "Nazik",
        "personal": "Kişisel",
        "daily": "Günlük",
        "life": "Yaşam",
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

    TR_LETTERS = re.compile(r'[çğıöşüÇĞİÖŞÜâîû]')
    TR_WORDS = re.compile(r'\b(ve|veya|ile|için|göre|kadar|temel|pratik|uygulama|tekrar|alfabe|selamlaşma|tanıtım|tanıtımlar|günlük|rutinler|sayılar|zaman|saat|aile|ilişkiler|hobiler|yiyecek|yemek|alışveriş|kıyafet|şehir|ulaşım|seyahat|tatil|kültür|kültürel|bilgiler|bağlam|dilbilgisi|kelimeler|kelime|kelimeleri|cümleler|cümle|cümleleri|ifadeler|ifade|ifadeleri|fiiller|fiil|sıfatlar|sıfat|zamirler|zamir|sorular|soru|soruları|sorusu|çevremizdeki|dünya|doğa|sağlık|iş|okul|ev|yerler|yol|tarifi|hava|durumu|mevsimler|doktora|gitmek|kutlama|durumları|işlevsel|topluluk|hediyeler|kutlamalar|tanım|tanımlama|kimlik|kim|ne|nerede|nereli|nasıl|neden|yanıt|yanıtlar|cevap|cevaplar|kurma|oluşturma|kullanma|kullanımı|anlatma|sorma|konuşma)\b', re.IGNORECASE)
    EN_WORDS = re.compile(
        r'\b(the|and|of|to|in|for|with|on|at|from|by|about|your|our|their|my|his|her|its|you|we|they|'
        r'describing|talking|using|navigating|understanding|introducing|asking|making|expressing|telling|visiting|seeking|'
        r'review|practice|practical|application|foundations|basics|intermediate|advanced|grammar|vocabulary|'
        r'words|phrases|sentences|daily|activities|routines|food|dining|shopping|environment|travel|traveling|travelling|questions|answers|'
        r'math|operations|culture|insights|context|customs|survival|numbers|counting|alphabet|vowels|consonants|'
        r'pronunciation|phonetics|rules|check|guide|overview|summary|world|around|us|'
        r'functional|language|situations|celebratory|emergencies|emergency|health|traditions|festivals|leisure|sports|'
        r'hobbies|community|recommendations|transactions|menus|accessories|sizes|colors|transport|transportation|places|'
        r'personal|description|identity|adjectives|adjective|nouns|noun|verbs|verb|conversation|dialogues|dialogue|'
        r'objects|friends|friendship|free|time|interests|ordering|buying|giving|directions|family|members|'
        r'feelings|emotions|workplace|office|home|school|weather|seasons|calendar|dates|essential|everyday|simple|'
        r'who|what|where|when|why|how|which|whose|whom)\b',
        re.IGNORECASE
    )

    @classmethod
    def clean_stutter(cls, text: str) -> str:
        """Removes word duplication, stuttering, and awkward repetitive phrasing."""
        if not text:
            return ""
        t = str(text).strip()
        t = re.sub(r'\bGünlük\s+Hayatta\s+Hayatta\s+Kalma\b', 'Günlük Hayatta Kalma', t, flags=re.IGNORECASE)
        t = re.sub(r'\bHayatta\s+Hayatta\b', 'Hayatta', t, flags=re.IGNORECASE)
        t = re.sub(r'\bve\s+ve\b', 've', t, flags=re.IGNORECASE)
        t = re.sub(r'\bveya\s+veya\b', 'veya', t, flags=re.IGNORECASE)
        t = re.sub(r'\biçin\s+için\b', 'için', t, flags=re.IGNORECASE)
        t = re.sub(r'\bde\s+de\b', 'de', t, flags=re.IGNORECASE)
        t = re.sub(r'\bda\s+da\b', 'da', t, flags=re.IGNORECASE)
        t = re.sub(r'\bile\s+ile\b', 'ile', t, flags=re.IGNORECASE)
        t = re.sub(r'\bWh-\s*Soruları\b', 'Soru Kelimeleri', t, flags=re.IGNORECASE)
        t = re.sub(r'\bWh-\s*Questions\b', 'Soru Kelimeleri', t, flags=re.IGNORECASE)
        t = re.sub(r'\bWh-\b', 'Soru Kelimeleri', t, flags=re.IGNORECASE)
        def _repl_dup(m):
            w = m.group(1)
            if w.lower() in ('yavaş', 'adım', 'tek', 'ayrı', 'az'):
                return m.group(0)
            return w
        t = re.sub(r'\b([a-zA-ZçğıöşüÇĞİÖŞÜâîû]+)\s+\1\b', _repl_dup, t, flags=re.IGNORECASE)
        t = re.sub(r',\s*ve\b', ' ve', t, flags=re.IGNORECASE)
        t = re.sub(r'\s{2,}', ' ', t).strip()
        return t

    @classmethod
    def is_hybrid_or_english(cls, text: str) -> bool:
        if not text or not isinstance(text, str):
            return False
        t = text.strip()
        if not t:
            return False
        low = t.lower()
        if re.search(r'\bve\s+ve\b', low) or re.search(r'\bhayatta\s+hayatta\b', low) or "pratik application" in low or "around us" in low or re.search(r'\bwh[- ]', low):
            return True
        quoted = set(m.strip("'\"").lower() for m in re.findall(r"['\"][^'\"]+['\"]", t))
        matches = [m.lower() for m in cls.EN_WORDS.findall(t)]
        leaked = [m for m in matches if m not in quoted]
        has_tr = bool(cls.TR_LETTERS.search(t) or cls.TR_WORDS.search(t))
        if leaked and has_tr:
            return True
        total_tokens = len(t.split())
        if total_tokens > 0 and len(leaked) >= (total_tokens / 2):
            return True
        return False

    @classmethod
    def is_clean_turkish(cls, text: str) -> bool:
        if not text or not isinstance(text, str):
            return False
        t = text.strip()
        if not t:
            return False
        if re.search(r'\bHayatta\s+Hayatta\b', t, re.IGNORECASE) or re.search(r'\bve\s+ve\b', t, re.IGNORECASE):
            return False
        if cls.is_hybrid_or_english(t):
            return False
        has_tr_chars = bool(cls.TR_LETTERS.search(t))
        has_tr_lexicon = bool(cls.TR_WORDS.search(t))
        return has_tr_chars or has_tr_lexicon

    @classmethod
    def clean_hybrids(cls, text: str) -> str:
        if not text:
            return ""
        t = str(text).strip()
        hybrids = [
            (r'\bWh-\s*Soruları\b', 'Soru Kelimeleri'),
            (r'\bWh-\s*Questions\b', 'Soru Kelimeleri'),
            (r'\bWh-\b', 'Soru Kelimeleri'),
            (r'Personal\s+Description\s+İçin', 'Kişisel Tanım İçin'),
            (r'Personal\s+Description', 'Kişisel Tanım'),
            (r'Traveling\s+İçin', 'Seyahat İçin'),
            (r'Travel\s+İçin', 'Seyahat İçin'),
            (r'Günlük\s+Hayatta\s+Hayatta\s+Kalma', 'Günlük Hayatta Kalma'),
            (r'Hayatta\s+Hayatta', 'Hayatta'),
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
        t = cls.clean_stutter(t)
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

        # Check if already pure Turkish (must not have remaining English keywords or stutter)
        if cls.is_clean_turkish(clean) and not cls.is_hybrid_or_english(clean):
            m_half = re.match(r"^(\d+)'den\s+(\d+)'(?:ye|e)\s+sayma\s*[:\-]\s*(.*)$", clean, re.IGNORECASE)
            if m_half:
                n1, n2, rest = m_half.group(1), m_half.group(2), m_half.group(3).strip()
                return cls.clean_stutter(f"{n1}'den {n2}'e Sayma: {cls.translate(rest)}")
            return cls.clean_stutter(clean)

        # Check exact match in phrase dictionary FIRST
        if low in cls.PHRASES:
            return cls.clean_stutter(cls.PHRASES[low])

        # Check title map from bilingual_materials.json (validated)
        tmap = _get_bm_title_map()
        cand = tmap.get(t) or tmap.get(clean)
        if not cand:
            for k, v in tmap.items():
                if k.lower() == low:
                    cand = v
                    break
        if cand:
            cand_clean = cls.clean_stutter(cand)
            if cls.is_clean_turkish(cand_clean) and not cls.is_hybrid_or_english(cand_clean):
                return cand_clean

        # Handle colon compound "A: B"
        if ":" in clean:
            parts = [p.strip() for p in clean.split(":", 1)]
            p1 = cls.translate(parts[0])
            p2 = cls.translate(parts[1])
            if cls.is_clean_turkish(p1) and cls.is_clean_turkish(p2) and not cls.is_hybrid_or_english(p1) and not cls.is_hybrid_or_english(p2):
                return cls.clean_stutter(f"{p1}: {p2}")

        # Handle "A vs. B" or "A versus B"
        m_vs = re.match(r'^(.*?)\s+(?:vs\.?|versus)\s+(.*)$', clean, re.IGNORECASE)
        if m_vs:
            s1 = cls.translate(m_vs.group(1).strip())
            s2 = cls.translate(m_vs.group(2).strip())
            return cls.clean_stutter(f"{s1} ve {s2} Karşılaştırması")

        # Handle "Getting Acquainted with (the\s+)?(Language/Topic)"
        m_acq = re.match(r'^getting\s+acquainted\s+with\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_acq:
            sub = m_acq.group(2).strip()
            sub_clean = re.sub(r'\s+language$', '', sub, flags=re.IGNORECASE).strip().lower()
            if sub_clean in cls.LANGUAGES:
                lang_name = cls.LANGUAGES[sub_clean][0]
                return cls.clean_stutter(f"{lang_name} ile Tanışma")
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr} ile Tanışma")

        # Handle "How to Ask and Answer 'X'" or "How to Ask and Answer X"
        m_ask_ans = re.match(r'^how\s+to\s+ask\s+and\s+answer\s+[\'"]?(.*?)[\'"]?$', clean, re.IGNORECASE)
        if m_ask_ans:
            sub = m_ask_ans.group(1).strip()
            sub_low = sub.lower()
            if sub_low in cls.QUOTED_EXPRESSIONS:
                sub_tr = cls.QUOTED_EXPRESSIONS[sub_low]
                return cls.clean_stutter(f"'{sub_tr}' Diye Sorma ve Cevaplama")
            return cls.clean_stutter(f"'{sub}' Diye Sorma ve Cevaplama")

        # Handle "How to (Verb) (X)"
        m_howto = re.match(r'^how\s+to\s+(.*?)\s+(.*)$', clean, re.IGNORECASE)
        if m_howto:
            verb = m_howto.group(1).strip()
            rest = m_howto.group(2).strip()
            rest_tr = cls.translate(rest)
            verb_tr = cls.VOCABULARY.get(verb.lower(), verb)
            return cls.clean_stutter(f"{rest_tr} {verb_tr} Yolları")

        # Handle "Sharing (X)"
        m_sharing = re.match(r'^sharing\s+(.*)$', clean, re.IGNORECASE)
        if m_sharing:
            sub = cls.translate(m_sharing.group(1).strip())
            return cls.clean_stutter(f"{sub} Paylaşma")

        # Handle "Exploring (X)"
        m_exp = re.match(r'^exploring\s+(.*)$', clean, re.IGNORECASE)
        if m_exp:
            sub = cls.translate(m_exp.group(1).strip())
            return cls.clean_stutter(f"{sub} Keşfetme")

        # Handle "Mastering (X)"
        m_mas = re.match(r'^mastering\s+(.*)$', clean, re.IGNORECASE)
        if m_mas:
            sub = cls.translate(m_mas.group(1).strip())
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr} Konusunda Uzmanlaşma")

        # Handle "Formulating (X) Questions"
        m_form_q = re.match(r'^formulating\s+(.*?)\s+questions$', clean, re.IGNORECASE)
        if m_form_q:
            sub = m_form_q.group(1).strip()
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr} Soruları Oluşturma")

        # Handle "Formulating (X)"
        m_form = re.match(r'^formulating\s+(.*)$', clean, re.IGNORECASE)
        if m_form:
            sub = m_form.group(1).strip()
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr} Oluşturma")

        # Handle "Using 'X' to (Y)" or "Using X to (Y)"
        m_using_to = re.match(r"^using\s+(.*?)\s+to\s+(.*)$", clean, re.IGNORECASE)
        if m_using_to:
            target_item = m_using_to.group(1).strip()
            action_item = m_using_to.group(2).strip()
            act_tr = cls.translate(action_item)
            if cls.is_clean_turkish(act_tr) and not cls.is_hybrid_or_english(act_tr):
                cleaned_target = target_item.replace("'", "").replace('"', '').capitalize()
                return cls.clean_stutter(f"'{cleaned_target}' Kullanarak {act_tr}")

        # Handle "Constructing (X) in (the\s+)?(Y)"
        m_const_in = re.match(r'^constructing\s+(.*?)\s+in\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_const_in:
            s1 = cls.translate(m_const_in.group(1).strip())
            s2 = cls.translate(m_const_in.group(3).strip())
            if cls.is_clean_turkish(s1) and cls.is_clean_turkish(s2) and not cls.is_hybrid_or_english(s1) and not cls.is_hybrid_or_english(s2):
                return cls.clean_stutter(f"{s2}'de {s1} Kurma")

        # Handle "Constructing (X)"
        m_const = re.match(r'^constructing\s+(.*)$', clean, re.IGNORECASE)
        if m_const:
            sub = cls.translate(m_const.group(1).strip())
            if cls.is_clean_turkish(sub) and not cls.is_hybrid_or_english(sub):
                return cls.clean_stutter(f"{sub} Kurma")

        # Handle "Polite Ways to (X)"
        m_polite = re.match(r'^polite\s+ways\s+to\s+(.*)$', clean, re.IGNORECASE)
        if m_polite:
            sub = cls.translate(m_polite.group(1).strip())
            if cls.is_clean_turkish(sub) and not cls.is_hybrid_or_english(sub):
                return cls.clean_stutter(f"{sub} İçin Nezaket İfadeleri")

        # Handle "Geography and Major Cities of (the\s+)?(X)"
        m_geo = re.match(r'^geography\s+and\s+major\s+cities\s+of\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_geo:
            sub = m_geo.group(2).strip()
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr} Coğrafyası ve Başlıca Şehirleri")

        # Handle "Celebrations and Traditions in (the\s+)?(X)"
        m_cel = re.match(r'^celebrations\s+and\s+traditions\s+in\s+(the\s+)?(.*)$', clean, re.IGNORECASE)
        if m_cel:
            sub = m_cel.group(2).strip()
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"{sub_tr}'de Kutlamalar ve Gelenekler")

        # Handle "Cultural Contexts: (X)" or "Cultural Contexts of (X)"
        m_cult = re.match(r'^cultural\s+contexts?\s*(?:of|in)?\s*(.*)$', clean, re.IGNORECASE)
        if m_cult and m_cult.group(1).strip():
            sub = m_cult.group(1).strip()
            sub_tr = cls.translate(sub)
            return cls.clean_stutter(f"Kültürel Bağlamlar: {sub_tr}")

        # Handle "Counting from (N1) to (N2)"
        m_count = re.match(r'^counting\s+from\s+(\d+)\s+to\s+(\d+)(.*)$', clean, re.IGNORECASE)
        if m_count:
            n1, n2, extra = m_count.group(1), m_count.group(2), m_count.group(3).strip()
            suffix = "e" if n2.endswith("00") or n2 in ["1", "3", "4", "5", "8", "70", "80"] else "a"
            res = f"{n1}'den {n2}'{suffix} Sayma"
            extra_clean = re.sub(r'^[:\s\-]+', '', extra).strip()
            if extra_clean:
                res += f": {cls.translate(extra_clean)}"
            return cls.clean_stutter(res)

        # Handle "Introduction to (X)"
        m_intro = re.match(r'^introduction\s+to\s+(.*)$', clean, re.IGNORECASE)
        if m_intro:
            sub = cls.translate(m_intro.group(1).strip())
            return cls.clean_stutter(sub if sub.endswith("Giriş") else f"{sub}'e Giriş")

        # Handle "Using (X) in (Y)"
        m_using_in = re.match(r'^using\s+(.*?)\s+in\s+(.*)$', clean, re.IGNORECASE)
        if m_using_in:
            s1 = cls.translate(m_using_in.group(1).strip())
            s2 = cls.translate(m_using_in.group(2).strip())
            if cls.is_clean_turkish(s1) and cls.is_clean_turkish(s2) and not cls.is_hybrid_or_english(s1) and not cls.is_hybrid_or_english(s2):
                return cls.clean_stutter(f"{s2}'de {s1} Kullanımı")

        # Handle "Using (X)"
        m_using = re.match(r'^using\s+(.*)$', clean, re.IGNORECASE)
        if m_using:
            sub = cls.translate(m_using.group(1).strip())
            if cls.is_clean_turkish(sub) and not cls.is_hybrid_or_english(sub):
                return cls.clean_stutter(f"{sub} Kullanımı")

        # Handle "Talking About (X)"
        m_talking = re.match(r'^talking\s+about\s+(.*)$', clean, re.IGNORECASE)
        if m_talking:
            sub = cls.translate(m_talking.group(1).strip())
            if cls.is_clean_turkish(sub) and not cls.is_hybrid_or_english(sub):
                return cls.clean_stutter(f"{sub} Hakkında Konuşma")

        # Handle "Navigating (X)"
        m_nav = re.match(r'^navigating\s+(.*)$', clean, re.IGNORECASE)
        if m_nav:
            sub = cls.translate(m_nav.group(1).strip())
            if cls.is_clean_turkish(sub) and not cls.is_hybrid_or_english(sub):
                if "taşıma" in sub.lower():
                    return cls.clean_stutter(f"{sub}da Yol Bulma")
                return cls.clean_stutter(f"{sub}'de Yol Bulma")

        # Handle "X for Y" - SAFETY INVARIANT: both parts MUST be clean Turkish
        m_for = re.match(r'^(.*?)\s+for\s+(.*)$', clean, re.IGNORECASE)
        if m_for:
            s1 = cls.translate(m_for.group(1).strip())
            s2 = cls.translate(m_for.group(2).strip())
            if cls.is_clean_turkish(s1) and cls.is_clean_turkish(s2) and not cls.is_hybrid_or_english(s1) and not cls.is_hybrid_or_english(s2):
                return cls.clean_stutter(f"{s2} İçin {s1}")

        # Handle "X in [Language]"
        for lang_en, (lang_nom, lang_adj, lang_loc) in cls.LANGUAGES.items():
            m_lang = re.match(rf'^(.*?)\s+in\s+{lang_en}$', clean, re.IGNORECASE)
            if m_lang:
                sub = m_lang.group(1).strip()
                sub_tr = cls.translate(sub)
                if cls.is_clean_turkish(sub_tr) and not cls.is_hybrid_or_english(sub_tr):
                    return cls.clean_stutter(f"{lang_loc} {sub_tr}")

        # Handle "X and Y" conjunction - SAFETY INVARIANT: both parts MUST be clean Turkish
        if " and " in clean.lower():
            parts = re.split(r'\s+and\s+', clean, flags=re.IGNORECASE)
            if len(parts) == 2:
                p1 = cls.translate(parts[0].strip())
                p2 = cls.translate(parts[1].strip())
                if cls.is_clean_turkish(p1) and cls.is_clean_turkish(p2) and not cls.is_hybrid_or_english(p1) and not cls.is_hybrid_or_english(p2):
                    return cls.clean_stutter(f"{p1} ve {p2}")

        # Handle comma-separated list "A, B, and C" or "A, B, C"
        if "," in clean:
            raw_items = re.split(r',\s*(?:and\s+)?', clean)
            if len(raw_items) > 1:
                tr_items = [cls.translate(item.strip()) for item in raw_items]
                if all(cls.is_clean_turkish(ti) and not cls.is_hybrid_or_english(ti) for ti in tr_items):
                    if len(tr_items) == 2:
                        return cls.clean_stutter(f"{tr_items[0]} ve {tr_items[1]}")
                    return cls.clean_stutter(", ".join(tr_items[:-1]) + f" ve {tr_items[-1]}")

        # Check Language + Noun (e.g. "German Language", "Spanish Alphabet")
        for lang_en, (lang_nom, lang_adj, lang_loc) in cls.LANGUAGES.items():
            if low == f"the {lang_en} language" or low == f"{lang_en} language":
                return f"{lang_nom} Dili"
            m_lang_noun = re.match(rf'^{lang_en}\s+(.*)$', clean, re.IGNORECASE)
            if m_lang_noun:
                sub = m_lang_noun.group(1).strip()
                sub_tr = cls.translate(sub)
                return cls.clean_stutter(f"{lang_adj} {sub_tr}")

        # Check Adjective + Noun (e.g. "Basic Greetings", "Essential Quantities")
        words = clean.split()
        if len(words) == 2:
            w1 = words[0].lower()
            w2 = words[1].lower()
            if w1 in cls.VOCABULARY and w2 in cls.VOCABULARY:
                return cls.clean_stutter(f"{cls.VOCABULARY[w1]} {cls.VOCABULARY[w2]}")

        # Only if ALL tokens are recognized vocabulary words (never create mixed-language hybrids)
        translated_words = []
        all_translated = True
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
                all_translated = False
                break

        if all_translated and translated_words:
            res = " ".join(translated_words)
            if cls.is_clean_turkish(res) and not cls.is_hybrid_or_english(res):
                return cls.clean_stutter(res)

        return clean


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





# ── PRACTICAL VOCABULARY EXAMPLES & COLLOCATIONS BANK ──
VOCAB_EXAMPLE_BANK = {
    "Spanish": {
        "leer": {
            "example": "Leo un libro fascinante cada noche.",
            "example_en": "I read a fascinating book every night.",
            "example_tr": "Her gece sürükleyici bir kitap okurum.",
            "tip_en": "Irregular gerund: 'leyendo'. Common phrase: 'leer en voz alta' (read aloud).",
            "tip_tr": "Ulaç hali kuralsızdır: 'leyendo'. Sık kullanılan kalıp: 'leer en voz alta' (sesli okumak)."
        },
        "escribir": {
            "example": "Ella escribe un diario todos los días.",
            "example_en": "She writes in a diary every day.",
            "example_tr": "O her gün günlük yazar.",
            "tip_en": "Past participle is irregular: 'escrito' (written).",
            "tip_tr": "Geçmiş zaman sıfat-fiili kuralsızdır: 'escrito' (yazılmış)."
        },
        "jugar": {
            "example": "Jugamos al fútbol los fines de semana.",
            "example_en": "We play soccer on weekends.",
            "example_tr": "Hafta sonları futbol oynarız.",
            "tip_en": "Stem-changing verb (u -> ue). Always takes preposition 'a' with sports: 'jugar al tenis'.",
            "tip_tr": "Kök değişimi yapar (u -> ue). Spor ve oyunlarda daima 'a' edatı alır: 'jugar al fútbol'."
        },
        "nadar": {
            "example": "Nado en la piscina olímpica cada sábado.",
            "example_en": "I swim in the Olympic pool every Saturday.",
            "example_tr": "Her cumartesi olimpik havuzda yüzerim.",
            "tip_en": "Regular -ar verb. Pair with 'en': 'nadar en el mar' (swim in the sea).",
            "tip_tr": "Düzenli -ar fiilidir. 'en' edatıyla kullanılır: 'nadar en el mar' (denizde yüzmek)."
        },
        "dibujar": {
            "example": "Me gusta dibujar paisajes a lápiz.",
            "example_en": "I like drawing landscapes in pencil.",
            "example_tr": "Karakalemle manzara çizmeyi severim.",
            "tip_en": "The noun form is 'el dibujo' (drawing/sketch).",
            "tip_tr": "İsim formu 'el dibujo' (çizim/resim) şeklindedir."
        },
        "cocinar": {
            "example": "Mi padre cocina una paella deliciosa.",
            "example_en": "My father cooks a delicious paella.",
            "example_tr": "Babam çok lezzetli bir paella pişirir.",
            "tip_en": "Related to 'la cocina' (the kitchen).",
            "tip_tr": "'La cocina' (mutfak) sözcüğüyle aynı köktendir."
        },
        "viajar": {
            "example": "Quiero viajar por todo el mundo.",
            "example_en": "I want to travel all over the world.",
            "example_tr": "Bütün dünyayı gezmek istiyorum.",
            "tip_en": "Transport requires preposition 'en': 'viajar en tren / en avión'.",
            "tip_tr": "Ulaşım araçlarında 'en' edatı kullanılır: 'viajar en tren / en avión'."
        },
        "bailar": {
            "example": "Ellos bailan salsa los viernes por la noche.",
            "example_en": "They dance salsa on Friday nights.",
            "example_tr": "Cuma geceleri salsa dansı yaparlar.",
            "tip_en": "Common phrase: 'bailar con' (dance with someone).",
            "tip_tr": "'Bailar con' (biriyle dans etmek) yapısıyla sık kullanılır."
        },
        "cantar": {
            "example": "Ella canta muy bien en el coro de la escuela.",
            "example_en": "She sings very well in the school choir.",
            "example_tr": "Okul korosunda çok güzel şarkı söyler.",
            "tip_en": "The noun is 'la canción' (the song).",
            "tip_tr": "İsim formu 'la canción' (şarkı) şeklindedir."
        },
        "escuchar musica": {
            "example": "Escucho música relajante mientras estudio.",
            "example_en": "I listen to relaxing music while studying.",
            "example_tr": "Ders çalışırken dinlendirici müzik dinlerim.",
            "tip_en": "Does not take a preposition for objects: 'escuchar música' (NOT 'escuchar a música').",
            "tip_tr": "Nesne alırken araya edat almaz: 'escuchar música'."
        },
        "ver peliculas": {
            "example": "Los domingos vemos películas en casa.",
            "example_en": "On Sundays we watch movies at home.",
            "example_tr": "Pazar günleri evde film izleriz.",
            "tip_en": "Irregular first-person present: 'yo veo'.",
            "tip_tr": "'Ver' fiilinin ben çekimi kuralsızdır: 'yo veo'."
        },
        "hacer ejercicio": {
            "example": "Hago ejercicio en el parque todas las mañanas.",
            "example_en": "I exercise in the park every morning.",
            "example_tr": "Her sabah parkta egzersiz yaparım.",
            "tip_en": "First-person present is irregular: 'yo hago'.",
            "tip_tr": "'Hacer' fiilinin şimdiki zaman 1. şahsı kuralsızdır: 'yo hago'."
        },
        "correr": {
            "example": "Corro cinco kilómetros cada mañana.",
            "example_en": "I run five kilometers every morning.",
            "example_tr": "Her sabah beş kilometre koşarım.",
            "tip_en": "Regular -er verb.",
            "tip_tr": "Düzenli -er fiilidir."
        },
        "hobi": {
            "example": "¿Cuál es tu pasatiempo favorito?",
            "example_en": "What is your favorite hobby?",
            "example_tr": "En sevdiğin hobi nedir?",
            "tip_en": "Native Spanish term is 'el pasatiempo' (pasar + tiempo).",
            "tip_tr": "İspanyolcada özgün karşılığı 'el pasatiempo' (vakit geçirme) sözcüğüdür."
        },
        "pasatiempo": {
            "example": "La fotografía es mi pasatiempo principal.",
            "example_en": "Photography is my main hobby.",
            "example_tr": "Fotoğrafçılık benim başlıca hobimdir.",
            "tip_en": "Compound word: 'pasar' (spend) + 'tiempo' (time). Plural: 'los pasatiempos'.",
            "tip_tr": "'Pasar' (geçirmek) ve 'tiempo' (zaman) birleşimidir. Çoğulu: 'los pasatiempos'."
        },
        "cero": {
            "example": "La temperatura bajó a cero grados esta noche.",
            "example_en": "The temperature dropped to zero degrees tonight.",
            "example_tr": "Sıcaklık bu gece sıfır dereceye düştü.",
            "tip_en": "Used with plural nouns: 'cero grados', 'cero errores'.",
            "tip_tr": "Çoğul isimlerle kullanılır: 'cero grados' (sıfır derece)."
        },
        "uno": {
            "example": "Solo queda un billete para el tren de las ocho.",
            "example_en": "Only one ticket remains for the eight o'clock train.",
            "example_tr": "Saat sekiz treni için sadece bir bilet kaldı.",
            "tip_en": "Shortens to 'un' before masculine singular nouns: 'un billete'. Feminine is 'una'.",
            "tip_tr": "Eril tekil isimlerden önce 'un' şeklinde kısalır: 'un billete'. Dişili 'una'dır."
        },
        "dos": {
            "example": "Necesito dos billetes de ida y vuelta para Madrid.",
            "example_en": "I need two round-trip tickets to Madrid.",
            "example_tr": "Madrid için iki gidiş-dönüş bileti istiyorum.",
            "tip_en": "Invariable for gender; used with both masculine and feminine nouns: 'dos billetes', 'dos maletas'.",
            "tip_tr": "Cinsiyete göre değişmez; hem eril hem dişil isimlerle 'dos' olarak kullanılır."
        },
        "tres": {
            "example": "El museo abre las puertas a las tres de la tarde.",
            "example_en": "The museum opens its doors at three in the afternoon.",
            "example_tr": "Müze kapılarını öğleden sonra saat üçte açıyor.",
            "tip_en": "Used in clock times with the feminine plural article: 'a las tres'.",
            "tip_tr": "Saat söylerken dişil çoğul tanımlıkla kullanılır: 'a las tres' (saat üçte)."
        },
        "cuatro": {
            "example": "Tenemos una reunión programada en la sala número cuatro.",
            "example_en": "We have a meeting scheduled in room number four.",
            "example_tr": "Dört numaralı salonda planlanmış bir toplantımız var.",
            "tip_en": "Invariable cardinal number; stays 'cuatro' before any noun.",
            "tip_tr": "Değişmez sayma sayısıdır; her ismin önünde 'cuatro' olarak kalır."
        },
        "cinco": {
            "example": "El tren de cercanías sale de la vía cinco en diez minutos.",
            "example_en": "The commuter train departs from track five in ten minutes.",
            "example_tr": "Banliyö treni on dakika içinde beş numaralı perondan kalkıyor.",
            "tip_en": "Remains unchanged before masculine and feminine nouns: 'cinco euros', 'cinco horas'.",
            "tip_tr": "Eril ve dişil isimlerin önünde değişmez: 'cinco euros' (beş avro), 'cinco horas' (beş saat)."
        },
        "seis": {
            "example": "El vuelo con destino a Barcelona tiene un retraso de seis horas.",
            "example_en": "The flight to Barcelona has a six-hour delay.",
            "example_tr": "Barselona uçuşunda altı saatlik bir gecikme var.",
            "tip_en": "Pronounced with a clear diphthong: [seys]. Invariable for gender.",
            "tip_tr": "Diftong ile telaffuz edilir: [seys]. Cinsiyete göre değişmez."
        },
        "siete": {
            "example": "El supermercado cierra todos los días a las siete en punto.",
            "example_en": "The supermarket closes every day at seven sharp.",
            "example_tr": "Süpermarket her gün tam saat yedide kapanıyor.",
            "tip_en": "Takes 'a las' in clock expressions: 'a las siete de la tarde'.",
            "tip_tr": "Saat ifadelerinde 'a las' kalıbı alır: 'a las siete' (saat yedide)."
        },
        "ocho": {
            "example": "El desayuno buffet se sirve a partir de las ocho de la mañana.",
            "example_en": "The breakfast buffet is served starting at eight in the morning.",
            "example_tr": "Açık büfe kahvaltı sabah saat sekizden itibaren servis edilir.",
            "tip_en": "Starts with silent 'h': pronounced [OH-choh].",
            "tip_tr": "'H' harfi sessizdir; doğrudan [oço] olarak okunur."
        },
        "nueve": {
            "example": "La habitación número nueve está situada en la segunda planta.",
            "example_en": "Room number nine is located on the second floor.",
            "example_tr": "Dokuz numaralı oda ikinci katta yer almaktadır.",
            "tip_en": "Written with 'v', pronounced as a soft bilabial consonant.",
            "tip_tr": "'V' harfiyle yazılır ve dudaklar birbirine hafif değdirilerek sesletilir."
        },
        "diez": {
            "example": "El menú del día incluye primer plato, postre y bebida por diez euros.",
            "example_en": "The daily menu includes first course, dessert, and drink for ten euros.",
            "example_tr": "Günün menüsüne başlangıç, tatlı ve içecek dahil on avrodur.",
            "tip_en": "Spelled with final 'z'. Pluralized in derivatives as 'decenas'.",
            "tip_tr": "Sonunda 'z' harfi bulunur. İspanya'da peltek, Latin Amerika'da 's' gibi sesletilir."
        },
        "once": {
            "example": "El tren nocturno llega a la estación central a las once de la noche.",
            "example_en": "The night train arrives at the central station at eleven at night.",
            "example_tr": "Gece treni merkez istasyona gece saat on birde varıyor.",
            "tip_en": "Irregular cardinal number derived from Latin 'undecim'.",
            "tip_tr": "Latinceden gelen kuralsız sayma sayısıdır; telaffuzu [onse] şeklindedir."
        },
        "doce": {
            "example": "El registro de salida del hotel debe completarse antes de las doce del mediodía.",
            "example_en": "Hotel check-out must be completed before twelve noon.",
            "example_tr": "Otelden çıkış işlemleri öğlen saat on ikiden önce tamamlanmalıdır.",
            "tip_en": "'Las doce' can mean noon ('las doce del mediodía') or midnight ('las doce de la noche').",
            "tip_tr": "'Las doce del mediodía' öğlen 12'yi, 'las doce de la noche' gece yarısı 12'yi ifade eder."
        },
        "trece": {
            "example": "El ascensor del hotel internacional no dispone de parada en el piso trece.",
            "example_en": "The international hotel elevator does not have a stop on the thirteenth floor.",
            "example_tr": "Uluslararası otelin asansöründe on üçüncü kat durağı bulunmuyor.",
            "tip_en": "In Hispanic culture, Tuesday the 13th ('martes 13') is considered superstitious rather than Friday the 13th.",
            "tip_tr": "İspanyol kültüründe uğursuz gün Cuma 13 değil, Salı 13'tür ('martes 13')."
        },
        "catorce": {
            "example": "El congreso sobre lingüística aplicada durará catorce días lectivos.",
            "example_en": "The conference on applied linguistics will last fourteen working days.",
            "example_tr": "Uygulamalı dilbilim kongresi on dört çalışma günü sürecek.",
            "tip_en": "Invariable cardinal number; derived from Latin 'quattuordecim'.",
            "tip_tr": "Değişmez sayma sayısıdır; [katorse] şeklinde okunur."
        },
        "quince": {
            "example": "El trayecto en metro directo hasta el aeropuerto dura solo quince minutos.",
            "example_en": "The direct metro ride to the airport takes only fifteen minutes.",
            "example_tr": "Havalimanına doğrudan metro yolculuğu sadece on beş dakika sürüyor.",
            "tip_en": "'Quince días' is the standard Spanish idiom for 'two weeks' or a fortnight.",
            "tip_tr": "'Quince días' (on beş gün), İspanyolcada iki haftalık süreyi ifade eden standart kalıptır."
        },
        "dieciséis": {
            "example": "La sesión académica se impartirá en el aula dieciséis a primera hora.",
            "example_en": "The academic session will be taught in classroom sixteen first thing in the morning.",
            "example_tr": "Akademik ders sabah erken saatte on altı numaralı derslikte işlenecektir.",
            "tip_en": "Written as one word with an acute accent on the last syllable: 'dieciséis'.",
            "tip_tr": "Bitişik yazılır ve son hecesinde vurgu işareti (tilde) taşır: 'dieciséis'."
        },
        "diecisiete": {
            "example": "La pinacoteca histórica ofrece entrada libre a partir de las diecisiete horas.",
            "example_en": "The historic art gallery offers free admission starting at 5:00 PM (seventeen hours).",
            "example_tr": "Tarihi sanat galerisi saat on yediden itibaren ücretsiz giriş sunmaktadır.",
            "tip_en": "Compound number written as a single word: 'diez y siete' -> 'diecisiete'.",
            "tip_tr": "'Diez y siete' yapısından türemiş tek kelimelik bileşiktir: 'diecisiete'."
        },
        "dieciocho": {
            "example": "Para formalizar un contrato de alquiler se requiere tener al menos dieciocho años.",
            "example_en": "To formalize a rental lease, one must be at least eighteen years old.",
            "example_tr": "Kira sözleşmesi imzalamak için en az on sekiz yaşında olmak gerekir.",
            "tip_en": "Expressing age in Spanish uses the verb 'tener': 'tener dieciocho años'.",
            "tip_tr": "İspanyolcada yaş belirtirken 'ser' değil, 'tener' (sahip olmak) fiili kullanılır: 'tener dieciocho años'."
        },
        "diecinueve": {
            "example": "El autobús interurbano con destino a Valencia saldrá del andén diecinueve.",
            "example_en": "The intercity bus to Valencia will depart from platform nineteen.",
            "example_tr": "Valensiya'ya giden şehirlerarası otobüs on dokuz numaralı perondan hareket edecektir.",
            "tip_en": "Single compound word: 'diecinueve'. Invariable before masculine or feminine nouns.",
            "tip_tr": "Bitişik yazılan birleşik sayıdır: 'diecinueve'. Her iki cinsiyette de değişmez."
        },
        "veinte": {
            "example": "El billete combinado de autobús y tranvía cuesta veinte euros al mes.",
            "example_en": "The combined bus and tram ticket costs twenty euros per month.",
            "example_tr": "Kombine otobüs ve tramvay bileti ayda yirmi avrodur.",
            "tip_en": "Changes to 'veinti-' when forming compound numbers from 21 to 29: 'veintiuno', 'veintidós'.",
            "tip_tr": "21-29 arası bileşik sayılarda 'veinti-' şekline dönüşür: 'veintiuno', 'veintidós'."
        }
    },
    "German": {
        "lesen": {
            "example": "Ich lese jeden Abend ein deutsches Buch.",
            "example_en": "I read a German book every evening.",
            "example_tr": "Her akşam Almanca bir kitap okurum.",
            "tip_en": "Stem-changing verb: du liest, er/sie liest.",
            "tip_tr": "Kök değişimi yapan fiildir: du liest, er liest."
        },
        "schreiben": {
            "example": "Er schreibt eine E-Mail an seinen Lehrer.",
            "example_en": "He writes an email to his teacher.",
            "example_tr": "Öğretmenine bir e-posta yazıyor.",
            "tip_en": "Takes dative for person: 'jemandem schreiben'.",
            "tip_tr": "Kişi belirtirken ismin -e halini (Dativ) alır."
        },
        "spielen": {
            "example": "Wir spielen am Wochenende gern Fußball.",
            "example_en": "We like playing soccer on the weekend.",
            "example_tr": "Hafta sonu severek futbol oynarız.",
            "tip_en": "Instrument requires 'auf' or direct: 'Klavier spielen'.",
            "tip_tr": "Müzik aletleriyle doğrudan kullanılır: 'Klavier spielen' (piyano çalmak)."
        },
        "schwimmen": {
            "example": "Im Sommer schwimme ich oft im See.",
            "example_en": "In summer I often swim in the lake.",
            "example_tr": "Yazın sık sık gölde yüzerim.",
            "tip_en": "Forms perfect with 'sein': 'Ich bin geschwommen'.",
            "tip_tr": "Geçmiş zamanda 'sein' yardımcı fiiliyle çekimlenir."
        },
        "reisen": {
            "example": "Ich möchte durch ganz Europa reisen.",
            "example_en": "I would like to travel through all of Europe.",
            "example_tr": "Bütün Avrupa'yı gezmek istiyorum.",
            "tip_en": "Forms perfect with 'sein': 'Ich bin gereist'.",
            "tip_tr": "Hareket bildirdiği için 'sein' ile kullanılır."
        }
    },
    "French": {
        "lire": {
            "example": "Je lis un roman passionnant avant de dormir.",
            "example_en": "I read an exciting novel before sleeping.",
            "example_tr": "Uyumadan önce heyecanlı bir roman okurum.",
            "tip_en": "Irregular 3rd group verb: je lis, nous lisons.",
            "tip_tr": "3. grup kuralsız fiildir: je lis, nous lisons."
        },
        "écrire": {
            "example": "Elle écrit une lettre à sa grand-mère.",
            "example_en": "She writes a letter to her grandmother.",
            "example_tr": "Büyükannesine bir mektup yazıyor.",
            "tip_en": "Past participle: 'écrit'.",
            "tip_tr": "Geçmiş zaman hali: 'écrit'."
        },
        "jouer": {
            "example": "Nous jouons au football le samedi matin.",
            "example_en": "We play soccer on Saturday mornings.",
            "example_tr": "Cumartesi sabahları futbol oynarız.",
            "tip_en": "Sports take 'à': 'jouer au foot'. Instruments take 'de': 'jouer du piano'.",
            "tip_tr": "Sporlarda 'à' (jouer au foot), enstrümanlarda 'de' (jouer du piano) alır."
        },
        "nager": {
            "example": "Je nage dans la piscine municipale.",
            "example_en": "I swim in the municipal pool.",
            "example_tr": "Belediye havuzunda yüzerim.",
            "tip_en": "Spelling change before 'o/a': 'nous nageons'.",
            "tip_tr": "'Nous' çekiminde 'e' harfi korunur: 'nous nageons'."
        },
        "voyager": {
            "example": "J'adore voyager et découvrir de nouvelles cultures.",
            "example_en": "I love traveling and discovering new cultures.",
            "example_tr": "Seyahat etmeyi ve yeni kültürler keşfetmeyi çok severim.",
            "tip_en": "Transport uses 'en': 'voyager en train'.",
            "tip_tr": "Taşıtlarla 'en' edatı kullanılır: 'voyager en train'."
        }
    },
    "Italian": {
        "leggere": {
            "example": "Leggo un bel libro ogni sera.",
            "example_en": "I read a nice book every evening.",
            "example_tr": "Her akşam güzel bir kitap okurum.",
            "tip_en": "Past participle is irregular: 'letto'.",
            "tip_tr": "Geçmiş zaman hali kuralsızdır: 'letto'."
        },
        "scrivere": {
            "example": "Scrive una cartolina dall'Italia.",
            "example_en": "He writes a postcard from Italy.",
            "example_tr": "İtalya'dan bir kartpostal yazıyor.",
            "tip_en": "Past participle: 'scritto'.",
            "tip_tr": "Geçmiş zaman hali: 'scritto'."
        },
        "giocare": {
            "example": "Giochiamo a calcio la domenica.",
            "example_en": "We play soccer on Sundays.",
            "example_tr": "Pazar günleri futbol oynarız.",
            "tip_en": "Always takes preposition 'a': 'giocare a tennis'.",
            "tip_tr": "Spor ve oyunlarda 'a' edatı alır: 'giocare a calcio'."
        },
        "viaggiare": {
            "example": "Mi piace viaggiare in treno attraverso la Toscana.",
            "example_en": "I like traveling by train through Tuscany.",
            "example_tr": "Toskana boyunca trenle seyahat etmeyi severim.",
            "tip_en": "Preposition 'in' for transport: 'in aereo', 'in treno'.",
            "tip_tr": "Ulaşım araçlarında 'in' edatı kullanılır: 'in treno'."
        }
    }
}

def get_vocab_example(language: str, term: str) -> dict:
    """Returns a practical authentic example sentence and collocation tip for a vocabulary term."""
    if not language or not term:
        return {}
    lang_bank = VOCAB_EXAMPLE_BANK.get(language, {})
    term_clean = term.strip().lower()
    # Direct match
    if term_clean in lang_bank:
        return lang_bank[term_clean]
    # Match without accents
    from services.concept_explanations import _normalize
    norm = _normalize(term_clean)
    for k, v in lang_bank.items():
        if _normalize(k) == norm:
            return v
    return {}

def get_letter_phonetics(language: str, letter: str) -> dict:
    """Returns authentic letter name, english phonetics, and turkish phonetics for a letter."""
    if not language or not letter:
        return {}
    alph = ALPHABETS.get(language, {})
    items = alph.get("items", [])
    target = letter.strip().upper()
    for it in items:
        if str(it.get("term", "")).strip().upper() == target or str(it.get("letter", "")).strip().upper() == target:
            return {
                "name": it.get("name") or it.get("translation") or target,
                "phonetic_en": it.get("phonetic_en", ""),
                "phonetic_tr": it.get("phonetic_tr", ""),
                "example": it.get("example", ""),
                "translation": it.get("translation", ""),
                "translation_tr": it.get("translation_tr", "")
            }
    return {}
