#!/usr/bin/env python3
"""title.py - lint a YouTube title and thumbnail pairing before you publish it.

    python3 title.py --title "..." --thumb "AI RAN IT"
    python3 title.py titles.txt            # one per line, ranked
    python3 title.py --title "..." --json

The pairing is the unit, not the title. A title that repeats the thumbnail text wastes half the
click surface, and that is the single most common mistake this checks for.

Length: YouTube truncates around 60 characters on desktop search and around 40 on a mobile home
feed. Both limits are reported because they are different failures - a desktop truncation loses the
tail, a mobile one can lose the subject.

RUSSIAN. A Cyrillic title is checked with Russian stop words, Russian vague adjectives, and Russian
messages. The character cuts stay at 60/40 because those are the measured feed limits, but Cyrillic
runs wider per character than Latin lowercase, so treat the mobile cut as roughly 35 in practice -
if a title clears 40 it still may lose its subject on a phone.
"""
import json, re, sys, os

DESKTOP, MOBILE, HARD = 60, 40, 100
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","ultimate","best","powerful",
         "secret","revolutionary","mindblowing","epic","perfect","complete","everything",
         # RU
         "невероятный","невероятно","крутой","крутая","безумный","мощный","секретный","секретная",
         "революционный","эпичный","идеальный","полный","лучший","лучшая","всё","уникальный"}
STOP = {"the","a","an","of","for","to","in","on","and","or","is","are","with","your","you","my","i",
        "this","that","it","how","what","why",
        # RU
        "и","в","во","на","с","со","к","ко","о","об","от","до","из","за","по","для","при","про",
        "это","этот","эта","эти","тот","та","то","как","что","чем","когда","почему","зачем",
        "я","ты","мы","вы","мой","моя","мои","твой","твоя","твои","наш","ваш","у","же","ли",
        "не","но","а","или","единственный","только"}

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")

def lang(t): return "ru" if CYRILLIC.search(t) else "en"

def words(t): return re.findall(r"[\w']+", t.lower())

MSG = {
 "en": {
  "hard": "{n} characters - YouTube's hard limit is {hard}",
  "desktop_over": "{n} characters - desktop search cuts near {desktop}",
  "desktop_ok": "{n} characters, inside the {desktop}-character desktop cut",
  "mobile": 'a mobile feed shows about "{head}..." - check the subject survives',
  "shouting": "{c} all-caps words - two is the ceiling before it reads as spam",
  "caps_ok": "{c} all-caps word for emphasis",
  "vague": "{w} - swap for a number, a name or a date",
  "figure_ok": "carries a concrete figure ({nums})",
  "no_number": "no number, date or name - the most reliable single fix",
  "question_ok": "open question in the title",
  "front": "the first three words are all filler - move the subject forward",
  "duplicate": "thumbnail repeats the title on {w} - the thumbnail should say what the title does not",
  "thumb_ok": "thumbnail and title carry different words",
  "thumb_len": "{n} words on the thumbnail - three is the ceiling at feed size",
 },
 "ru": {
  "hard": "{n} символов - жёсткий лимит YouTube {hard}",
  "desktop_over": "{n} символов - обрезка в поиске на десктопе около {desktop}",
  "desktop_ok": "{n} символов, влезает в десктопную обрезку на {desktop}",
  "mobile": 'в мобильной ленте видно примерно "{head}..." - проверь, выживает ли суть',
  "shouting": "{c} слова капсом - два это предел, дальше читается как спам",
  "caps_ok": "{c} слово капсом для акцента",
  "vague": "{w} - замени на число, имя или дату",
  "figure_ok": "есть конкретная цифра ({nums})",
  "no_number": "нет числа, даты или имени - самое надёжное исправление",
  "question_ok": "открытый вопрос в заголовке",
  "front": "первые три слова - вода, вынеси суть вперёд",
  "duplicate": "обложка повторяет заголовок на {w} - обложка должна говорить то, чего нет в заголовке",
  "thumb_ok": "обложка и заголовок из разных слов",
  "thumb_len": "{n} слов на обложке - три это предел на размере ленты",
 },
}

def check(title, thumb=None):
    t = title.strip()
    n = len(t)
    m = MSG[lang(t)]
    issues, good = [], []
    if n > HARD: issues.append(("length", m["hard"].format(n=n, hard=HARD)))
    elif n > DESKTOP: issues.append(("length", m["desktop_over"].format(n=n, desktop=DESKTOP)))
    else: good.append(m["desktop_ok"].format(n=n, desktop=DESKTOP))
    if n > MOBILE:
        head = t[:MOBILE].rsplit(" ", 1)[0]
        issues.append(("mobile", m["mobile"].format(head=head)))
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2: issues.append(("shouting", m["shouting"].format(c=len(caps))))
    elif caps: good.append(m["caps_ok"].format(c=len(caps)))
    v = [w for w in words(t) if w in VAGUE]
    if v: issues.append(("vague", m["vague"].format(w=", ".join(sorted(set(v))))))
    nums = re.findall(r"\d[\d,.]*%?", t)
    if nums: good.append(m["figure_ok"].format(nums=", ".join(nums[:3])))
    else: issues.append(("no-number", m["no_number"]))
    if t.endswith("?"): good.append(m["question_ok"])
    # digits are never in STOP, so a title that opens on "40 секунд" front-loads fine
    front = [w for w in words(t)[:3] if w not in STOP]
    if not front: issues.append(("front-load", m["front"]))
    if thumb:
        tw, hw = set(words(t)) - STOP, set(words(thumb)) - STOP
        shared = tw & hw
        if shared:
            issues.append(("duplicate", m["duplicate"].format(w=", ".join(sorted(shared)))))
        else:
            good.append(m["thumb_ok"])
        if len(words(thumb)) > 4:
            issues.append(("thumb-length", m["thumb_len"].format(n=len(words(thumb)))))
    score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))
    return {"title": t, "chars": n, "score": score, "issues": issues, "good": good}

def show(r):
    print(f'\n  "{r["title"]}"')
    print(f"  {r['chars']} chars   score {r['score']}/100")
    for k, m in r["issues"]: print(f"    x  {k:<12} {m}")
    for m in r["good"]:      print(f"    ok              {m}")

def main():
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    thumb = a[a.index("--thumb") + 1] if "--thumb" in a else None
    if "--title" in a:
        rows = [check(a[a.index("--title") + 1], thumb)]
    elif a and os.path.exists(a[0]):
        rows = [check(l, thumb) for l in open(a[0]).read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1)
    rows.sort(key=lambda r: -r["score"])
    if as_json: print(json.dumps(rows, indent=1)); return
    for r in rows: show(r)
    print()

if __name__ == "__main__":
    main()
