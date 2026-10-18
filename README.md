# AnimaTube and the YouTube agent skills

AnimaTube is a cross-platform desktop animation editor built with Python and PySide6. It creates
animated scenes, combines image and audio assets, exports MP4 with FFmpeg, and can upload a
rendered video to YouTube after you explicitly sign in and confirm its metadata.

## AnimaTube desktop app

### Project structure

```text
animatube/
  core/       Project, scene, asset, and keyframe models; JSON persistence
  export/     Qt frame renderer and FFmpeg MP4/audio encoder
  ui/         PySide6 editor, timeline, scene controls, export and upload dialogs
  youtube/    Google OAuth and resumable YouTube Data API uploader
tests/
  test_core.py
requirements.txt
```

### Setup

Install Python 3.10 or later, then install the Python dependencies:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install FFmpeg separately and make sure `ffmpeg` is on `PATH`. AnimaTube uses FFmpeg's H.264
encoder for MP4 output; exporting fails with a clear message if FFmpeg is unavailable. Launch the
desktop app from the repository root:

```bash
python -m animatube
```

### YouTube API credentials

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project and
   enable **YouTube Data API v3**.
2. Configure the OAuth consent screen. While the app is in testing, add the Google account that
   will upload as a test user.
3. Create an OAuth client ID with application type **Desktop app**, then download its JSON file.
4. Store the file outside the repository (the default path is
   `~/.animatube/client_secret.json`) or select it in the upload dialog. Never commit this file or
   the generated `~/.animatube/youtube_token.json` token.
5. In AnimaTube, choose **YouTube upload**, select an MP4, complete the title and privacy fields,
   then sign in in the browser window. Uploading is always an explicit user action.

Google may require OAuth app verification for accounts beyond configured test users. YouTube API
quota and channel restrictions also apply. Scheduled videos must be private until their scheduled
publish time.

### Using the editor

- **Scenes:** use the scene controls to add, duplicate, delete, reorder scenes, set each scene's
  duration, and choose a fade, wipe, slide, or dissolve transition.
- **Canvas and layers:** add text, rectangles, circles, triangles, and a simple built-in character;
  import PNG/JPEG/SVG/GIF image assets, or drag image files onto the canvas. Select and drag layers
  directly, reorder them in the layer list, change the canvas background color, and edit properties
  in the inspector.
- **Animation:** scrub the frame slider, add keyframes for position, scale, rotation, and opacity,
  choose linear/eased interpolation, or apply fade, slide, bounce, zoom, and text typewriter presets.
  Press Play to preview the scene.
- **Audio:** import music or voice-over tracks, set volume, start offset and fades, record from a
  microphone with Qt Multimedia, or generate narration using the local `pyttsx3` speech engine.
- **Projects:** save and open `.anima` JSON projects. Assets are copied into a sibling
  `<project>_assets` directory on save. Changes autosave every two minutes to
  `~/.animatube/autosave.anima`; use Ctrl+Z/Ctrl+Y for in-memory undo and redo.
- **Export:** choose a 16:9 YouTube, 9:16 Shorts, or square output at 720p, 1080p, or 4K and 24,
  30, or 60 fps. AnimaTube renders H.264 MP4 and shows frame/encoding progress.
- **Upload:** upload an exported MP4 with a title, description, tags, category, privacy, optional
  thumbnail, and optional scheduled publish time.

### Current limitations

- GIF files are imported as a still image (their first frame), not as animated image assets. SVG
  import depends on Qt's SVG image plugin being available in the installed PySide6 build.
- The built-in character is a simple vector illustration; there is no rigging, lip-sync, or
  advanced shape editor. The preview and export use the same scene renderer.
- Voice recording depends on a working Qt Multimedia audio backend and microphone. Text-to-speech
  depends on the operating system's local speech engine available to `pyttsx3`.
- YouTube uses the API's resumable upload protocol and retries upload chunks while the app remains
  open. Upload-session URLs are not persisted across restarts; if an upload is interrupted after
  closing the app, start the upload again. OAuth access tokens are refreshed when possible; if
  authorization expires or is revoked, sign in again.
- The frame renderer writes temporary PNG frames before FFmpeg encoding, so long 4K projects need
  substantial temporary disk space. FFmpeg itself is an external prerequisite and is not bundled
  by the PyInstaller command below.

### Tests

Run the dependency-free project/model tests with:

```bash
python -m unittest discover -s tests -v
```

### Package with PyInstaller

Install PyInstaller in the activated environment and build from the repository root:

```bash
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name AnimaTube --collect-all PySide6 --collect-all googleapiclient --collect-all google_auth_oauthlib animatube/__main__.py
```

The output is under `dist/AnimaTube/` (or `dist/AnimaTube.exe` depending on the chosen PyInstaller
mode). Install FFmpeg on the target computer and add it to `PATH`; do not package Google OAuth
client credentials into the executable. Test the package on each target operating system.

