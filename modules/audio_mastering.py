"""
Native numpy/scipy re-implementation of Anh Tấn's mastering chain, as a
drop-in replacement for driving a real headless Audacity instance
(modules/audacity_bridge.py). Same 3 effects, same documented parameters,
transcribed from "Edit voice.docx" steps 4-6 -- computed locally instead.

Not bit-identical to Audacity's own DSP engine (different implementation
under the hood), but same recipe, same numbers, no external process/apt
install/window automation required -- runs instantly, every session.

Chain (in this exact order, matching the doc):
  1. Compressor    — Threshold -15dB, Ratio 2:1, Knee 5dB,
                      Attack 15ms, Release 120ms, Lookahead 1ms, Makeup 0dB
  2. Normalize      — peak amplitude to -1.0 dB
  3. Filter Curve EQ — exact curve from EQ.txt (f0..f6 / v0..v6 below)
"""
import numpy as np
from scipy import signal

# Verbatim from EQ.txt
_EQ_FREQS_HZ = [20, 80, 120, 200, 3000, 8000, 20000]
_EQ_GAINS_DB = [0, -6, 1, -2, 1.5, 2, 0]
_EQ_FILTER_LENGTH = 8191


def _compressor(x, sr, threshold_db=-15.0, ratio=2.0, knee_db=5.0,
                 attack_ms=15.0, release_ms=120.0, lookahead_ms=1.0, makeup_db=0.0):
    """Feed-forward soft-knee compressor with a block-rate envelope
    follower (control-rate ~2ms blocks -- standard practice, and the only
    way an attack/release-switching gain smoother is fast in pure Python)."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    eps = 1e-9

    lookahead = max(0, int(round(sr * lookahead_ms / 1000.0)))
    x_delayed = np.concatenate([np.zeros(lookahead), x])[:n] if lookahead else x

    block = max(1, int(round(sr * 0.002)))  # ~2ms control-rate
    n_blocks = int(np.ceil(n / block))
    pad = n_blocks * block - n
    level = np.pad(np.abs(x), (0, pad)).reshape(n_blocks, block).max(axis=1)
    level_db = 20 * np.log10(level + eps)

    half_knee = knee_db / 2.0
    over = level_db - threshold_db
    gain_db = np.where(
        over <= -half_knee, 0.0,
        np.where(
            over >= half_knee,
            over * (1.0 / ratio - 1.0),
            ((over + half_knee) ** 2) * (1.0 / ratio - 1.0) / (2.0 * knee_db),
        ),
    )

    block_rate = max(sr / block, 1.0)
    attack_coef = np.exp(-1.0 / (block_rate * (attack_ms / 1000.0))) if attack_ms > 0 else 0.0
    release_coef = np.exp(-1.0 / (block_rate * (release_ms / 1000.0))) if release_ms > 0 else 0.0

    smoothed = np.empty_like(gain_db)
    prev = 0.0
    for i in range(n_blocks):
        target = gain_db[i]
        coef = attack_coef if target < prev else release_coef  # more negative = attacking
        prev = coef * prev + (1.0 - coef) * target
        smoothed[i] = prev

    gain_db_full = np.repeat(smoothed, block)[:n]
    gain_lin = 10 ** ((gain_db_full + makeup_db) / 20.0)
    return (x_delayed * gain_lin)


def _peak_normalize(x, target_db=-1.0):
    peak = np.max(np.abs(x))
    if peak < 1e-9:
        return x
    return x * (10 ** (target_db / 20.0) / peak)


def _filter_curve_eq(x, sr, freqs_hz=_EQ_FREQS_HZ, gains_db=_EQ_GAINS_DB,
                      numtaps=_EQ_FILTER_LENGTH):
    """FFT-domain FIR EQ from a piecewise frequency/gain curve — the same
    technique Audacity's own Filter Curve effect uses. `firwin2` needs a
    curve starting at 0 Hz and ending exactly at Nyquist, strictly
    increasing; Chatterbox's 24kHz output means the curve's 20kHz point
    (above the 12kHz Nyquist) has to be clipped down first."""
    nyq = sr / 2.0
    freqs = list(map(float, freqs_hz))
    gains = list(map(float, gains_db))
    if freqs[0] > 0:
        freqs = [0.0] + freqs
        gains = [gains[0]] + gains

    clipped_f, clipped_g = [], []
    for f, g in zip(freqs, gains):
        f = min(f, nyq * 0.999999)
        if not clipped_f or f > clipped_f[-1]:
            clipped_f.append(f)
            clipped_g.append(g)
        else:
            clipped_g[-1] = g  # collapsed onto the previous (clipped) point
    if clipped_f[-1] < nyq:
        clipped_f.append(nyq)
        clipped_g.append(clipped_g[-1])

    freqs_norm = np.array(clipped_f) / nyq
    gains_lin = 10 ** (np.array(clipped_g) / 20.0)
    if numtaps % 2 == 0:
        numtaps += 1
    taps = signal.firwin2(numtaps, freqs_norm, gains_lin)
    return signal.fftconvolve(x, taps, mode="same")


def apply_master_chain(wav, sr):
    """Compressor -> Normalize -> Filter Curve EQ, in that order, matching
    'Edit voice.docx' steps 4-6. Takes/returns a 1-D float array."""
    x = np.asarray(wav, dtype=np.float64).flatten()
    x = _compressor(x, sr, threshold_db=-15.0, ratio=2.0, knee_db=5.0,
                     attack_ms=15.0, release_ms=120.0, lookahead_ms=1.0, makeup_db=0.0)
    x = _peak_normalize(x, target_db=-1.0)
    x = _filter_curve_eq(x, sr)
    return x.astype(np.float32)
