#!/usr/bin/env python3
"""retention.py - read a YouTube Studio audience-retention export and find the leaks.

    python3 retention.py retention.csv
    python3 retention.py retention.csv --transcript transcript.srt   # names what was said at each drop
    python3 retention.py retention.csv --json

Get the file from Studio: Analytics -> a video -> Engagement -> the audience-retention chart ->
the download icon -> "Audience retention". Two columns, a position (percent or seconds) and a
percentage still watching.

It reports three things, because they are three different problems with three different fixes:
  HOOK LEAK    what you lost in the first 30 seconds
  CLIFFS       single steep drops - a specific moment people left at
  SLIDE        the steady bleed rate across the flat middle

With --transcript it prints what you were saying at each cliff, which is the only version of this
report you can act on without scrubbing the video yourself.
"""
import csv, json, os, re, sys

def _parse_csv_record(r):
    nums = []
    for c in r:
        c = c.strip().replace("%", "").replace(",", "")
        try: nums.append(float(c))
        except ValueError: nums.append(None)
    vals = [n for n in nums if n is not None]
    if len(vals) < 2: return None
    column = next(i for i, n in enumerate(nums) if n is not None)
    return (vals[0], vals[1]), column, "%" in r[column]

def _heading_unit(label):
    return {
        "seconds": "seconds",
        "percent": "percent",
        "%": "percent",
        "position (seconds)": "seconds",
        "position (percent)": "percent",
        "position (%)": "percent",
        "video position (seconds)": "seconds",
        "video position (percent)": "percent",
        "video position (%)": "percent",
    }.get(label.strip().casefold())

def _read_csv(path):
    rows = []
    heading_seen = False
    heading_unit = None
    aligned = True
    position_percent = False
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.reader(fh):
            if not heading_seen and any(c.strip() for c in r):
                heading_unit = _heading_unit(r[0])
                heading_seen = True
            parsed = _parse_csv_record(r)
            if parsed is None: continue
            pair, column, marked_percent = parsed
            rows.append(pair)
            aligned = aligned and column == 0
            position_percent = position_percent or marked_percent
    if position_percent: return rows, "percent"
    if aligned: return rows, heading_unit
    return rows, None

def load_csv(path):
    rows, _ = _read_csv(path)
    return rows

def _cli_inputs():
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    tr = a[a.index("--transcript") + 1] if "--transcript" in a else None
    files = [x for x in a if not x.startswith("--") and x != tr]
    return a, as_json, tr, files

def _resolve_axis(a, xs, unit):
    pct_axis = max(xs) <= 100.5
    if unit is not None: pct_axis = unit == "percent"
    dur = None
    if "--duration" in a: dur = float(a[a.index("--duration") + 1])
    return pct_axis, dur

def _opening_loss(rows, ys, pct_axis, dur):
    start = ys[0] or 100.0
    # HOOK: the first 30 seconds, or the first 10% when the axis is a percentage and we have no duration
    cutoff = 30.0 if not pct_axis else (30.0 / dur * 100 if dur else 10.0)
    hook_end = min((y for x, y in rows if x <= cutoff), default=start)
    hook_leak = start - hook_end
    return start, cutoff, hook_leak

def _rank_cliffs(rows, xs, ys, pct_axis, dur):
    def at(x): return (x / 100.0 * dur) if (pct_axis and dur) else x
    drops = []
    for i in range(1, len(rows)):
        d = ys[i - 1] - ys[i]
        span = xs[i] - xs[i - 1] or 1
        drops.append((d / span, xs[i - 1], xs[i], d))
    drops.sort(reverse=True)
    cliffs = [{"from": round(a1, 2), "to": round(b1, 2), "lost": round(d, 2),
               "at_seconds": round(at(a1), 1) if (not pct_axis or dur) else None}
              for _, a1, b1, d in drops[:5] if d > 0.8]
    return drops, cliffs

def _calculate_slide(drops, cutoff):
    mid = [d for d, x0, _, _ in [(r[0], r[1], r[2], r[3]) for r in drops] if x0 > cutoff]
    slide = sum(mid) / len(mid) if mid else 0
    return slide

def _transcript_context(tr, cliffs):
    said = {}
    if tr and os.path.exists(tr):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yt-edit"))
        from deadair import load as load_cues
        cues = load_cues(tr)
        for c in cliffs:
            if c["at_seconds"] is None: continue
            t = c["at_seconds"]
            near = [q[2] for q in cues if q[0] <= t + 4 and q[1] >= t - 4]
            said[str(c["from"])] = " ".join(near)[:140]
    return said

def _render_text(files, rows, ys, hook_leak, cliffs, said, slide):
    print(f"\n  {files[0]}   {len(rows)} points   {ys[0]:.1f}% -> {ys[-1]:.1f}%\n")
    verdict = "healthy" if hook_leak < 25 else "leaking" if hook_leak < 40 else "severe"
    print(f"  HOOK LEAK   {hook_leak:.1f}% lost in the opening   [{verdict}]")
    print(f"              under 25 is healthy for this length. Fix the first line before anything else.\n")
    print("  CLIFFS      the moments people actually left")
    for c in cliffs:
        where = f"{c['at_seconds']:.0f}s" if c["at_seconds"] is not None else f"{c['from']}"
        print(f"    -{c['lost']:5.1f}%  at {where:>8}" + (f"   \"{said.get(str(c['from']),'')}\"" if said else ""))
    if not cliffs: print("    none steeper than 0.8% - the loss is all slide, not moments")
    print(f"\n  SLIDE       {slide:.3f}% per unit across the middle")
    print( "              a flat slide is pacing, not content. Cut the middle, do not rewrite it.\n")

def main():
    a, as_json, tr, files = _cli_inputs()
    if not files or not os.path.exists(files[0]): print(__doc__); sys.exit(1)
    rows, unit = _read_csv(files[0])
    if len(rows) < 8: print("could not read at least 8 data points from that csv"); sys.exit(1)
    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
    pct_axis, dur = _resolve_axis(a, xs, unit)
    start, cutoff, hook_leak = _opening_loss(rows, ys, pct_axis, dur)
    drops, cliffs = _rank_cliffs(rows, xs, ys, pct_axis, dur)
    slide = _calculate_slide(drops, cutoff)
    said = _transcript_context(tr, cliffs)
    out = {"points": len(rows), "start": start, "hook_leak": round(hook_leak, 2),
           "end": ys[-1], "cliffs": cliffs, "slide_per_unit": round(slide, 3), "said": said}
    if as_json: print(json.dumps(out, indent=1)); return
    _render_text(files, rows, ys, hook_leak, cliffs, said, slide)

if __name__ == "__main__":
    main()
