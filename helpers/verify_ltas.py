#!/usr/bin/env python3
"""Verify the C chain moved the Riverside capture toward the audiobook reference."""
import subprocess, os
import numpy as np
from scipy import signal

SR = 48000
P = os.path.expanduser("~/Movies/four-jobs-proofs")
# Reference master: Mind Your F**king Business. Dom rates this one; Plan B's
# master is bass-inflated and is kept only for comparison.
REF = ("/Users/dominicmonkhouse/Library/CloudStorage/"
       "GoogleDrive-dom@monkhouseandcompany.com/Shared drives/MONKHOUSE & COMPANY/"
       "Audiobooks/Mind Your F**King Business/Mind Your Fking Business [Full].mp3")
REF_START = 1800

REF_PLANB = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-dom@monkhouseandcompany.com/My Drive/"
    "pat@monkhouseandcompany.com 2026-07-14T14:52:46.173Z/F**K Plan B Audiobook/4 - Part 1.mp3"
)
CENTRES = np.array([50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000,
                    1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000], float)


def load(path, start, dur):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", path,
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


a = bands(gate(load(os.path.join(P, "A-audio-AS-DOWNLOADED-720p.mp4"), 100, 600)))
b = bands(gate(load(os.path.join(P, "B-audio-CLEANED-720p.mp4"), 100, 600)))
c = bands(gate(load(os.path.join(P, "C-audio-AUDIOBOOK-MATCHED-720p.mp4"), 100, 600)))
d = bands(gate(load(os.path.join(P, "D-audio-MYFB-MATCHED-720p.mp4"), 100, 600)))
r = bands(gate(load(REF, REF_START, 600)))

print("%-8s | %8s %8s %8s %8s" % ("Hz", "A-ref", "B-ref", "C-ref", "D-ref"))
print("-" * 46)
for i, cf in enumerate(CENTRES):
    print("%-8.0f | %+8.1f %+8.1f %+8.1f %+8.1f"
          % (cf, a[i] - r[i], b[i] - r[i], c[i] - r[i], d[i] - r[i]))

# Mean absolute deviation from the reference, weighted to audible speech range
aud = (CENTRES >= 80) & (CENTRES <= 12500)
print("\nMean absolute deviation from MYFB reference, 80Hz-12.5kHz:")
for name, v in (("A raw       ", a), ("B last week ", b), ("C vs PlanB  ", c), ("D vs MYFB   ", d)):
    print("  %s %5.2f dB" % (name, np.nanmean(np.abs(v - r)[aud])))
