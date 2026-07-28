#!/usr/bin/env python3
"""Long-term average spectrum comparison between a capture and a reference master.

Measures the LTAS of both (speech-gated, level-normalised) and derives the
corrective EQ that moves the capture toward the reference's spectral balance.
Useful when a recording should be made to sit like an existing, known-good
master — an audiobook, a previous episode, a mix you already trust.

Outputs a third-octave table to stdout, plus `ltas_diff.npy` and
`ltas_comparison.png` in the output directory.

Usage:
    python helpers/ltas_match.py --src capture.mp4 --ref reference.mp3
    python helpers/ltas_match.py --src capture.mp4 --ref reference.mp3 \
        --compare other-master.mp3 --ref-start 1800 --duration 600
    python helpers/ltas_match.py --src capture.mp4 --ref reference.mp3 --out /path/to/edit
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000

# Hard Rule 12: session outputs live in <videos_dir>/edit/, never inside the
# skill directory. This file ships inside a three-machine git repo — writing
# artefacts next to itself would commit render output to that repo.
SKILL_DIR = Path(__file__).resolve().parent.parent


def load(path, start, dur):
    """Decode a span to mono float32 at SR via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(path),
           "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def speech_gate(x, frame=4800, keep=0.55):
    """Keep the most energetic `keep` fraction of frames — biases LTAS to speech,
    not room tone or pauses."""
    n = len(x) // frame
    fr = x[: n * frame].reshape(n, frame)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    thr = np.quantile(rms, 1.0 - keep)
    return fr[rms >= thr].ravel()


def ltas(x):
    """Welch PSD in dB."""
    f, p = signal.welch(x, SR, nperseg=8192, noverlap=4096, scaling="spectrum")
    return f, 10 * np.log10(p + 1e-20)


# third-octave centres, 50Hz .. 16kHz
CENTRES = np.array([50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
                    800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300,
                    8000, 10000, 12500, 16000], dtype=float)


def bands(f, db):
    out = []
    for c in CENTRES:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        m = (f >= lo) & (f < hi)
        out.append(db[m].mean() if m.any() else np.nan)
    return np.array(out)


def resolve_out_dir(args) -> Path:
    """Default the output directory to the source's own `edit/` folder.

    Never the script's directory — that is inside the skill repo (Hard Rule 12).
    """
    out = Path(args.out).expanduser().resolve() if args.out else (
        Path(args.src).expanduser().resolve().parent / "edit"
    )
    if out == SKILL_DIR or SKILL_DIR in out.parents or out in SKILL_DIR.parents:
        sys.exit(
            f"refusing to write to {out}: session outputs must not land inside the "
            f"video-use skill directory ({SKILL_DIR}). Pass --out <videos_dir>/edit."
        )
    out.mkdir(parents=True, exist_ok=True)
    return out


