#!/usr/bin/env python3
"""Score YouTube hooks with five explainable HEURISTICS (not performance predictions).

Port of the MIT-licensed hook scorer from Jakeschincariol/youtube-agent-skill.
Adds Egyptian-Arabic and code-switched technical-speech cues. No dependencies.

    python3 hookscore.py --hook "ليه الـ Docker container شغال بس الموقع مش بيفتح؟"
    python3 hookscore.py --json hooks.txt
    python3 hookscore.py hooks.txt
"""

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE.parent / 'references' / 'hooks.json').read_text(encoding='utf-8'))
FORMULAS = DATA['hooks']

WORD = re.compile(r"[\w]+(?:[.\-'][\w]+)*", re.UNICODE)
CONCRETE = re.compile(r"(?:\d[\d,.]*\s?(?:%|٪|k|m|x)?|\$\d+|\d+\s*(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|ثانية|دقيقة|دقايق|أيام|يوم|شهر))", re.I)
TECH = re.compile(r"\b(?:Docker|VPS|SSH|DNS|SSL|API|JWT|RBAC|CI/CD|React|Next\.js|Laravel|PostgreSQL|Supabase|Linux|Redis|Kubernetes|GitHub|Nginx|Proxy|Production|Database|Deploy|Container|Server)\b", re.I)
YOU_EN = re.compile(r"\b(?:you|your|you're|youre|yourself)\b", re.I)
YOU_AR = re.compile(r"(?:إنت|انت|أنت|بتاعك|مشروعك|موقعك|عندك|لك|بتعمل|بتستخدم|هتعمل|هتشتري|شاري|بتشتغل|شغلك|سيستمك)")
STAKE_EN = re.compile(r"\b(?:lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
STAKE_AR = re.compile(r"(?:خسر|هيقع|وقع|بوظ|هيبوظ|مشكلة|المشكلة|خطر|غلط|مش شغال|مش بيفتح|بيعلق|بيفشل|فلوس|وقت|بطيء|قبل ما|توقف|ماتعملش|متعملش|اوعى|إوعى|اتعطل)")
CURIOSITY_EN = re.compile(r"\b(?:why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)
CURIOSITY_AR = re.compile(r"(?:ليه|إزاي|ازاي|إيه|ايه|إمتى|امتى|بس|لكن|مع إن|رغم|السبب|طب|ازاي|بدل ما|وليه)")
CLOSED = re.compile(r"\b(?:because|so that|which means)\b|(?:عشان كده|وده معناه إن|الاجابة هي)", re.I)
FILLER_EN = {'basically','actually','literally','just','really','very','so','kind','sort','like','guys','hey','welcome','today','video','subscribe','channel'}
VAGUE_EN = {'amazing','incredible','insane','crazy','huge','massive','secret','powerful','ultimate','best','revolutionary','unbelievable'}
FILLER_AR = {'النهاردة','يا جماعة','يعني','بصوا','بص','فيديو','القناة','بصراحة'}
VAGUE_AR = {'رهيب','جامد','جدا','جدًا','خطير','سحري','سر','أسرار','اسطوري','أسطوري','أفضل'}
FIX_AR = {
    'SPECIFICITY':'استبدل كلمة عامة باسم أداة، مثال، رقم موثّق أو نتيجة حقيقية',
    'ADDRESS':'وضح مين المخاطب والمشكلة اللي بيواجهها',
    'STAKES':'وضح التكلفة الحقيقية أو إيه اللي بيتعطل لو تجاهل المشكلة',
    'CURIOSITY':'سيب سؤال مفتوح بدل ما تجاوبه كله في أول جملة',
    'BREVITY':'اختصر أول جملة واقرأها بصوتك؛ استهدف فكرة واحدة',
}


FIX_EN = {
    'SPECIFICITY': 'replace a vague claim with a concrete tool, example, or verified figure',
    'ADDRESS': 'make it clear which viewer you are addressing',
    'STAKES': 'name the real cost or failure if the problem is ignored',
    'CURIOSITY': 'leave a useful question open instead of answering it immediately',
    'BREVITY': 'keep one clear idea that fits comfortably in a spoken breath',
}


def clamp(n):
    return max(0, min(100, int(round(n))))


def words(text):
    return WORD.findall(text)


def arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))


