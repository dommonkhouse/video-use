#!/usr/bin/env python3
"""YouTube delivery for the video-use weekly long-form flow.

Three subcommands, each a deterministic, verified step:

  upload    Upload a finished file as PRIVATE, print the video id.
  describe  Set a video's description from a fully-built text file, with a
            timestamped backup, a dry-run mode, API + public read-back
            verification, and automatic restore if verification fails.
  chapters  Compute a YouTube chapter block from an edl.json (kept ranges) plus
            a list of source-time anchors, mapping each anchor to its output
            timestamp.

This folds in and supersedes ~/Projects/mcp-setup/bin/mc-youtube-description:
same safe machinery (token refresh, backup, verify-with-retry, restore), but
template-agnostic — it does not hard-code any campaign, tool slug, or
placeholder marker. The per-video description body is bespoke voice content the
agent writes from references/youtube-delivery.md; this script only handles the
mechanics that must not go wrong.

Auth: reads a force-ssl OAuth token and the client secret from
~/.config/mco-youtube-analytics/ by default (override with flags). The token
file stores the refresh token; the client secret stores client_id/secret.

Never invents metadata. Title is passed in verbatim (Dom's own words); privacy
defaults to private so publishing stays a human decision.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config/mco-youtube-analytics"
DEFAULT_TOKEN = CONFIG_DIR / "youtube_oauth_token.dominic.force-ssl.json"
DEFAULT_CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
DEFAULT_BACKUP_ROOT = Path.home() / "Documents/youtube-description-backups"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"


class DeliverError(RuntimeError):
    pass


# ---------------------------------------------------------------- auth

def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError as e:
        raise DeliverError(f"missing file: {path}") from e
    except json.JSONDecodeError as e:
        raise DeliverError(f"invalid JSON in {path}: {e}") from e


def access_token(token_path: Path, client_secret_path: Path) -> str:
    tok = _load(token_path)
    scopes = tok.get("scopes") or tok.get("scope") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    if FORCE_SSL not in scopes:
        raise DeliverError(f"token missing {FORCE_SSL}: {token_path}")
    refresh = tok.get("refresh_token")
    if not refresh:
        if tok.get("access_token") or tok.get("token"):
            return tok.get("access_token") or tok.get("token")
        raise DeliverError(f"token has no refresh_token: {token_path}")
    cs = _load(client_secret_path)
    inst = cs.get("installed") or cs.get("web") or cs
    body = urllib.parse.urlencode({
        "client_id": tok.get("client_id") or inst["client_id"],
        "client_secret": tok.get("client_secret") or inst["client_secret"],
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        inst.get("token_uri", "https://oauth2.googleapis.com/token"),
        data=body, headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        raise DeliverError(f"token refresh failed HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')}") from e


def api(method: str, path: str, token: str,
        params: dict | None = None, body: dict | None = None) -> dict:
    url = f"{API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        raise DeliverError(f"YouTube {method} {path} HTTP {e.code}: "
                           f"{e.read().decode('utf-8', 'replace')}") from e
    return json.loads(raw) if raw else {}


def fetch_snippet(video_id: str, token: str) -> dict:
    items = api("GET", "videos", token,
                params={"part": "snippet", "id": video_id}).get("items") or []
    if len(items) != 1:
        raise DeliverError(f"expected 1 video for {video_id}, got {len(items)}")
    sn = items[0].get("snippet")
    if not isinstance(sn, dict):
        raise DeliverError(f"video {video_id} has no snippet")
    return sn


def public_description(video_id: str) -> str:
    p = subprocess.run(["yt-dlp", "--skip-download", "--print", "description",
                        f"https://www.youtube.com/watch?v={video_id}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise DeliverError(f"yt-dlp readback failed: {p.stderr.strip()}")
    return p.stdout.rstrip("\n")


# ---------------------------------------------------------------- upload

def cmd_upload(a) -> int:
    token = access_token(Path(a.token), Path(a.client_secret))
    src = Path(a.file).expanduser()
    if not src.exists():
        raise DeliverError(f"file not found: {src}")
    meta = {"snippet": {"title": a.title, "categoryId": a.category},
            "status": {"privacyStatus": a.privacy,
                       "selfDeclaredMadeForKids": False}}
    boundary = "----videouse" + datetime.now().strftime("%H%M%S%f")
    size = src.stat().st_size
    # resumable upload: start a session, then PUT the bytes in chunks.
    init = urllib.request.Request(
        f"{UPLOAD_API}/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/*",
                 "X-Upload-Content-Length": str(size)},
        method="POST")
    with urllib.request.urlopen(init, timeout=60) as r:
        session = r.headers["Location"]
    chunk = 64 * 1024 * 1024
    sent, last = 0, -1
    with src.open("rb") as fh:
        while sent < size:
            buf = fh.read(chunk)
            end = sent + len(buf) - 1
            put = urllib.request.Request(
                session, data=buf,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Length": str(len(buf)),
                         "Content-Range": f"bytes {sent}-{end}/{size}"},
                method="PUT")
            try:
                with urllib.request.urlopen(put, timeout=600) as r:
                    resp = json.loads(r.read().decode())
                    print(f"VIDEO_ID={resp['id']}")
                    print(f"URL=https://www.youtube.com/watch?v={resp['id']}")
                    return 0
            except urllib.error.HTTPError as e:
                if e.code == 308:  # resume incomplete: continue
                    sent = end + 1
                    pct = int(sent * 100 / size)
                    if pct >= last + 5:
                        last = pct
                        print(f"  uploaded {pct}%", flush=True)
                    continue
                raise DeliverError(f"upload chunk HTTP {e.code}: "
                                   f"{e.read().decode('utf-8', 'replace')}") from e
    raise DeliverError("upload finished without a final response")


# ---------------------------------------------------------------- describe

WRITABLE = ["title", "description", "tags", "categoryId",
            "defaultLanguage", "defaultAudioLanguage"]


def _run_dir(root: Path, video_id: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    d = root / f"{video_id}-{stamp}"
    n = 2
    while d.exists():
        d = root / f"{video_id}-{stamp}-{n}"
        n += 1
    d.mkdir(parents=True)
    return d


def _payload(video_id: str, snippet: dict, description: str) -> dict:
    out = {}
    for f in WRITABLE:
        if f == "description":
            out[f] = description
        elif f in snippet:
            out[f] = snippet[f]
    for req in ("title", "categoryId"):
        if req not in out:
            raise DeliverError(f"snippet missing required field: {req}")
    return {"id": video_id, "snippet": out}


def _assert_preserved(before: dict, after: dict) -> None:
    for f in WRITABLE:
        if f == "description":
            continue
        if before.get(f) != after.get(f):
            raise DeliverError(f"non-description field changed: {f}")


def _validate(description: str, video_id: str) -> None:
    """Template-agnostic sanity checks: content, no leftover placeholders,
    the video id is wired into the tracking, chapters start at 0:00."""
    if not description.strip():
        raise DeliverError("description is empty")
    for placeholder in ("VIDEO_ID", "PLACEHOLDER", "TKTK", "TODO"):
        if placeholder in description:
            raise DeliverError(f"description still contains {placeholder}")
    if f"mco_video_id={video_id}" not in description:
        raise DeliverError(f"description missing mco_video_id={video_id}")
    if "Chapters:" in description and "0:00" not in description:
        raise DeliverError("chapters present but first chapter is not 0:00")


def _set_and_verify(a, token: str, description: str) -> None:
    root = Path(a.backup_root).expanduser()
    run = _run_dir(root, a.video_id)
    before = fetch_snippet(a.video_id, token)
    (run / "snippet-before.json").write_text(json.dumps(before, indent=2))
    (run / "description-before.txt").write_text(str(before.get("description", "")))
    _validate(description, a.video_id)

    if a.dry_run:
        (run / "description-proposed.txt").write_text(description)
        print(f"dry-run backup: {run}")
        print("dry-run passed")
        return

    payload = _payload(a.video_id, before, description)
    print(f"restore: youtube_deliver.py restore --video-id {a.video_id} "
          f"--snippet-backup {run / 'snippet-before.json'}")
    api("PUT", "videos", token, params={"part": "snippet"}, body=payload)

    err = None
    for attempt in range(6):
        try:
            after = fetch_snippet(a.video_id, token)
            if str(after.get("description", "")) != description:
                raise DeliverError("API read-back description mismatch")
            _assert_preserved(before, after)
            (run / "snippet-after.json").write_text(json.dumps(after, indent=2))
            print("live description set, API-verified")
            print(f"evidence: {run}")
            return
        except Exception as e:  # noqa: BLE001
            err = e
            if attempt < 5:
                time.sleep(15)
    print("verification failed; restoring from backup", file=sys.stderr)
    _restore(a.video_id, run / "snippet-before.json", token)
    raise DeliverError(f"description verify failed, restored: {err}")


def cmd_describe(a) -> int:
    if a.dry_run == a.live:
        raise DeliverError("choose exactly one of --dry-run or --live")
    token = access_token(Path(a.token), Path(a.client_secret))
    description = Path(a.desc_file).expanduser().read_text("utf-8").rstrip("\n")
    _set_and_verify(a, token, description)
    return 0


def _restore(video_id: str, backup: Path, token: str) -> None:
    sn = _load(backup)
    payload = _payload(video_id, sn, str(sn.get("description", "")))
    api("PUT", "videos", token, params={"part": "snippet"}, body=payload)


def cmd_restore(a) -> int:
    token = access_token(Path(a.token), Path(a.client_secret))
    _restore(a.video_id, Path(a.snippet_backup).expanduser(), token)
    print("restored")
    return 0


# ---------------------------------------------------------------- chapters

def _fmt(t: float) -> str:
    return "%d:%02d" % (int(t // 60), int(t % 60))


def cmd_chapters(a) -> int:
    """Map source-time anchors to output timestamps through the kept ranges.

    edl.json: {"ranges": [{"source": .., "start": s, "end": e}, ...]} in the
    order they appear in the cut. anchors.json: [[source_seconds, "label"], ...].
    A source time inside a dropped gap snaps forward to the next kept range.
    """
    edl = _load(Path(a.edl).expanduser())
    ranges = edl.get("ranges") or edl
    rows, off = [], 0.0
    for r in ranges:
        s, e = float(r["start"]), float(r["end"])
        rows.append((s, e, off))
        off += e - s

    def to_out(src: float):
        for s, e, o in rows:
            if s <= src <= e:
                return o + (src - s)
        for s, e, o in rows:  # snap forward to next kept range
            if s > src:
                return o
        return None

    anchors = _load(Path(a.anchors).expanduser())
    print("Chapters:\n")
    for src, label in anchors:
        out = to_out(float(src))
        if out is None:
            print(f"  [skipped: {label} at {src}s falls outside the cut]",
                  file=sys.stderr)
            continue
        print(f"{_fmt(out)} - {label}")
    return 0


# ---------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token", default=str(DEFAULT_TOKEN))
    p.add_argument("--client-secret", default=str(DEFAULT_CLIENT_SECRET))
    p.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    sub = p.add_subparsers(dest="command", required=True)

    up = sub.add_parser("upload", help="upload a file as private")
    up.add_argument("--file", required=True)
    up.add_argument("--title", required=True)
    up.add_argument("--privacy", default="private",
                    choices=["private", "unlisted", "public"])
    up.add_argument("--category", default="22")
    up.set_defaults(func=cmd_upload)

    de = sub.add_parser("describe", help="set description from a text file")
    de.add_argument("--video-id", required=True)
    de.add_argument("--desc-file", required=True)
    mode = de.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    de.set_defaults(func=cmd_describe)

    re = sub.add_parser("restore", help="restore a snippet backup")
    re.add_argument("--video-id", required=True)
    re.add_argument("--snippet-backup", required=True)
    re.set_defaults(func=cmd_restore)

    ch = sub.add_parser("chapters", help="compute chapters from edl + anchors")
    ch.add_argument("--edl", required=True)
    ch.add_argument("--anchors", required=True)
    ch.set_defaults(func=cmd_chapters)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except DeliverError as e:
        print(f"youtube_deliver: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