## The YouTube agent skills

The rest of this repository provides Claude skills that help plan and produce YouTube channel
content. Those skills remain copy-ready assistants; unlike the explicit desktop uploader above,
they do not publish videos or access YouTube credentials.

Eleven Claude skills that run a YouTube channel. Free, MIT, no signup, no API key, nothing to
connect.

One of them writes your script off 21 hook formulas and scores the hook before you waste a take on
it. One lints the title and the thumbnail as a single pairing, because writing them separately is
why half of your click surface says the same thing twice. One reads your audience-retention export
and tells you the exact second people left and what you were saying when they did. One turns a
transcript into an edit decision list. One finds the Shorts already hiding inside a long video. One
goes and finds what is working in your niche and ranks it by how far each video beat its own
channel, not by how big the channel is.

**Nothing gets published until you do it.** These skills write. You upload.

## Install

Paste this into Claude:

```
https://github.com/Jakeschincariol/youtube-agent-skill

Install this skill, then confirm /yt-script works.
```

Or do it yourself, in Claude Code:

```bash
git clone https://github.com/Jakeschincariol/youtube-agent-skill.git
cp -r youtube-agent-skill/skills/yt-* ~/.claude/skills/
```

Or as a plugin:

```
/plugin marketplace add Jakeschincariol/youtube-agent-skill
/plugin install youtube-agent
```

Project-local instead of global: copy the same folders into your repo's `.claude/skills/`. No Claude
Code at all? Paste any single `SKILL.md` at the top of a chat and it runs as a mode. You lose the six
Python tools, which is most of the point of `/yt-script`, `/yt-retention` and `/yt-edit`, but the
rest works.

Then spend ten minutes on [`templates/voice.md`](templates/voice.md). Copy it to
`~/.claude/youtube/voice.md` and fill it in, or send Claude three of your own videos and say "write
my voice.md from these". Every skill reads that file. It matters more here than anywhere else,
because you have to say the words out loud.

## The eleven

| command | what it does |
| --- | --- |
| `/yt-script` | One idea into a script. Five hooks off [21 formulas](skills/yt-script/hooks.json), scored, then the spoken script with the retention beats marked. |
| `/yt-package` | Title and thumbnail as one pairing, linted for truncation, duplication and vagueness. |
| `/yt-edit` | A transcript into an edit decision list: dead air, filler cues, retakes, with timecodes. |
| `/yt-comment` | The comment section triaged into four piles, then replies in your voice. Says which one to pin. |
| `/yt-plan` | A week that fits the hours you actually have. One anchor, one cheap one, three Shorts. |
| `/yt-viral` | What is working in your niche, ranked by multiple over each channel's own median. |
| `/yt-retention` | Your retention export read properly: hook leak, the cliffs, the slide, and what to change. |
| `/yt-shorts` | The Shorts already inside a long video, with a new first line written for each. |
| `/yt-seo` | The description, the tags that are worth having, and the three queries this should win. |
| `/yt-chapters` | Chapters from a transcript, validated against YouTube's own rules so they render. |
| `/yt-audit` | The whole channel, ending in ONE fix rather than twenty. |

## The six tools

Every one of these runs on a clean Python 3 with no dependencies. They are the reason the skills are
not just prompts.

```bash
python3 skills/yt-script/hookscore.py --hook "one line"        # 5-property hook panel
python3 skills/yt-package/title.py --title "..." --thumb "..." # title + thumbnail linter
python3 skills/yt-edit/deadair.py transcript.srt               # edit decision list
python3 skills/yt-chapters/chapters.py transcript.srt          # validated chapters
python3 skills/yt-retention/retention.py retention.csv         # where they left, and why
python3 skills/yt-viral/swipe.py collected.json --min 2.0      # outliers by own-channel multiple
```

## The fine print

The part most packs leave out.

**The skills do not publish.** Each skill ends in a block you copy and a question — ship it, or
change it? The separate AnimaTube desktop uploader above can upload only after you explicitly
configure Google OAuth and confirm the video details; it does not run your channel unattended.

**`hookscore.py` is a heuristic, not a predictor.** The panel was built and calibrated against 74
real short-form hooks (the first 15 seconds of auto-captions, top-8 and bottom-8 by views across
five channels). It separates deliberately bad hooks from real ones well. It separates a given
creator's hits from their own misses barely at all. A low score is a reason to look again; a high
score is not a promise.

**The formula classifier is about the words, not the result.** When `/yt-viral` says a title used
The Statistic, that is a judgement about the title you can see, not a claim about why the video got
its views.

**`/yt-viral` reads, it does not scrape.** Public listings only. It never logs in as you and never
touches your credentials.

**Tags barely matter** and this pack says so instead of selling you a tag generator.

**Nothing invents a number.** If a skill wants a figure it does not have, it asks you for it or
writes the line without it.

## Licence

MIT. Use it, change it, ship it.
