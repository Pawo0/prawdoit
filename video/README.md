# Demo video

A 1:44 video of Prawdowid as it works today (`out/prawdowid-demo.mp4`): the website, the Discord bot and the browser extension.
Everything on screen inside the windows is a recording of the real application answering real requests;
Remotion adds the window frame, camera moves, cursor, captions and title cards.

The visual palette is **Soczysty karmin**: `#C92743`, `#9C1A32`, ivory `#FAF5EC`, and soft pink `#F0DCE0`.
The existing demo and presentation clips were migrated with `tools/recolor-legacy.mjs input.mp4 output.mp4`;
this changes colors in the archived footage without re-running checks or posting Discord messages.
Use an original cobalt recording as input only once. Future recordings use the application's current palette directly.

```bash
cd video && npm install
npm run capture            # records the website and the extension (backend must run on :8000)
npm run render             # → out/prawdowid-demo.mp4 (1920×1080, 60 fps)
npm run studio             # preview and scrub in the browser
```

## How it is made

1. **Capture** (`capture/`, Playwright + Chromium). Each scene drives the real UI and saves two files to
   `public/captures/`: the footage (2560×1440 MP4) and a log on the same clock — cursor path, clicks, and
   named *marks* with the rectangle of the element they refer to (`a-verdict`, `sheet-result`, …).
2. **Compose** (`src/`, Remotion). Scenes are written against those marks: “from `a-result` look at the
   verdict”, “caption X until `reply`”. No pixel coordinates or timestamps are typed in by hand, so a
   re-recording with different timing or layout needs no edits.

Chromium cannot deliver frames of that size in real time, so capture runs in slow motion (our input and the
page's CSS animations five times slower) and is retimed afterwards. **Waiting for the server is the
exception**: those stretches are recorded at true speed. Where the video then skips part of a wait, the cut
is labelled on screen with the seconds skipped.

| File | What it holds |
|---|---|
| `capture/lib.mjs` | recorder: screencast, scene clock, hand-like cursor, typing, marks |
| `capture/run.mjs` | the website and extension scenes; the claims typed are constants at the top |
| `capture/discord.mjs` | the Discord scene (see below) |
| `src/capture.ts` | reads a recording: marks, timeline (cuts), camera, cursor |
| `src/Footage.tsx` | recording inside a window: clips, zoom, cursor, outlines |
| `src/scenes/*.tsx` | one file per scene: cuts, camera shots, captions |
| `src/copy.ts` | every caption and title |
| `src/theme.ts` | colours, fonts and layout taken from `web/static/style.css` |

## Discord scene

It is recorded in the real Discord web client against the deployed bot, so it needs a signed-in browser
profile and **posts one real message** per run.

```bash
node capture/discord-login.mjs      # once: opens a window, you sign in; session kept in ~/.cache/prawdowid-video/
node capture/discord.mjs --dry      # rehearsal: types the command, sends nothing
node capture/discord.mjs            # sends one /sprawdz and records the reply
```

Server, channel, bot name and claim come from `PRAWDOWID_DISCORD_SERVER`, `_CHANNEL`, `_BOT`, `_CLAIM`.
The script refuses to run unless it finds exactly that server and channel. The list of the account's other
servers is hidden before recording; the channel's existing messages and the account's name are visible.
Delete `~/.cache/prawdowid-video/discord-profile` to sign that browser out.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `PRAWDOWID_BASE` | `http://localhost:8000` | application to record |
| `PRAWDOWID_CAPTURE_SLOW` | `5` | slow-motion factor; raise it on a slower machine if motion looks choppy |
| `PRAWDOWID_CAPTURE_GPU` | on | `0` records with software rendering |
| `PRAWDOWID_CAPTURE_DEBUG` | — | directory for a screenshot at every mark |
| `CHROME_PATH` | Playwright's Chromium | browser used for capture |

Recording the website and the extension runs real checks, so it adds a few entries to the local audit log
and analyst queue, like any other use of the application.

Remotion is free for individuals and for organisations of up to three people; larger companies need a
[company licence](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md).
