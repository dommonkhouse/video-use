# Dom Monkhouse — voice audio reference

Reference spectra for matching Dom's recorded audio. Measured 2026-07-23.

## Which reference to use

**For a YouTube video, match a YouTube talking-head, not an audiobook.** The two
media are mastered differently — the audiobook sits ~5 dB brighter in the 4-8kHz
presence band than YouTube creators do (measured 2026-07-23 against Nate B Jones,
20VC, and Daniel Priestley, which agree with each other to 2.5-3.5 dB and all sit
~5 dB from the audiobook). Matching a YouTube video to the audiobook overshoots
the presence band and reads as crispy/sibilant. Dom's own raw Riverside capture
is often already within ~2.5 dB of a solo YouTube reference; a light touch beats
a heavy chain. Daniel Priestley (solo founder talking-head) is the closest
format match for Dom's weekly video; the 2026-07-22 recording matched him at
2.71 dB with only bass weight + de-boxing + air, no de-essing (his 4-8kHz sits on
top of Dom's already).

**Only match `Mind Your F**king Business` when the target is narration** (an
audiobook, a VSL read, a voiceover). Dom rates this master; he considers the
`F**k Plan B` master poor, and the measurement agrees with him.

```
Mind Your F**king Business  (USE THIS)
  Shared drives/MONKHOUSE & COMPANY/Audiobooks/
    Mind Your F**King Business/Mind Your Fking Business [Full].mp3
  320kbps MP3, 44.1kHz stereo, 4h41m. Sample from ~1800s (clear of intro/credits).

F**k Plan B  (comparison only — do not match to this)
  Shared drives/MONKHOUSE & COMPANY/Audiobooks/F**k Plan B/FK Plan B [Full].mp3
  also: My Drive/pat@... 2026-07-14.../F**K Plan B Audiobook/4 - Part 1.mp3
```

The two masters differ by **5.18 dB mean absolute** across 80Hz–12.5kHz. Plan B is
**boomy and dull simultaneously** — roughly 13dB more energy at 100–125Hz, and
4–10dB darker across 4–10kHz. Matching to it drags a recording toward a thick,
closed-in sound. This was discovered the hard way: a chain matched to Plan B
(the "C" version, 2026-07-23) was rejected by ear before the better reference
was identified.

## The signatures

Third-octave, speech-gated (top 55% of frames by RMS), normalised so the
200Hz–2kHz band averages 0 dB. Comparing *shape*, not level.

| Hz | MYFB (use) | Plan B (avoid) |
|------|------|------|
| 50 | -18.2 | -6.2 |
| 63 | -14.9 | -3.7 |
| 80 | -4.8 | 5.7 |
| 100 | 7.2 | 20.7 |
| 125 | 9.6 | 21.5 |
| 160 | 5.1 | 13.9 |
| 200 | 6.0 | 14.9 |
| 250 | 6.2 | 11.7 |
| 315 | 3.1 | 7.2 |
| 400 | 6.2 | 7.0 |
| 500 | 6.7 | 3.6 |
| 630 | 4.3 | 0.6 |
| 800 | -2.5 | -4.8 |
| 1000 | -1.7 | -7.7 |
| 1250 | -4.1 | -7.5 |
| 1600 | -9.3 | -9.8 |
| 2000 | -15.0 | -15.1 |
| 2500 | -14.4 | -13.0 |
| 3150 | -16.3 | -15.5 |
| 4000 | -11.5 | -15.4 |
| 5000 | -11.7 | -18.9 |
| 6300 | -13.4 | -22.2 |
| 8000 | -13.9 | -23.6 |
| 10000 | -20.9 | -23.6 |
| 12500 | -28.3 | -26.8 |
| 16000 | -32.1 | -34.0 |

## ASR is not a second opinion against Dom's own words

Running the same ASR engine twice is not two independent checks — it's one
opinion repeated, and it can be wrong in the same way both times. When a
transcript disagrees with what Dom says he said about his own speech, his
firsthand word wins; do not "verify" it by re-running the same model and
reporting a match as if it settled the question. (2026-07-23: ElevenLabs Scribe
heard "youthfulness" for "usefulness" — the /s/ fricative lives at 4–8kHz, the
exact band Riverside strips — and running Scribe a second time on the restored
audio still said "youthfulness". That was one engine twice, not proof; Dom's
word was right.)

## What Riverside does to Dom's voice

Riverside's noise suppression removes the top end. Against MYFB, a raw Riverside
capture typically runs **9–14 dB short across 4–10kHz** and **30+ dB short above
12.5kHz**. It is also light below 125Hz, and carries a boxy bump around 315Hz.

Two consequences worth knowing:

- The "lispy" complaint is a **missing top-end** problem, not excess sibilance.
  **De-essing makes it worse.** Above ~12kHz there is nothing left to boost, so
  the fix is harmonic regeneration (`aexciter`), not EQ.
- The severity varies **per recording**. On 2026-07-15 the midrange was badly
  affected; on 2026-07-22 the 300Hz–8kHz band came out near-clean. **Always
  measure — never assume last week's chain still applies.** A chain carried over
  from 2026-07-15 to 2026-07-22 scored *worse than doing nothing* (6.75 dB vs
  5.80 dB deviation) because its 4.5k/6k/8k notches cut a band that was fine.

Raw Riverside audio also tends to peak at **0.0 dBFS** with no headroom. Open any
chain with a level drop and close it with a limiter.

## Worked chain — 2026-07-22 recording, matched to MYFB

Took deviation from 5.80 dB (raw) to **3.13 dB**. Derive per recording rather than
reusing this verbatim; it is a worked example, not a preset.

```
volume=-6dB,
highpass=f=55,
equalizer=f=85:t=q:w=0.7:g=6,
equalizer=f=130:t=q:w=1.2:g=3,
equalizer=f=315:t=q:w=1.4:g=-5.5,
equalizer=f=630:t=q:w=1.3:g=3.5,
equalizer=f=2000:t=q:w=1.4:g=-4,
equalizer=f=5000:t=q:w=0.8:g=9,
equalizer=f=8500:t=q:w=0.9:g=9,
aexciter=level_in=1:level_out=1:amount=3:drive=9:blend=0:freq=10000:ceil=18000,
acompressor=threshold=-20dB:ratio=2.5:attack=10:release=180:makeup=2,
alimiter=limit=0.94
```

## How to measure

`helpers/ltas_match.py` measures a source against a reference and prints the
third-octave table plus the correction needed. `helpers/verify_ltas.py` scores
candidate renders against the reference and reports mean absolute deviation, so
a chain can be checked rather than guessed. Both need numpy + scipy.

Method: decode 600s of each to mono 48kHz, gate to the top 55% of frames by RMS
(keeps speech, drops room tone), Welch PSD, average into third-octave bands,
normalise on 200Hz–2kHz.

Watch for the exciter overshooting into 6–8kHz — that reads as crispy, which is
the exact texture Dom objects to. Verify after rendering; add a corrective notch
around 7kHz if needed.
