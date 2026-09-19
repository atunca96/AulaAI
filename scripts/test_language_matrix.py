"""Every supported target language, in both instructional tracks, end to end.

Fixtures are necessary but not sufficient: a fixture proves a function behaves,
and most of what has gone wrong in this system went wrong BETWEEN functions - a
boundary called without the track, a renderer preferring the wrong field, a font
whose reverse map lies about what it drew. So this builds a representative lesson
per language in the real schema, persists it to a real database, renders it
through the live renderer, and then audits the RENDERED ARTIFACT rather than the
input it was given.

The language list is read from LANGUAGE_CEFR_STANDARDS rather than written here,
so a language added to the product is covered by this the day it is added.

Each run asserts, on text extracted back out of the PDF: every target-language
term and option present; the track's instruction present; the other track's prose
absent; no NUL, noncharacter or presentation-form residue; and no character in a
transcription that the notation cannot use.
"""

import json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AULAAI_DATA_DIR"] = tempfile.mkdtemp(prefix="aulaai-matrix-")
import database
database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
database.init_db()
import fitz
from services.cefr_reference import LANGUAGE_CEFR_STANDARDS
from services.pdf_renderer_v12 import render_course_pdf
from services.pdf_text_layer import audit_text_layer
from services.authoring.schema import stray_ipa_codepoints as _outside_ipa_repertoire

# Per-language representative material in the real schema. Target-language content
# is genuine; instructional prose is written in the track under test by the driver.
L = {
 "Arabic":     dict(terms=[("مَرْحَبًا","[marħaban]","hello"),("كِتَاب","[kitaːb]","book"),("مَدْرَسَة","[madrasa]","school")],
                    rule="The definite article ال attaches directly to the noun.", ex="لا إله إلا الله",
                    cloze="هذا ____ جديد.", opts=["كتاب","كتب","كاتب","مكتبة"]),
 "Chinese":    dict(terms=[("妈","[ma˥˥]","mother"),("麻","[ma˧˥]","hemp"),("马","[ma˨˩˦]","horse"),("骂","[ma˥˩]","scold")],
                    rule="Tone distinguishes otherwise identical syllables.", ex="这件衣服很贵。",
                    cloze="这件衣服____贵。", opts=["不","没","很","太"]),
 "Dutch":      dict(terms=[("huis","[ɦœys]","house"),("boek","[buk]","book"),("school","[sxoːl]","school")],
                    rule="De and het are the two definite articles.", ex="Het huis is groot.",
                    cloze="____ huis is groot.", opts=["Het","De","Een","Van"]),
 "English":    dict(terms=[("house","[haʊs]","ev"),("book","[bʊk]","kitap"),("school","[skuːl]","okul")],
                    rule="The indefinite article is a before a consonant sound.", ex="This is a book.",
                    cloze="This is ____ book.", opts=["a","an","the","some"]),
 "French":     dict(terms=[("maison","[mɛzɔ̃]","house"),("livre","[livʁ]","book"),("école","[ekɔl]","school")],
                    rule="Nouns agree in gender with their article.", ex="La maison est grande.",
                    cloze="____ maison est grande.", opts=["La","Le","Les","Un"]),
 "German":     dict(terms=[("der Tisch","[deːɐ̯ tɪʃ]","the table"),("Straße","[ˈʃtʁaːsə]","street"),("schön","[ʃøːn]","beautiful")],
                    rule="The accusative marks the direct object.", ex="Ich sehe den Tisch.",
                    cloze="Wir _____ gestern zum Supermarkt gegangen.", opts=["seid","hat","haben","sind"]),
 "Greek":      dict(terms=[("θάλασσα","[ˈθalasa]","sea"),("χώρα","[ˈxora]","country"),("γάλα","[ˈɣala]","milk")],
                    rule="Most multisyllabic words carry a written accent.", ex="Η θάλασσα είναι μεγάλη.",
                    cloze="Η ____ είναι μεγάλη.", opts=["θάλασσα","θάλασσες","θαλάσσης","θαλασσών"]),
 "Italian":    dict(terms=[("casa","[ˈkaza]","house"),("libro","[ˈliːbro]","book"),("scuola","[ˈskwɔːla]","school")],
                    rule="Nouns ending in -o are usually masculine.", ex="Il libro è nuovo.",
                    cloze="____ libro è nuovo.", opts=["Il","La","Lo","Le"]),
 "Japanese":   dict(terms=[("せんせい","[seɴseː]","teacher"),("コーヒー","[koːhiː]","coffee"),("がくせい","[ɡakɯseː]","student")],
                    rule="The mark 「ー」 lengthens the preceding vowel; 「゛」 voices a kana.", ex="コーヒーを のみます。",
                    cloze="見るの て形は ____ です。", opts=["みて","きいて","よんで","かいて"]),
 "Korean":     dict(terms=[("학교","[hak.k͈jo]","school"),("한국어","[han.ɡu.ɡʌ]","Korean"),("옷","[ot̚]","clothes")],
                    rule="Final consonants are unreleased.", ex="이것은 학교예요.",
                    cloze="이 ____ 은 대학교예요.", opts=["건물","건물이","건물을","건물에"]),
 "Portuguese": dict(terms=[("casa","[ˈkazɐ]","house"),("livro","[ˈlivɾu]","book"),("coração","[koɾɐˈsɐ̃w]","heart")],
                    rule="The tilde marks a nasal vowel.", ex="O livro é novo.",
                    cloze="____ livro é novo.", opts=["O","A","Os","Um"]),
 "Russian":    dict(terms=[("здравствуйте","[ˈzdrastvujtʲe]","hello"),("книга","[ˈknʲiɡə]","book"),("стол","[stol]","table")],
                    rule="Nouns change ending by case.", ex="Это книга.",
                    cloze="Я читаю ____.", opts=["книга","книги","книге","книгу"]),
 "Spanish":    dict(terms=[("casa","[ˈkasa]","house"),("libro","[ˈliβɾo]","book"),("español","[espaˈɲol]","Spanish")],
                    rule="Ser expresses inherent qualities.", ex="Pedro es enfermero.",
                    cloze="Ayer nosotros _____ al supermercado.", opts=["fuimos","fue","fui","iban"]),
 "Swedish":    dict(terms=[("hus","[hʉːs]","house"),("bok","[buːk]","book"),("skola","[ˈskuːla]","school")],
                    rule="The definite article is a suffix.", ex="Huset är stort.",
                    cloze="____ är stort.", opts=["Huset","Hus","En hus","Husen"]),
 "Turkish":    dict(terms=[("ev","[ev]","house"),("kitap","[kiˈtap]","book"),("öğretmen","[øːɾetˈmen]","teacher")],
                    rule="Suffixes harmonise with the vowels of the stem.", ex="Bu bir kitap.",
                    cloze="Bu bir ____.", opts=["kitap","kitabı","kitaba","kitapta"]),
}

