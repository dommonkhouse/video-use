# YouTube delivery — weekly long-form

The delivery step for Dom Monkhouse's weekly founder-CEO video, once the edit is
approved. Read this whenever the job ends in "upload it" / "publish it" / "put it
on YouTube". The mechanics live in `helpers/youtube_deliver.py`; this file holds
the template, the convention, and the judgement calls the script can't make.

## Order of operations

1. **Upload PRIVATE first.** Never public on first upload. Title, thumbnail, and
   the description's tracking links all need decisions or the video id, which
   doesn't exist until the file is up. Publishing is Dom's call, made after he
   sees it live.
   `youtube_deliver.py upload --file FINAL-4K.mp4 --title "<Dom's words>"`
2. **Build the description** from the template below, filling the real video id
   into every `mco_video_id` / `utm_content` slot.
3. **Set it** with a dry-run, then live:
   `youtube_deliver.py describe --video-id ID --desc-file desc.txt --dry-run`
   then `--live`. The script backs up, sets, verifies via API + public
   read-back, and auto-restores if verification fails.
4. **Surface the human-only steps** (title choice, thumbnail, end screen,
   publish) to Dom. Do not claim them done.

## Title — never invent it

The title is Dom's own wording, from the Speakflow script he read or from his
message. Do not generate a title. If the script/doc offers several pairings and
he hasn't chosen, use the one that matches the script he actually read and say
which, so he can override. Failure mode (2026-07-15): an invented title —
"Why Your Strategy Isn't Working: The Strategic Attention Audit" — when the real
title was just "Why your strategy isn't working".

## Description template

Match this structure exactly — it is the live convention (see the decision-rights
video `QfEaNx8dCoQ` for a shipped example):

```
<One-sentence hook, Dom's voice, no link.>

Get the <free tool name> (free): <TOOL_URL>?utm_source=youtube&utm_medium=video&utm_campaign=<CAMPAIGN>&mco_video_id=<VIDEO_ID>&utm_content=<VIDEO_ID>-desc

Get a copy of Mind Your F**king Business: https://mindyourfkingbusiness.com/?utm_source=youtube&utm_medium=video&utm_campaign=dominicmonkhouse&mco_video_id=<VIDEO_ID>&utm_content=<VIDEO_ID>-desc

Watch this next: <title of the video this one points to>
https://youtu.be/<NEXT_VIDEO_ID>

Chapters:

0:00 - <first chapter>
<computed chapter lines>

<Body: several short paragraphs in Dom's voice describing what's in the video,
then a "What you'll learn:" list. First person. No fabricated stats.>
```

Order is fixed: hook, free tool, book, watch-next, chapters, body. The free tool
and the book are the two standing links; the free tool changes per video (this
week's topic), the book is always second.

## UTM / attribution convention

Established by MON-285 (RevTrack removal, 2026-06-10): CMM / GoHighLevel is the
single source of YouTube→lead attribution via standard UTM tags. Every tracked
link carries:

- `utm_source=youtube`
- `utm_medium=video`
- `utm_campaign=<campaign>` — **per-topic**, so videos roll up separately. The
  free-tool link uses a topic campaign like `founder-four-jobs`; the book link
  uses the standing `dominicmonkhouse` campaign.
- `mco_video_id=<VIDEO_ID>` — video-level attribution, the real YouTube id.
- `utm_content=<VIDEO_ID>-desc` for description links.

In-video assets (a QR panel) use the **same** campaign but a distinct
`utm_content` — e.g. `four-jobs-qr` — so scans separate from description clicks
in reporting. The QR is baked into the render, so it cannot carry the video id
(which doesn't exist yet); it carries a stable slug instead. The description
links, added after upload, carry the id.

## Chapters

Compute them from the cut, never guess:
`youtube_deliver.py chapters --edl edl.json --anchors anchors.json`

`anchors.json` is `[[source_seconds, "label"], ...]` at each narrative section
start (from the script's section headings). The script maps each source time
through the kept ranges to its output timestamp. YouTube's rules: the first
chapter must be `0:00`, at least three chapters, each at least 10s long. Labels
are plain and scannable — a viewer decides whether to jump.

## The end screen — API cannot do it

The YouTube Data API does **not** expose end screens (or cards). They are a
YouTube Studio-only feature: you can neither read nor set them via the API. So a
request to "add the [next] video at the end" cannot be done or verified by this
script. Handle it by:

- Confirming the target video exists and getting its id (search the channel).
- Adding it as the "Watch this next" text link (a fallback that also aids the
  description).
- Telling Dom the end-screen card itself must be placed in Studio, or offering
  to drive his authenticated browser (playwright-cli) to place it. Do not claim
  the end screen is set.

## Weekly checklist

- [ ] Upload the approved 4K as **private**; capture the video id.
- [ ] Title = Dom's exact words (name which pairing if he hasn't chosen).
- [ ] Description built from the template; free tool this week + book second.
- [ ] Every `mco_video_id` / `utm_content` carries the real id; campaign is
      per-topic.
- [ ] Chapters computed from the cut (0:00 first).
- [ ] "Watch this next" points at the intended next video.
- [ ] `describe --dry-run` then `--live`; verify the public read-back.
- [ ] Surface to Dom: title confirmation, thumbnail, end-screen card, publish —
      all human decisions, none of them claimed done.

## Auth

Credentials live in `~/.config/mco-youtube-analytics/`:
- `youtube_oauth_token.dominic.force-ssl.json` — has the `youtube.force-ssl`
  scope (upload + edit) and a refresh token.
- `client_secret.json` — the OAuth client id/secret.

The token file stores the refresh token but not the client id/secret; the helper
combines the two. The channel is "Dominic Monkhouse" (`UCf4lUgrIfPrSK0UZFCNdmPg`).

## Superseded tool

`~/Projects/mcp-setup/bin/mc-youtube-description` was the earlier
description-patcher. It is superseded by `helpers/youtube_deliver.py`: its
validation hard-coded an older template (`founder-freedom-call`,
`founder-power-of-one-tool`, a `VIDEO_ID-desc` placeholder-replace workflow) that
no longer matches the live convention, and it had no upload or chapters support.
Use the helper. The old tool can be retired once Dom confirms nothing external
still calls it.
