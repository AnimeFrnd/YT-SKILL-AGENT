---
name: yt-script
description: >-
  Draft, critique, and improve YouTube scripts and first-15-second hooks, including
  Shorts, with 21 hook structures and an optional Python 3 scoring tool. Use for
  /yt-script, $yt-script, requests for YouTube spoken scripts, five opening-hook
  alternatives, retention beats, on-screen directions, or hook rewrites. Supports
  English and Egyptian Arabic mixed with technical English. Do not invoke for
  publishing or managing YouTube accounts.
---

# yt-script for ChatGPT and Codex

Write a YouTube script that delivers the title's promise. This OpenAI-compatible
adapter is based on the original `skills/yt-script` in
[Jakeschincariol/youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill)
(MIT). It creates scripts only; it does **not** access YouTube, upload, publish,
or claim to predict retention.

## Start with the user's context

1. Identify the topic, viewer, promised takeaway, language, requested format and
   duration from the message and conversation. Do not ask again if supplied.
   If the topic cannot be inferred, ask for that one missing input.
2. For delivery style, prioritize an explicit voice sample/profile the user
   supplied. Otherwise read a `voice.md` file attached to the conversation or
   present in the project if accessible. For Codex, also consider
   `$HOME/.agents/youtube/voice.md` if it exists and is user-controlled. If none
   exists, use the user's language and `references/voice-template.md` as a
   lightweight guide; do not block drafting to request three videos.
3. Never invent numbers, real-world outcomes, screenshots, quotations, or
   sources. Verify version-sensitive technical claims with authoritative
   materials when tools permit, or qualify/omit them.

## Generate and evaluate the hook

1. Read `references/hooks.json`. Write **five genuinely different hooks** using
   different formulas. Every hook should confirm the likely video title in the
   first sentence, create a useful unanswered question, and lead naturally to
   something the script actually shows or explains.
2. **If Python execution is available**, score those five hooks with the
   dependency-free local tool. Resolve paths relative to this `SKILL.md`, not
   the current working directory:

   ```bash
   # Write one proposed hook per UTF-8 line to /tmp/yt-hooks.txt first.
   python3 scripts/hookscore.py --json /tmp/yt-hooks.txt
   # Or score a single hook:
   python3 scripts/hookscore.py --hook 'Why does my Docker app work locally but fail on the VPS?'
   ```

   In Codex, run this in the skill folder, or provide the full absolute path to
   `scripts/hookscore.py`. In ChatGPT, run it only where a code-execution tool
   actually exists. Never invent a numerical score if the tool cannot run:
   show two editorially selected hooks marked **unscored** instead.
3. Compare results to the real promise, factual accuracy and creator's voice.
   Show the best two hooks, the formula for each, and (only if executed) their
   score, strongest and weakest scoring dimensions. Choosing the slightly
   lower-scoring hook for a better audience fit is allowed and often wiser.

## Write the spoken script

- **Opening:** Hook immediately with a relevant situation, misconception,
  question or consequence. Skip introductions and subscribe requests.
- **Body:** One idea per beat. Give an `[ON SCREEN: ...]` direction for each beat
  that visualizes evidence, a diagram, source material or a concrete example.
- **Payoff:** Explicitly answer the hook, don't just tease the answer.
- **Close:** One natural call to action (if useful), not a stack of requests.
- **Shorts:** Keep 45-60 second scripts appropriately short rather than
  importing the full long-form beat timings. Prioritize the first two seconds.
- **Trade-offs:** Where a technical decision matters, briefly explain when the
  solution *does not* apply, rather than presenting it as universal.

Estimate runtime from the spoken text only and an **explicit assumed pace**.
English: use ~150 spoken words/minute as a starting estimate. Egyptian Arabic
or code-switched scripts: use ~120-150 spoken words/minute as an illustration;
words, pauses and delivery differ by speaker. Do not present the estimate as a
recorded or measured duration.

## Hand back

- Best two hook alternatives, formula and rationale; show scores only if the
  scorer was actually executed.
- One complete ready-to-record spoken script split into time-coded beats,
  each with `[ON SCREEN: ...]`.
- Approximate duration and one practical filming/demo note.
- Optionally a brief question about whether to ship or revise.

## Score interpretation

The CLI is an **editing heuristic**, not a retention, click-through or virality
predictor. Its Arabic support is rule-based and uncalibrated against Arabic
retention data. Do not use `STRONG` or `WEAK` as evidence that a video will
perform a certain way. Verify against YouTube Analytics after publication.
