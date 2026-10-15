---
name: yt-retention
description: >-
  Read a YouTube Studio audience-retention export and find where viewers
  actually leave, then say what to change. Use for "why do people stop
  watching", "my retention is bad", a pasted retention chart or CSV, or "fix
  my pacing".
---

# yt-retention

The retention graph is the only honest feedback YouTube gives you. Almost nobody exports it.

```bash
python3 retention.py retention.csv --duration 600
python3 retention.py retention.csv --transcript transcript.srt
```

Getting the file: Studio -> a video -> Analytics -> Engagement -> the audience-retention chart ->
the download icon -> "Audience retention". The first nonempty CSV record can label column zero
`seconds`, `percent`, `%`, `position (seconds)`, `position (percent)`, `position (%)`,
`video position (seconds)`, `video position (percent)` or `video position (%)`; outer spaces and
case are ignored. A label applies only when column zero supplies the first numeric position in
every retained row. A `%` in a successfully parsed retained position cell takes precedence.
Seconds stay seconds with or without `--duration`. For percent axes, a nonzero `--duration`
supplies cliff times in seconds and a 30-second hook window; without it or with zero, the hook
uses the first 10% and cliff times are unavailable. Unlabelled data keeps the
`max(position) <= 100.5` percent heuristic.

## Three different problems

- **HOOK LEAK** - what is lost in the first 30 seconds. Under 25% is healthy. This is always the
  first thing to fix and it is always the first fifteen seconds of script, never the edit.
- **CLIFFS** - single steep drops. A cliff is a moment: a topic change with no signposting, a
  sponsor read, a long setup. With `--transcript` the tool prints what was being said there, which
  is what makes the report actionable instead of interesting.
- **SLIDE** - the steady bleed across the middle. A flat slide is pacing. The fix is cutting, not
  rewriting.

## What to hand back

Name the single biggest leak and one change for it. Not a list of five. Then, only if asked, the
rest. And if the hook leak is healthy and the slide is flat, say the video is fine and the problem
is packaging - send them to `/yt-package`.

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**