def label_for(path) -> str:
    return Path(path).stem[:9]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Compare the long-term average spectrum of a capture against a reference master."
    )
    ap.add_argument("--src", required=True,
                    help="Capture to correct (any file ffmpeg can decode)")
    ap.add_argument("--ref", required=True,
                    help="Reference master to match toward")
    ap.add_argument("--compare", default=None,
                    help="Optional third file, shown alongside for context only")
    ap.add_argument("--out", default=None,
                    help="Output directory. Default: <src's folder>/edit")
    ap.add_argument("--src-start", type=float, default=100.0,
                    help="Seconds into --src to start analysing (default 100)")
    ap.add_argument("--ref-start", type=float, default=1800.0,
                    help="Seconds into --ref to start analysing (default 1800, "
                         "well clear of intros and credits)")
    ap.add_argument("--compare-start", type=float, default=60.0,
                    help="Seconds into --compare to start analysing (default 60)")
    ap.add_argument("--duration", type=float, default=600.0,
                    help="Seconds of audio to analyse from each file (default 600)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    out_dir = resolve_out_dir(args)

    print(f"decoding source: {Path(args.src).name} ({args.duration:.0f}s)...")
    src = speech_gate(load(args.src, args.src_start, args.duration))
    print(f"decoding reference: {Path(args.ref).name} ({args.duration:.0f}s)...")
    ref = speech_gate(load(args.ref, args.ref_start, args.duration))
    old = None
    if args.compare:
        print(f"decoding comparison: {Path(args.compare).name} ({args.duration:.0f}s)...")
        old = speech_gate(load(args.compare, args.compare_start, args.duration))

    norm = (CENTRES >= 200) & (CENTRES <= 2000)

    def prof(x):
        f, d = ltas(x)
        b = bands(f, d)
        return b - np.nanmean(b[norm])

    bs_n, br_n = prof(src), prof(ref)
    bo_n = prof(old) if old is not None else None
    diff = br_n - bs_n  # dB to ADD to source to match the reference

    src_l, ref_l = label_for(args.src), label_for(args.ref)
    cmp_l = label_for(args.compare) if args.compare else ""

    if bo_n is None:
        print("\n%-9s %10s %10s %9s" % ("Hz", src_l, ref_l, "diff→ref"))
        print("-" * 42)
        for c, a, b, d in zip(CENTRES, bs_n, br_n, diff):
            flag = ("  <<<" if d > 0 else "  >>>") if abs(d) >= 3 else ""
            print("%-9.0f %10.1f %10.1f %+9.1f%s" % (c, a, b, d, flag))
    else:
        print("\n%-9s %10s %10s %10s %9s" % ("Hz", src_l, ref_l, cmp_l, "diff→ref"))
        print("-" * 53)
        for c, a, b, o, d in zip(CENTRES, bs_n, br_n, bo_n, diff):
            flag = ("  <<<" if d > 0 else "  >>>") if abs(d) >= 3 else ""
            print("%-9.0f %10.1f %10.1f %10.1f %+9.1f%s" % (c, a, b, o, d, flag))

    aud = (CENTRES >= 80) & (CENTRES <= 12500)
    if bo_n is not None:
        print("\nHow different are the two references from each other?")
        print("  mean abs difference, 80Hz-12.5kHz: %.2f dB"
              % np.nanmean(np.abs(br_n - bo_n)[aud]))

    npy_path = os.path.join(out_dir, "ltas_diff.npy")
    np.save(npy_path, np.vstack([CENTRES, bs_n, br_n, diff]))
    print("\ndata: %s" % npy_path)

    # matplotlib is a declared dependency. Do NOT swallow ImportError here — a
    # missing plot would look like a successful table-only run when the real
    # problem is a broken environment.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    ax1.semilogx(CENTRES, bs_n, "o-", label=f"{src_l} (capture)", lw=2)
    ax1.semilogx(CENTRES, br_n, "s-", label=f"{ref_l} (reference)", lw=2)
    if bo_n is not None:
        ax1.semilogx(CENTRES, bo_n, "^-", label=f"{cmp_l} (comparison)", lw=1.5, alpha=0.7)
    ax1.set_ylabel("Level (dB, normalised 200Hz-2kHz)")
    ax1.legend()
    ax1.grid(True, which="both", alpha=0.3)
    ax1.set_title("Long-term average spectrum: capture vs reference")
    ax2.semilogx(CENTRES, diff, "o-", color="crimson", lw=2)
    ax2.axhline(0, color="k", lw=0.8)
    ax2.fill_between(CENTRES, -1.5, 1.5, alpha=0.15, color="green")
    ax2.set_ylabel("Correction needed (dB)")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.grid(True, which="both", alpha=0.3)
    for ax in (ax1, ax2):
        ax.set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000, 16000])
        ax.set_xticklabels(["50", "100", "200", "500", "1k", "2k", "5k", "10k", "16k"])
    plt.tight_layout()
    png_path = os.path.join(out_dir, "ltas_comparison.png")
    plt.savefig(png_path, dpi=110)
    print("plot: %s" % png_path)


if __name__ == "__main__":
    main()