def specificity(text):
    w = [t.lower() for t in words(text)]
    nums = len(CONCRETE.findall(text))
    tech = len({x.lower() for x in TECH.findall(text)})
    vague = sum(x in VAGUE_EN or x in VAGUE_AR for x in w)
    filler = sum(x in FILLER_EN or x in FILLER_AR for x in w)
    return clamp(34 + min(nums, 3) * 22 + min(tech, 2) * 13 - vague * 16 - filler * 5)


def address(text):
    en, ar = len(YOU_EN.findall(text)), len(YOU_AR.findall(text))
    early = bool(YOU_EN.search(' '.join(words(text)[:6])) or YOU_AR.search(' '.join(words(text)[:6])))
    return clamp(26 + min(en + ar, 3) * 20 + (30 if early else 0))


def stakes(text):
    en, ar = len(STAKE_EN.findall(text)), len(STAKE_AR.findall(text))
    return clamp(22 + min(en + ar, 3) * 26 + (14 if CONCRETE.search(text) else 0))


def curiosity(text):
    en, ar = len(CURIOSITY_EN.findall(text)), len(CURIOSITY_AR.findall(text))
    question = 18 if text.rstrip().endswith(('?', '؟')) else 0
    closed = -18 if CLOSED.search(text) else 0
    return clamp(24 + min(en + ar, 3) * 17 + question + closed)


def brevity(text):
    n = len(words(text))
    if n == 0:
        return 0
    lo, hi = (8, 28) if arabic(text) else (9, 24)
    if lo <= n <= hi:
        return 100
    if n < lo:
        return clamp(max(30, 100 - (lo - n) * 11))
    return clamp(max(10, 100 - (n - hi) * 7))


PROPS = [('SPECIFICITY', specificity), ('ADDRESS', address),
         ('STAKES', stakes), ('CURIOSITY', curiosity), ('BREVITY', brevity)]


def classify(text):
    best, hits = None, 0
    for formula in FORMULAS:
        patterns = list(formula['match']) + list(formula.get('match_ar', []))
        matches = sum(bool(re.search(pattern, text, re.I)) for pattern in patterns)
        if matches > hits:
            best, hits = formula, matches
    return (best['name'] if best else 'Unclassified'), hits


def band(value):
    return 'STRONG' if value >= 72 else 'WORKABLE' if value >= 55 else 'WEAK'


def score(text):
    parts = {name: fn(text) for name, fn in PROPS}
    vals = list(parts.values())
    verdict = round(0.6 * sum(vals) / len(vals) + 0.4 * min(vals))
    formula, hits = classify(text)
    return {'hook': text.strip(), 'language':'Arabic/mixed' if arabic(text) else 'English',
            'properties':parts,'verdict':verdict,'band':band(verdict),
            'formula':formula,'matched':hits,
            'weakest':min(parts, key=parts.get),
            'note':'Heuristic writing aid; not a measured retention or virality prediction.'}


def report(item):
    print('\n ' + item['hook'])
    for label, value in item['properties'].items():
        print(f'   {label:<12} {value:3d}  {"#" * (value//5)}')
    print(f'   {"VERDICT":<12} {item["verdict"]:3d}  {item["band"]}')
    print(f'   formula      {item["formula"]}')
    fixes = FIX_AR if item['language'] == 'Arabic/mixed' else FIX_EN
    print(f'   weakest      {item["weakest"]}: {fixes[item["weakest"]]}')
    print('   note         Heuristic only — check fit, truth and on-screen proof yourself')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', nargs='?', type=Path, help='UTF-8 file containing one hook per line')
    p.add_argument('--hook', help='Score one hook')
    p.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    a = p.parse_args()
    if a.hook is None and a.file is None:
        p.error('provide --hook TEXT or FILE')
    if a.hook is not None and a.file is not None:
        p.error('provide either --hook or a file, not both')
    lines = [a.hook] if a.hook is not None else a.file.read_text(encoding='utf-8').splitlines()
    ranked = sorted((score(line) for line in lines if line.strip()), key=lambda x:-x['verdict'])
    if not ranked:
        p.error('no nonblank hooks provided')
    if a.json:
        print(json.dumps(ranked,ensure_ascii=False,indent=2))
    else:
        for item in ranked:
            report(item)
        if len(ranked)>1:
            print(f'\n Winner: {ranked[0]["hook"]} ({ranked[0]["verdict"]})')


if __name__ == '__main__':
    main()