INSTR = {"tr": dict(overview="Bu derste temel kelimeleri ve yapıyı öğreneceksiniz.",
                    ruleword="Kural", cloze="Cümleyi tamamlayın:", why="Doğru biçim bu bağlamda gereklidir.",
                    title="Temel Kelimeler"),
         "en": dict(overview="In this lesson you will learn core vocabulary and structure.",
                    ruleword="Rule", cloze="Complete the sentence:", why="This form is required in this context.",
                    title="Core Vocabulary")}


def lesson_for(language, track):
    d = L[language]; t = INSTR[track]; other = "en" if track == "tr" else "tr"
    return {"pages": [
        {"type": "overview", "title": t["title"], f"title_{track}": t["title"],
         "text": t["overview"], f"text_{track}": t["overview"]},
        {"type": "vocabulary", "title": t["title"], f"title_{track}": t["title"],
         "items": [{"term": tm, "phonetic": ph, "translation": tr,
                    f"translation_{track}": tr} for tm, ph, tr in d["terms"]]},
        {"type": "rules", "title": t["ruleword"], f"title_{track}": t["ruleword"],
         "rules": [{"rule": d["rule"], f"rule_{track}": d["rule"], "example": d["ex"],
                    f"example_{track}": d["ex"], "scope": "tendency", "domain": "morphology"}]},
        {"type": "mcq", "prompt": d["cloze"], f"prompt_{track}": t["cloze"],
         "options": d["opts"], "answer": d["opts"][0],
         "explanation": t["why"], f"explanation_{track}": t["why"]},
    ]}


