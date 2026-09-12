from pathlib import Path

root = Path(__file__).resolve().parents[1]
app_path = root / "public" / "js" / "app.js"
app = app_path.read_text(encoding="utf-8")

anchor = '''function resolveStudyOptionLabel(p, canonicalOption) {
  const canonical = Array.isArray(p.options) ? p.options : [];
  const idx = canonical.indexOf(canonicalOption);
  if (idx < 0) return canonicalOption;
  const localized = currentLang === 'tr' ? p.options_tr : p.options_en;
  if (Array.isArray(localized) && localized.length === canonical.length && localized[idx]) {
    return localized[idx];
  }
  return canonicalOption;
}
'''
helper = anchor + '''
function stableStudyOptionOrder(options, seed) {
  // Stable value-based ordering makes legacy material questions stop presenting the
  // canonical correct answer as option A, without changing the value used for grading.
  const hash = (text) => {
    let h = 2166136261 >>> 0;
    const s = String(text || '');
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h >>> 0;
  };
  return [...options].sort((a, b) => hash(`${seed}|${a}`) - hash(`${seed}|${b}`));
}
'''
if anchor not in app:
    raise RuntimeError("resolveStudyOptionLabel anchor missing")
app = app.replace(anchor, helper, 1)

old = '''               const allOptions = Array.from(new Set(rawOptions)).filter(Boolean);
               if (!Array.isArray(p.options) || p.options.length <= 1) {
                 allOptions.sort();
               }
               const translatedPrompt = resolveStudyPrompt(p, topic);'''
new = '''               let allOptions = Array.from(new Set(rawOptions)).filter(Boolean);
               if (!Array.isArray(p.options) || p.options.length <= 1) {
                 allOptions.sort();
               }
               const optionSeed = `${topic && topic.id ? topic.id : 'topic'}|${p.prompt || p.prompt_en || p.prompt_tr || ''}`;
               allOptions = stableStudyOptionOrder(allOptions, optionSeed);
               const translatedPrompt = resolveStudyPrompt(p, topic);'''
if old not in app:
    raise RuntimeError("material MCQ option-order anchor missing")
app = app.replace(old, new, 1)
app_path.write_text(app, encoding="utf-8")
print("Applied stable frontend option ordering for existing material MCQs")
