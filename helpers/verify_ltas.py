#!/usr/bin/env python3
"""Check whether candidate audio treatments moved a capture toward a reference master.

Companion to `ltas_match.py`: that one derives the corrective EQ, this one
measures how close each rendered attempt actually got. Prints a per-band
deviation table plus a single mean-absolute-deviation figure per candidate, so
the winner is the smallest number.

Prints only — writes no files.

Usage:
    python helpers/verify_ltas.py --ref reference.mp3 --src A-raw.mp4 --src B-cleaned.mp4
    python helpers/verify_ltas.py --ref reference.mp3 --src A.mp4 --src B.mp4 \
        --ref-start 1800 --src-start 100 --duration 600
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000

CENTRES = np.array([50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000,
                    1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000], float)


def load(path, start, dur):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(path),
                          "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def gate(x, frame=4800, keep=0.55):
    n = len(x) // frame
    fr = x[: n * frame].reshape(n, frame)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    return fr[rms >= np.quantile(rms, 1 - keep)].ravel()


def bands(x):
    f, p = signal.welch(x, SR, nperseg=8192, noverlap=4096, scaling="spectrum")
    db = 10 * np.log10(p + 1e-20)
    out = []
    for c in CENTRES:
        m = (f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))
        out.append(db[m].mean() if m.any() else np.nan)
    b = np.array(out)
    norm = (CENTRES >= 200) & (CENTRES <= 2000)
    return b - np.nanmean(b[norm])


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Measure how close each candidate render sits to a reference master."
    )
    ap.add_argument("--src", action="append", required=True, metavar="PATH",
                    help="Candidate render to measure. Repeat for each candidate.")
    ap.add_argument("--ref", required=True,
                    help="Reference master to measure against")
    ap.add_argument("--src-start", type=float, default=100.0,
                    help="Seconds into each candidate to start analysing (default 100)")
    ap.add_argument("--ref-start", type=float, default=1800.0,
                    help="Seconds into --ref to start analysing (default 1800)")
    ap.add_argument("--duration", type=float, default=600.0,
                    help="Seconds of audio to analyse from each file (default 600)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    missing = [p for p in [*args.src, args.ref] if not Path(p).expanduser().exists()]
    if missing:
        sys.exit("file(s) not found:\n  " + "\n  ".join(missing))

    labels = [Path(p).stem[:11] for p in args.src]
    print(f"reference: {Path(args.ref).name}")
    r = bands(gate(load(Path(args.ref).expanduser(), args.ref_start, args.duration)))
    cands = []
    for p, lab in zip(args.src, labels):
        print(f"measuring: {Path(p).name}")
        cands.append(bands(gate(load(Path(p).expanduser(), args.src_start, args.duration))))

    header = "%-8s |" % "Hz" + "".join(" %11s" % f"{lab}-ref" for lab in labels)
    print("\n" + header)
    print("-" * len(header))
    for i, cf in enumerate(CENTRES):
        row = "%-8.0f |" % cf + "".join(" %+11.1f" % (c[i] - r[i]) for c in cands)
        print(row)

    # Mean absolute deviation from the reference, weighted to audible speech range
    aud = (CENTRES >= 80) & (CENTRES <= 12500)
    print("\nMean absolute deviation from reference, 80Hz-12.5kHz (lower is closer):")
    scored = sorted(
        ((float(np.nanmean(np.abs(c - r)[aud])), lab) for c, lab in zip(cands, labels)),
    )
    for score, lab in scored:
        print("  %-12s %5.2f dB" % (lab, score))
    print("\nclosest: %s (%.2f dB)" % (scored[0][1], scored[0][0]))


if __name__ == "__main__":
    main()
