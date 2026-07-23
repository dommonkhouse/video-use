#!/usr/bin/env python3
"""LTAS comparison: this week's raw Riverside audio vs Dom's audiobook narration.

Measures the long-term average spectrum of both (speech-gated, level-normalised)
and derives the corrective EQ that moves the Riverside capture toward the
audiobook's spectral balance.

Outputs a third-octave table, a PNG plot, and an ffmpeg filter chain.
"""
import subprocess, sys, os
import numpy as np
from scipy import signal

SR = 48000
OUT = os.path.dirname(os.path.abspath(__file__))

SRC = os.path.expanduser("~/Movies/four-jobs-proofs/A-audio-AS-DOWNLOADED-720p.mp4")

# Reference: Mind Your F**king Business audiobook. Dom's preferred master —
# he rates the Plan B one as poor, so it is kept only as a comparison.
REF = ("/Users/dominicmonkhouse/Library/CloudStorage/"
       "GoogleDrive-dom@monkhouseandcompany.com/Shared drives/MONKHOUSE & COMPANY/"
       "Audiobooks/Mind Your F**King Business/Mind Your Fking Business [Full].mp3")
REF_START = 1800  # 30 min in, well clear of intro and credits

REF_OLD = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-dom@monkhouseandcompany.com/My Drive/"
    "pat@monkhouseandcompany.com 2026-07-14T14:52:46.173Z/F**K Plan B Audiobook/4 - Part 1.mp3"
)


def load(path, start, dur):
    """Decode a span to mono float32 at SR via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", path,
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


def main():
    print("decoding source (Riverside, 600s of speech)...")
    src = speech_gate(load(SRC, 100, 600))
    print("decoding reference: Mind Your F**king Business (600s)...")
    ref = speech_gate(load(REF, REF_START, 600))
    print("decoding comparison: F**k Plan B (600s)...")
    old = speech_gate(load(REF_OLD, 60, 600))

    norm = (CENTRES >= 200) & (CENTRES <= 2000)

    def prof(x):
        f, d = ltas(x)
        b = bands(f, d)
        return b - np.nanmean(b[norm])

    bs_n, br_n, bo_n = prof(src), prof(ref), prof(old)
    diff = br_n - bs_n  # dB to ADD to source to match the MYFB reference

    print("\n%-9s %10s %8s %8s %9s" % ("Hz", "riverside", "MYFB", "PlanB", "diff→MYFB"))
    print("-" * 50)
    for c, a, b, o, d in zip(CENTRES, bs_n, br_n, bo_n, diff):
        flag = ""
        if abs(d) >= 3:
            flag = "  <<<" if d > 0 else "  >>>"
        print("%-9.0f %10.1f %8.1f %8.1f %+9.1f%s" % (c, a, b, o, d, flag))

    aud = (CENTRES >= 80) & (CENTRES <= 12500)
    print("\nHow different are the two audiobook masters from each other?")
    print("  mean abs difference, 80Hz-12.5kHz: %.2f dB"
          % np.nanmean(np.abs(br_n - bo_n)[aud]))

    np.save(os.path.join(OUT, "ltas_diff.npy"), np.vstack([CENTRES, bs_n, br_n, diff]))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
        ax1.semilogx(CENTRES, bs_n, "o-", label="Riverside (this week, raw)", lw=2)
        ax1.semilogx(CENTRES, br_n, "s-", label="Audiobook narration (reference)", lw=2)
        ax1.set_ylabel("Level (dB, normalised 200Hz-2kHz)")
        ax1.legend(); ax1.grid(True, which="both", alpha=0.3)
        ax1.set_title("Long-term average spectrum: Riverside capture vs audiobook reference")
        ax2.semilogx(CENTRES, diff, "o-", color="crimson", lw=2)
        ax2.axhline(0, color="k", lw=0.8)
        ax2.fill_between(CENTRES, -1.5, 1.5, alpha=0.15, color="green")
        ax2.set_ylabel("Correction needed (dB)"); ax2.set_xlabel("Frequency (Hz)")
        ax2.grid(True, which="both", alpha=0.3)
        for ax in (ax1, ax2):
            ax.set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000, 16000])
            ax.set_xticklabels(["50", "100", "200", "500", "1k", "2k", "5k", "10k", "16k"])
        plt.tight_layout()
        p = os.path.join(OUT, "ltas_comparison.png")
        plt.savefig(p, dpi=110)
        print("\nplot: %s" % p)
    except ImportError:
        print("\n(matplotlib unavailable - table only)")


if __name__ == "__main__":
    main()