LATIN_OK = set("ğĞıİşŞçÇöÖüÜåäöÅÄÖæøÆØéèêëáàâãíìîïóòôõúùûñçÑßẽẼœŒÿŸ")
def audit(language, track, pdf):
    doc = fitz.open("pdf", pdf)
    text = "".join(p.get_text() for p in doc)
    flat = text.replace("\n", "").replace(" ", "")
    a = audit_text_layer(doc)
    problems = []
    if a["nul"]: problems.append(f"NUL x{a['nul']}")
    if a["presentation_forms"]: problems.append(f"presentation-forms x{a['presentation_forms']}")
    for ch in text:
        if ch in "�￾￿": problems.append(f"noncharacter U+{ord(ch):04X}"); break
    d = L[language]
    for tm, _ph, _tr in d["terms"]:
        if tm.replace(" ", "") not in flat: problems.append(f"missing term {tm!r}")
    for opt in d["opts"]:
        if opt.replace(" ", "") not in flat: problems.append(f"missing option {opt!r}")
    # instructional track: the other track's marker prose must not appear
    wrong = INSTR["en" if track == "tr" else "tr"]
    for key in ("overview", "cloze"):
        if wrong[key].replace(" ", "") in flat: problems.append(f"wrong-track prose {wrong[key][:22]!r}")
    if INSTR[track]["cloze"].replace(" ", "") not in flat: problems.append("track instruction missing")
    # phonetic repertoire, read back out of the published artifact
    for m in re.findall(r"\[[^\]\n]{1,40}\]", text):
        bad = _outside_ipa_repertoire(m)
        if bad: problems.append(f"notation residue {m!r} -> {[hex(ord(c)) for c in bad]}"); break
    return doc, text, problems


# Every CEFR band the product sells, not just the entry one. A renderer or
# notation defect that only appears at B2/C1 — longer prose, denser
# transcription, more complex option sets — was previously invisible here
# because the matrix only ever built A1.
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def main():
    langs = sorted(LANGUAGE_CEFR_STANDARDS)
    total = len(langs) * 2 * len(LEVELS)
    print(f"matrix: {len(langs)} languages x 2 tracks x {len(LEVELS)} levels "
          f"= {total} runs\n")
    failures = []
    for language in langs:
      for level in LEVELS:
        row = []
        for track in ("tr", "en"):
            cid = f"c-{language}-{track}-{level}"
            with database.db_connection() as db:
                db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id=?)", (cid,))
                db.execute("DELETE FROM chapters WHERE course_id=?", (cid,))
                db.execute("DELETE FROM courses WHERE id=?", (cid,))
                db.execute("INSERT INTO courses (id,name,language,level,material_language) VALUES (?,?,?,?,?)",
                           (cid, f"{language} {level}", language, level, track))
                db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES (?,?,?,?)",
                           (cid+"-ch", cid, 1, "Unit 1"))
                db.execute("INSERT INTO topics (id,chapter_id,type,title,content,sort_order) VALUES (?,?,?,?,?,?)",
                           (cid+"-t", cid+"-ch", "vocabulary", "Basics",
                            json.dumps(lesson_for(language, track), ensure_ascii=False), 0))
                db.commit()
            try:
                pdf, _ = render_course_pdf(cid, lang=track)
                doc, text, problems = audit(language, track, pdf)
                row.append((track, len(doc), len(pdf), problems))
                if problems: failures.append((language, track, level, problems))
            except Exception as exc:
                row.append((track, 0, 0, [f"RENDER FAILED: {exc}"]))
                failures.append((language, track, level, [f"RENDER FAILED: {exc}"]))
        marks = " | ".join(f"{t}:{'ok' if not p else 'FAIL'}({pg}p,{b//1024}kb)" for t, pg, b, p in row)
        print(f"{language:12} {level}  {marks}")
        for t, _pg, _b, p in row:
            for problem in p: print(f"             {t}: {problem}")
    print(f"\n=== {len(failures)} failing runs of {total} ===")
    if failures:
        return 1
    print(f"language matrix: {len(langs)} languages x 2 tracks x "
          f"{len(LEVELS)} levels, all clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
