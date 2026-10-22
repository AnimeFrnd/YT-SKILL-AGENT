#!/usr/bin/env python3
"""hookscore.py - score a YouTube hook before you waste a take on it.

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one. The
weakest-link weighting is deliberate: a hook with four strong properties and one dead one is a hook
that leaks at the dead one, and averaging hides that.

    python3 hookscore.py hooks.txt            # one hook per line, ranked
    python3 hookscore.py --hook "one line"    # score a single hook
    python3 hookscore.py --json hooks.txt     # machine-readable

RUSSIAN. A Cyrillic hook is scored against hooks.json match_ru and the Russian lexicons, then
reported in Russian. The Russian lexicons are thinner than the English ones, so Russian scores run
low in absolute terms: compare your five hooks against each other, not against the STRONG band.

WHAT THIS CAN AND CANNOT TELL YOU. Measured against 74 real short-form hooks (first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels): it separates deliberately bad
hooks from real ones well, and it separates a creator's own hits from their own misses barely at
all. Treat a low score as a reason to look again, never a high score as a promise.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORMULAS = json.load(open(os.path.join(HERE, "hooks.json")))["hooks"]

FILLER = {"basically","actually","literally","just","really","very","so","kind","sort","like",
          "guys","hey","welcome","today","video","subscribe","channel",
          # RU
          "просто","вообще","короче","типа","вроде","очень","сегодня","видео","ролик","канал",
          "подписывайтесь","друзья","всем","привет"}
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","game","changer","secret",
         "powerful","ultimate","best","revolutionary","mind","blowing","unbelievable",
         # RU - the words that make a hook sound like an advert
         "невероятный","невероятно","крутой","безумный","секретный","секретная","мощный",
         "ультимативный","лучший","лучшая","революционный","магия","волшебный","волшебная",
         "уникальный","эксклюзивный"}
CONCRETE = re.compile(
    r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h|тыс|млн)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?"
    r"|\d+\s?(секунд|минут|час|дн|день|недел|месяц|год|тыс|млн)[а-яё]*)", re.I)
YOU = re.compile(
    r"\b(you|your|you're|youre|yourself|ты|тебя|тебе|тобой|твой|твоя|твои|твоего|"
    r"вы|вас|вам|ваш|ваша|ваши|вашего)\b", re.I)
STAKE = re.compile(
    r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead|"
    r"теряешь|потерять|потратишь|тратишь|впустую|зря|бросить|провал|ошибка|ошибку|"
    r"риск|стоит|перестань|опоздаешь|упустишь|переписываешь|возишься|подолгу|мучаешься|переделываешь)\b", re.I)
CURIOSITY = re.compile(
    r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually|"
    r"почему|как|что|зачем|какой|какая|какие|который|но|никто|почти|кроме|причина|"
    r"на самом деле|потому|всё равно|дело (не )?в|что если|при[её]м)\b", re.I)

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")

def lang(t): return "ru" if CYRILLIC.search(t) else "en"

def words(t): return re.findall(r"[\w'%$.]+", t.lower())

def specificity(t):
    w = words(t)
    if not w: return 0
    nums = len(CONCRETE.findall(t))
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))

def address(t):
    n = len(YOU.findall(t))
    first = 30 if YOU.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))

def stakes(t):
    n = len(STAKE.findall(t))
    return max(0, min(100, 22 + n * 26 + (14 if CONCRETE.search(t) else 0)))

def curiosity(t):
    n = len(CURIOSITY.findall(t))
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if re.search(r"\b(because|so that|which means)\b", t, re.I) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity(t):
    n = len(words(t))
    if n == 0: return 0
    # 9-24 words is the band a spoken hook lands in at ~150wpm inside 10 seconds
    if 9 <= n <= 24: return 100
    if n < 9:  return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)

PROPS = [("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity)]

def classify(t):
    """Match against the English patterns, or the Russian ones when the hook is Cyrillic."""
    key = "match_ru" if lang(t) == "ru" else "match"
    best, hits = None, 0
    for f in FORMULAS:
        pats = f.get(key) or f["match"]
        n = sum(1 for p in pats if re.search(p, t, re.I))
        if n > hits: best, hits = f, n
    return (best["name"] if best else "Unclassified"), hits

def score(t):
    parts = {n: fn(t) for n, fn in PROPS}
    vals = list(parts.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    name, hits = classify(t)
    return parts, verdict, name, hits

def band(v): return "STRONG" if v >= 72 else "WORKABLE" if v >= 55 else "WEAK"

def report(t, parts, verdict, name, hits):
    print(f"\n  {t.strip()}")
    print(f"  {'-' * min(72, max(20, len(t.strip())))}")
    for k, v in parts.items():
        print(f"    {k:<12} {v:3d}  {'#' * (v // 5)}")
    print(f"    {'VERDICT':<12} {verdict:3d}  {band(verdict)}")
    print(f"    formula      {name}" + (f"  ({hits} pattern{'s' if hits != 1 else ''} matched)" if hits else "  (no formula matched - that is usually a summary, not a hook)"))
    low = min(parts, key=parts.get)
    fix = FIX_RU if lang(t) == "ru" else FIX
    print(f"    weakest      {low} - {fix[low]}")

FIX = {
 "SPECIFICITY": "swap one adjective for a number, a name or a date",
 "ADDRESS": "say 'you' in the first six words",
 "STAKES": "name what it costs them to keep doing it the current way",
 "CURIOSITY": "cut the half of the sentence that answers itself",
 "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}

FIX_RU = {
 "SPECIFICITY": "замени одно прилагательное на число, имя или дату",
 "ADDRESS": "скажи «ты» в первых шести словах",
 "STAKES": "назови, чем зрителю стоит продолжать делать по-старому",
 "CURIOSITY": "убери половину фразы, которая сама отвечает на вопрос",
 "BREVITY": "9-24 слова. Прочитай вслух и остановись там, где кончается дыхание",
}

def main():
    a = sys.argv[1:]
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if "--hook" in a:
        lines = [a[a.index("--hook") + 1]]
    elif a and os.path.exists(a[0]):
        lines = [l for l in open(a[0]).read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1 if not a else 0)
    out = []
    for t in lines:
        parts, verdict, name, hits = score(t)
        out.append({"hook": t.strip(), "properties": parts, "verdict": verdict,
                    "band": band(verdict), "formula": name, "matched": hits})
    out.sort(key=lambda r: -r["verdict"])
    if as_json:
        print(json.dumps([{k: v for k, v in r.items() if k != "matched"} for r in out], indent=1, ensure_ascii=False)); return
    for r in out:
        report(r["hook"], r["properties"], r["verdict"], r["formula"], r["matched"])
    if len(out) > 1:
        print(f"\n  winner: {out[0]['hook'].strip()}  ({out[0]['verdict']}, {out[0]['band']})\n")

if __name__ == "__main__":
    main()
