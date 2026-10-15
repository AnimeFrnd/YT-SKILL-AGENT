# ChatGPT and Codex: YouTube script skill

This is a standalone **OpenAI-compatible** version of the repository's
`yt-script` workflow. It lives alongside the original Claude skill rather
than replacing or changing it.

**Current scope:** `yt-script` only. The repository's other 10 Claude
workflows are unchanged and have not been ported by this contribution.

## Install in ChatGPT

ChatGPT skill upload requires access to Skills in an eligible workspace.
In ChatGPT, open **Plugins → Skills → Create → Upload from your computer**.

Upload a ZIP containing the single top-level `yt-script/` folder, including
`SKILL.md`, `agents/openai.yaml`, `scripts/` and `references/`. To create a
portable ZIP with `yt-script/` at the archive root, run this from the repository
root:

```bash
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
base = Path('openai/yt-script')
with ZipFile('/tmp/yt-script-openai.zip', 'w', ZIP_DEFLATED) as z:
    for path in sorted(base.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            z.write(path, Path('yt-script') / path.relative_to(base))
PY
```

Invoke it with a natural request like:

> Use yt-script: explain Docker in a 60-second Egyptian Arabic Short with on-screen beats.

Typing `/yt-script` in ChatGPT can also express intent as **text**, but
installing this skill does not register a native slash command. Python scoring
requires a session with code execution. When unavailable, the instructions
require unscored editorial recommendations rather than fabricated scores.

## Install in Codex

```bash
mkdir -p "$HOME/.agents/skills"
cp -R openai/yt-script "$HOME/.agents/skills/yt-script"
```

Then, in Codex, start a session and ask:

```
$yt-script Write a 60-second Short on why Docker helps with environment drift.
```

Alternatively, for a project-specific skill, copy to
`<your-repo>/.agents/skills/yt-script/`. Codex recognizes `SKILL.md` there.
If newly copied skills do not appear, restart Codex.

## Run the scorer and tests

Python 3 only, no third-party dependencies:

```bash
python3 openai/yt-script/scripts/hookscore.py \
  --hook 'Why does my Docker container work locally but fail on the server?'
python3 openai/yt-script/scripts/hookscore.py \
  --hook 'ليه الـ Docker شغال عندك بس على الـ VPS واقع؟'
python3 -m unittest discover -s openai/yt-script/tests -v
```

The scorer ranks *writing properties*, not likely YouTube views or retention.
Its Arabic heuristics are experimental and have not been calibrated on Arabic
audience data.

## Customize the voice

See `references/voice-template.md` within the skill folder. ChatGPT can use
voice guidance supplied in the conversation or a file accessible to the current
session. Codex can additionally read `$HOME/.agents/youtube/voice.md` if the
user creates it. A missing profile must not block a basic script draft.

## Compatibility and attribution

- Original workflow and hook ideas: [Jake Schincariol](https://github.com/Jakeschincariol/youtube-agent-skill) (MIT).
- This port adds OpenAI-oriented instructions, optional display metadata,
  language-aware scoring, and tests. It does **not** use the YouTube API or
  publish videos.
- OpenAI docs: [Codex skills](https://learn.chatgpt.com/docs/build-skills),
  [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt).
