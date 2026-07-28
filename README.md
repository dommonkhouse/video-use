# video-use — ARCHIVED

**This repository is read-only. Do not edit it. Nothing here is loaded at runtime.**

The `video-use` skill now lives in the canonical skills repo:

- Repo: [`dommonkhouse/skills`](https://github.com/dommonkhouse/skills)
- Path: `~/.codex/skills/video-use/`

Make every change there. Edits made in this repo, or in a stale local clone of
it, will not reach any machine and will not be picked up by any agent.

## Why this repo was retired (2026-07-28, MON-682)

The skills repo tracked only a 42-byte symlink pointing at a clone of this
repository. That arrangement had three problems, none of them visible until
someone asked:

1. **A fresh machine got a dangling symlink, not a working skill.** It worked
   only because all three machines happened to have this repo cloned already.
2. **Nothing watched upstream.** No hook, LaunchAgent or sync monitored
   `browser-use/video-use`. The entire justification for keeping a fork — pulling
   improvements back — rested on a notification that did not exist.
3. **The merge path was never used.** At retirement the fork was zero commits
   behind upstream, with nine commits of our own on top.

The decision is recorded in `claude-config/memory/feedback/skills-canonical-repo.md`.

## What this repo is still for

Provenance, and nothing else. It is the only record of which commits are ours
versus upstream's. Those nine commits, oldest first:

```
88ebd4c 2026-07-09  Add review-first render ladder
760a01d 2026-07-10  Add scripted shorts delivery safeguards
c7a5eb7 2026-07-12  Track video-use dependency lock
cc6ec19 2026-07-23  Load Remotion guidance for video animations
75dcbdb 2026-07-23  Add YouTube delivery + audio-reference + LTAS helpers
95a0a5e 2026-07-23  Capture cut-edge, audio-order, grade and ASR lessons
deb72ca 2026-07-27  Wire in the installed HyperFrames skills; land rules 17-18
503ed32 2026-07-28  Apply unscoped package feedback across all outputs
30e1aab 2026-07-28  Fix silent-failure imports, one-off helpers, output names
```

## Upstream review policy

Forked from [`browser-use/video-use`](https://github.com/browser-use/video-use).
Upstream is reviewed **deliberately and never blind-merged**: read the diff,
decide what is worth having, port it in by hand to the canonical repo. Skill
content someone depends on does not get merged sight-unseen from a third party.
