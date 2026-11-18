"""Synthèse audio procédurale : effets sonores, ambiances et musiques (licence CC0).

Tous les sons du jeu sont générés ici par calcul (oscillateurs, bruit filtré,
enveloppes, réverbération par convolution) puis enregistrés en WAV 16 bits.
"""
import wave
import numpy as np

SR = 44100
RNG = np.random.default_rng(1234)


# ----------------------------------------------------------------------------
# Briques de base
# ----------------------------------------------------------------------------
def t_axis(dur):
    return np.arange(int(SR * dur), dtype=np.float64) / SR


def env_adsr(n, a=0.005, d=0.1, s=0.6, r=0.2, sustain_time=None):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    if sustain_time is None:
        s_n = max(0, n - a_n - d_n - r_n)
    else:
        s_n = int(sustain_time * SR)
    e = np.concatenate([np.linspace(0, 1, max(a_n, 1)), np.linspace(1, s, max(d_n, 1)),
                        np.full(s_n, s), np.linspace(s, 0, max(r_n, 1))])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def env_exp(n, decay, attack=0.002):
    t = np.arange(n) / SR
    e = np.exp(-t / max(decay, 1e-4))
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e


def noise(n):
    return RNG.uniform(-1, 1, n)


def brown(n):
    b = np.cumsum(RNG.uniform(-1, 1, n))
    b -= np.convolve(b, np.ones(2001) / 2001, mode="same")
    return b / (np.abs(b).max() + 1e-9)


def fft_filter(x, lo=None, hi=None, slope=1.0):
    """Filtre passe-bande doux dans le domaine fréquentiel."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if hi is not None:
        g *= 1.0 / (1.0 + (f / hi) ** (2 * slope * 2))
    if lo is not None:
        g *= 1.0 / (1.0 + (lo / np.maximum(f, 1e-3)) ** (2 * slope * 2))
    return np.fft.irfft(X * g, n)


def sweep(f0, f1, dur, shape="sine", curve=2.0):
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    f = f1 + (f0 - f1) * (1 - t) ** curve
    ph = np.cumsum(f) / SR * 2 * np.pi
    if shape == "sine":
        return np.sin(ph)
    if shape == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    if shape == "square":
        return np.sign(np.sin(ph))
    return np.sin(ph)


def osc(freq, dur, shape="sine", detune=0.0, phase=0.0):
    t = t_axis(dur)
    ph = 2 * np.pi * freq * (1 + detune) * t + phase
    if shape == "sine":
        return np.sin(ph)
    if shape == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    if shape == "tri":
        return 2 * np.abs(2 * ((ph / (2 * np.pi)) % 1.0) - 1) - 1
    if shape == "square":
        return np.sign(np.sin(ph))
    return np.sin(ph)


def reverb(x, time=1.2, mix=0.25, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * time)
    ir = rng.uniform(-1, 1, n) * np.exp(-np.arange(n) / SR / (time / 5.0))
    ir = fft_filter(ir, hi=6000)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    m = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]
    return x * (1 - mix) + y * mix


def delay(x, time, feedback=0.4, taps=4):
    y = x.copy()
    d = int(time * SR)
    g = feedback
    for k in range(1, taps + 1):
        if d * k >= len(x):
            break
        y[d * k:] += x[:-d * k] * g
        g *= feedback
    return y


def norm(x, peak=0.9):
    m = np.abs(x).max()
    return x / m * peak if m > 1e-9 else x


def stereo(x, width=0.0, seed=0):
    if width <= 0:
        return np.stack([x, x], -1)
    d = int(0.012 * SR * width)
    r = np.concatenate([np.zeros(d), x[:-d]]) if d > 0 else x
    return np.stack([x, r], -1)


def loop_crossfade(x, fade=0.5):
    """Rend un tampon bouclable en fondant la fin dans le début."""
    n = int(fade * SR)
    if x.ndim == 1:
        x = x.copy()
        head = x[:n].copy()
        tail = x[-n:].copy()
        w = np.linspace(0, 1, n)
        x[:n] = head * w + tail * (1 - w)
        return x[:-n]
    return np.stack([loop_crossfade(x[:, c], fade) for c in range(x.shape[1])], -1)


def write_wav(path, x):
    if x.ndim == 1:
        x = stereo(x)
    data = (np.clip(x, -1, 1) * 32000).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# ----------------------------------------------------------------------------
# Effets sonores
# ----------------------------------------------------------------------------
def sfx_ui_hover():
    x = osc(1800, 0.05, "sine") * env_exp(int(0.05 * SR), 0.015)
    return norm(x, 0.35)


def sfx_ui_click():
    n = int(0.12 * SR)
    x = sweep(1400, 700, 0.12) * env_exp(n, 0.03) + fft_filter(noise(n), lo=3000) * env_exp(n, 0.006) * 0.4
    return norm(reverb(x, 0.4, 0.15), 0.55)


def sfx_ui_back():
    n = int(0.14 * SR)
    x = sweep(700, 350, 0.14) * env_exp(n, 0.04)
    return norm(x, 0.45)


def sfx_ui_confirm():
    a = osc(660, 0.35, "tri") * env_exp(int(0.35 * SR), 0.12)
    b = np.concatenate([np.zeros(int(0.07 * SR)), osc(990, 0.28, "tri") * env_exp(int(0.28 * SR), 0.12)])
    x = a + b[: len(a)] * 0.8
    return norm(reverb(x, 0.8, 0.3), 0.6)


def sfx_step(seed):
    rng = np.random.default_rng(seed)
    n = int(0.16 * SR)
    x = noise(n)
    x = fft_filter(x, lo=80, hi=900 + rng.random() * 600) * env_exp(n, 0.025 + rng.random() * 0.01, 0.002)
    thump = osc(70 + rng.random() * 20, 0.16) * env_exp(n, 0.02)
    grit = fft_filter(noise(n), lo=2500, hi=7000) * env_exp(n, 0.01) * 0.25
    return norm(x + thump * 0.6 + grit, 0.5)


def sfx_land():
    n = int(0.3 * SR)
    x = fft_filter(noise(n), lo=40, hi=600) * env_exp(n, 0.06) + osc(55, 0.3) * env_exp(n, 0.08) * 0.8
    return norm(x, 0.7)


def sfx_jump():
    n = int(0.18 * SR)
    x = fft_filter(noise(n), lo=200, hi=1500) * env_exp(n, 0.04)
    return norm(x, 0.35)


def sfx_shot(kind):
    if kind == "pulsar":
        n = int(0.28 * SR)
        x = sweep(2400, 380, 0.28, "saw", curve=3.0) * env_exp(n, 0.05)
        x = fft_filter(x, hi=5000)
        x += fft_filter(noise(n), lo=1500, hi=9000) * env_exp(n, 0.02) * 0.6
        x += osc(90, 0.28) * env_exp(n, 0.04) * 0.9
        return norm(reverb(x, 0.6, 0.18), 0.75)
    if kind == "faucon":
        n = int(0.9 * SR)
        x = sweep(3200, 120, 0.9, "saw", curve=4.0) * env_exp(n, 0.18)
        x = fft_filter(x, hi=4000)
        x += fft_filter(noise(n), lo=100, hi=3000) * env_exp(n, 0.12) * 0.9
        x += osc(55, 0.9) * env_exp(n, 0.15) * 1.2
        return norm(reverb(x, 1.6, 0.35), 0.9)
    # tempete
    n = int(0.6 * SR)
    x = fft_filter(noise(n), lo=60, hi=2500) * env_exp(n, 0.09)
    x += sweep(900, 80, 0.6, "square", curve=3.0) * env_exp(n, 0.07) * 0.5
    x += osc(48, 0.6) * env_exp(n, 0.1) * 1.2
    return norm(reverb(fft_filter(x, hi=6000), 1.0, 0.3), 0.9)


def sfx_overheat():
    n = int(0.8 * SR)
    x = fft_filter(noise(n), lo=2000, hi=9000) * env_adsr(n, 0.01, 0.2, 0.4, 0.4)
    x += sweep(800, 300, 0.8, "square") * env_exp(n, 0.2) * 0.2
    return norm(x, 0.5)


def sfx_ready():
    n = int(0.15 * SR)
    x = osc(1200, 0.15, "sine") * env_exp(n, 0.04) + osc(1800, 0.15) * env_exp(n, 0.03) * 0.5
    return norm(x, 0.35)


def sfx_hitmarker():
    n = int(0.07 * SR)
    x = osc(2600, 0.07, "tri") * env_exp(n, 0.015) + fft_filter(noise(n), lo=4000) * env_exp(n, 0.004) * 0.6
    return norm(x, 0.45)


def sfx_kill():
    a = osc(880, 0.25, "tri") * env_exp(int(0.25 * SR), 0.07)
    b = np.concatenate([np.zeros(int(0.05 * SR)), osc(1320, 0.2, "tri") * env_exp(int(0.2 * SR), 0.07)])
    x = a + b[: len(a)]
    return norm(reverb(x, 0.5, 0.2), 0.5)


def sfx_impact():
    n = int(0.18 * SR)
    x = fft_filter(noise(n), lo=600, hi=6000) * env_exp(n, 0.025) + osc(180, 0.18) * env_exp(n, 0.02) * 0.4
    return norm(x, 0.5)


def sfx_drone_shot():
    n = int(0.35 * SR)
    x = sweep(1200, 200, 0.35, "square", curve=2.0) * env_exp(n, 0.08)
    x = fft_filter(x, hi=3000) + osc(120, 0.35) * env_exp(n, 0.05) * 0.5
    return norm(reverb(x, 0.6, 0.2), 0.6)


def sfx_hurt():
    n = int(0.35 * SR)
    x = fft_filter(noise(n), lo=80, hi=1200) * env_exp(n, 0.08) + sweep(200, 60, 0.35) * env_exp(n, 0.1)
    x += fft_filter(noise(n), lo=3000, hi=8000) * env_exp(n, 0.03) * 0.3
    return norm(x, 0.75)


def sfx_explosion(seed=0):
    rng = np.random.default_rng(seed)
    n = int(2.2 * SR)
    x = fft_filter(noise(n), lo=25, hi=900 + rng.random() * 400) * env_exp(n, 0.35, 0.004)
    x += osc(40 + rng.random() * 10, 2.2) * env_exp(n, 0.25) * 1.5
    crack = fft_filter(noise(n), lo=1500, hi=8000) * env_exp(n, 0.05) * 0.8
    debris = np.zeros(n)
    for _ in range(25):
        k = int(rng.uniform(0.15, 1.4) * SR)
        m = int(0.04 * SR)
        if k + m < n:
            debris[k:k + m] += fft_filter(noise(m), lo=2000, hi=7000) * env_exp(m, 0.008) * rng.uniform(0.05, 0.25)
    x = x + crack + debris
    return norm(reverb(x, 2.0, 0.35), 0.95)


def sfx_pickup():
    notes = [72, 76, 79, 84]
    x = np.zeros(int(0.6 * SR))
    for i, nte in enumerate(notes):
        s = osc(midi(nte), 0.3, "tri") * env_exp(int(0.3 * SR), 0.1)
        k = int(i * 0.06 * SR)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 0.8, 0.3), 0.55)


def sfx_data():
    x = np.zeros(int(0.8 * SR))
    for i, nte in enumerate([67, 74, 79, 86, 91]):
        s = osc(midi(nte), 0.35, "sine") * env_exp(int(0.35 * SR), 0.12)
        s += osc(midi(nte) * 2.01, 0.35) * env_exp(int(0.35 * SR), 0.05) * 0.3
        k = int(i * 0.05 * SR)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 1.0, 0.35), 0.55)


def sfx_beacon_tick():
    n = int(0.12 * SR)
    x = osc(1500, 0.12, "sine") * env_exp(n, 0.03)
    return norm(x, 0.3)


def sfx_capture():
    x = np.zeros(int(1.4 * SR))
    for i, nte in enumerate([60, 64, 67, 72, 76]):
        s = osc(midi(nte), 0.9, "saw") * env_exp(int(0.9 * SR), 0.3)
        s = fft_filter(s, hi=2500)
        k = int(i * 0.08 * SR)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 1.5, 0.4), 0.7)


def sfx_wave_start():
    n = int(2.4 * SR)
    t = t_axis(2.4)
    x = np.zeros(n)
    for f in (55, 82.4, 110, 164.8):
        x += osc(f, 2.4, "saw", detune=0.003) * 0.3
    x = fft_filter(x, hi=900) * env_adsr(n, 0.25, 0.4, 0.7, 1.2)
    x += fft_filter(noise(n), lo=30, hi=200) * env_exp(n, 0.6) * 0.6
    x *= 1 + 0.15 * np.sin(2 * np.pi * 5 * t)
    return norm(reverb(x, 2.5, 0.4), 0.85)


def sfx_wave_clear():
    x = np.zeros(int(2.0 * SR))
    chords = [(57, 60, 64), (59, 62, 67), (60, 64, 69)]
    for i, ch in enumerate(chords):
        k = int(i * 0.22 * SR)
        dur = 1.4 if i == 2 else 0.4
        s = sum(osc(midi(nn), dur, "saw", detune=0.002) for nn in ch)
        s = fft_filter(s, hi=2200) * env_adsr(len(s), 0.01, 0.1, 0.6, dur * 0.5)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 1.8, 0.35), 0.75)


def sfx_victory():
    x = np.zeros(int(4.0 * SR))
    seq = [(0.0, (60, 64, 67)), (0.35, (62, 65, 69)), (0.7, (64, 67, 72)), (1.05, (65, 69, 72, 77))]
    for st, ch in seq:
        dur = 2.8 if st > 1 else 0.45
        s = sum(osc(midi(nn), dur, "saw", detune=0.003) + osc(midi(nn), dur, "saw", detune=-0.003) for nn in ch)
        s = fft_filter(s, hi=3000) * env_adsr(len(s), 0.02, 0.2, 0.7, dur * 0.5)
        k = int(st * SR)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 2.5, 0.4), 0.8)


def sfx_defeat():
    x = np.zeros(int(4.0 * SR))
    seq = [(0.0, (57, 60, 64)), (0.6, (53, 57, 60)), (1.2, (52, 55, 59)), (1.9, (45, 52, 57, 60))]
    for st, ch in seq:
        dur = 2.0 if st > 1.5 else 0.7
        s = sum(osc(midi(nn), dur, "saw", detune=0.004) for nn in ch)
        s = fft_filter(s, hi=1400) * env_adsr(len(s), 0.05, 0.2, 0.6, dur * 0.6)
        k = int(st * SR)
        x[k:k + len(s)] += s[: len(x) - k]
    return norm(reverb(x, 3.0, 0.45), 0.8)


def sfx_heartbeat():
    n = int(0.9 * SR)
    x = np.zeros(n)
    for st in (0.0, 0.22):
        m = int(0.18 * SR)
        k = int(st * SR)
        x[k:k + m] += osc(50, 0.18) * env_exp(m, 0.05) * (1.0 if st == 0 else 0.7)
    return norm(fft_filter(x, hi=300), 0.8)


def sfx_thunder(seed=0):
    rng = np.random.default_rng(seed)
    n = int(5.0 * SR)
    x = fft_filter(noise(n), lo=20, hi=400) * env_adsr(n, 0.05, 0.6, 0.5, 3.5)
    x *= 1 + 0.6 * fft_filter(noise(n), hi=6)
    crack = fft_filter(noise(n), lo=800, hi=5000) * env_exp(n, 0.15) * 0.5
    return norm(reverb(x + crack, 3.0, 0.5), 0.9)


def sfx_whoosh():
    n = int(0.5 * SR)
    t = np.linspace(0, 1, n)
    x = fft_filter(noise(n), lo=300, hi=2500) * np.sin(np.pi * t) ** 2
    return norm(x, 0.4)


# ----------------------------------------------------------------------------
# Boucles d'ambiance
# ----------------------------------------------------------------------------
def loop_drone_hum():
    dur = 4.0
    t = t_axis(dur)
    x = np.zeros_like(t)
    for f, a in ((120, 1.0), (240, 0.5), (360, 0.3), (182, 0.4)):
        x += np.sin(2 * np.pi * f * t + 2 * np.sin(2 * np.pi * 0.5 * t)) * a
    x += fft_filter(noise(len(t)), lo=400, hi=2500) * 0.5
    x *= 1 + 0.2 * np.sin(2 * np.pi * 30 * t)
    return norm(stereo(x), 0.5)


def loop_city():
    dur = 30.0
    n = int(dur * SR)
    t = t_axis(dur)
    rumble = fft_filter(brown(n), lo=20, hi=250) * 0.8
    wind = fft_filter(noise(n), lo=200, hi=1200) * (0.3 + 0.3 * fft_filter(noise(n), hi=0.3) * 5)
    x = rumble + wind * 0.25
    # passages de véhicules lointains
    for _ in range(9):
        c = RNG.uniform(1.5, dur - 1.5)
        w = RNG.uniform(1.5, 3.0)
        g = np.exp(-((t - c) / w) ** 2 * 3)
        x += fft_filter(noise(n), lo=80, hi=700) * g * RNG.uniform(0.3, 0.7)
    # klaxons et sirènes très lointains
    for _ in range(2):
        c = RNG.uniform(3, dur - 5)
        k = int(c * SR)
        m = int(3.0 * SR)
        tt = np.arange(m) / SR
        siren = np.sin(2 * np.pi * (700 + 180 * np.sin(2 * np.pi * 0.6 * tt)) * tt)
        x[k:k + m] += fft_filter(siren, hi=1500) * np.sin(np.pi * tt / 3.0) ** 2 * 0.06
    # oiseaux
    for _ in range(12):
        c = int(RNG.uniform(0.5, dur - 0.5) * SR)
        m = int(0.12 * SR)
        f0 = RNG.uniform(2500, 4500)
        b = sweep(f0, f0 * RNG.uniform(0.7, 1.3), 0.12) * env_adsr(m, 0.01, 0.05, 0.5, 0.05) * 0.05
        x[c:c + m] += b
    left = x
    right = np.roll(x, int(0.3 * SR)) * 0.9 + fft_filter(brown(n), lo=20, hi=200) * 0.2
    st = np.stack([left, right], -1)
    return norm(loop_crossfade(st, 1.0), 0.6)


def loop_rain():
    dur = 12.0
    n = int(dur * SR)
    x = fft_filter(noise(n), lo=400, hi=9000) * 0.6 + fft_filter(brown(n), lo=50, hi=400) * 0.5
    drops = np.zeros(n)
    for _ in range(900):
        k = int(RNG.uniform(0, dur - 0.02) * SR)
        m = int(0.01 * SR)
        drops[k:k + m] += noise(m) * env_exp(m, 0.002) * RNG.uniform(0.1, 0.5)
    x += fft_filter(drops, lo=1500, hi=8000)
    st = np.stack([x, np.roll(x, int(1.3 * SR))], -1)
    return norm(loop_crossfade(st, 1.0), 0.6)


# ----------------------------------------------------------------------------
# Musiques
# ----------------------------------------------------------------------------
def _pad(notes, dur, cutoff=1400, voices=3):
    x = np.zeros(int(dur * SR))
    for nn in notes:
        for v in range(voices):
            det = (v - (voices - 1) / 2) * 0.004
            x += osc(midi(nn), dur, "saw", detune=det, phase=RNG.random() * 6.28)
    x = fft_filter(x, hi=cutoff, slope=1.2)
    return x * env_adsr(len(x), 0.8, 0.5, 0.85, 1.2)


def _pluck(freq, dur, bright=3000):
    n = int(dur * SR)
    x = osc(freq, dur, "saw") * 0.6 + osc(freq, dur, "tri") * 0.4
    x = fft_filter(x, hi=bright)
    return x * env_exp(n, 0.18, 0.003)


def _kick():
    n = int(0.45 * SR)
    return sweep(150, 42, 0.45, curve=4.0) * env_exp(n, 0.16, 0.001) + fft_filter(noise(n), lo=1500) * env_exp(n, 0.004) * 0.3


def _snare():
    n = int(0.3 * SR)
    return fft_filter(noise(n), lo=1200, hi=9000) * env_exp(n, 0.07) * 0.7 + osc(190, 0.3) * env_exp(n, 0.05) * 0.5


def _hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    return fft_filter(noise(n), lo=7000) * env_exp(n, 0.08 if open_ else 0.015) * 0.35


def _place(buf, s, start):
    k = int(start * SR)
    if k >= len(buf):
        return
    m = min(len(s), len(buf) - k)
    buf[k:k + m] += s[:m]


def music_menu():
    bpm = 84
    beat = 60.0 / bpm
    bars = 16
    total = bars * 4 * beat
    n = int(total * SR) + int(3 * SR)
    pad = np.zeros(n)
    arp = np.zeros(n)
    bass = np.zeros(n)
    drums = np.zeros(n)
    prog = [(57, (57, 60, 64, 69)), (53, (53, 57, 60, 65)), (48, (55, 60, 64, 67)), (55, (55, 59, 62, 67))]
    for bar in range(bars):
        root, chord = prog[(bar // 2) % 4]
        st = bar * 4 * beat
        if bar % 2 == 0:
            _place(pad, _pad(chord, 8 * beat + 1.0, cutoff=900 + 300 * (bar / bars)), st)
            _place(bass, osc(midi(root - 24), 8 * beat, "sine") * env_adsr(int(8 * beat * SR), 0.3, 0.5, 0.8, 1.0), st)
        if bar >= 2:
            pattern = [0, 2, 1, 3, 2, 1, 3, 2]
            for i, p in enumerate(pattern):
                f = midi(chord[p] + 12)
                _place(arp, _pluck(f, beat * 1.5, bright=2200 + 800 * np.sin(bar)), st + i * beat / 2)
        if bar >= 4:
            for b in range(4):
                if b in (0, 2):
                    _place(drums, _kick() * 0.7, st + b * beat)
                _place(drums, _hat() * 0.5, st + b * beat + beat / 2)
            if bar % 4 == 3:
                _place(drums, _hat(True), st + 3.5 * beat)
    arp = delay(arp, beat * 0.75, 0.38, 4)
    L = pad * 0.42 + arp * 0.22 + bass * 0.5 + drums * 0.45
    R = np.roll(pad, int(0.015 * SR)) * 0.42 + np.roll(arp, int(beat * 0.375 * SR)) * 0.18 + bass * 0.5 + drums * 0.45
    st = np.stack([reverb(L, 2.2, 0.32, 1), reverb(R, 2.2, 0.32, 2)], -1)
    st = st[: int(total * SR) + int(2 * SR)]
    return norm(loop_crossfade(st, 2.0), 0.8)


def music_game():
    bpm = 118
    beat = 60.0 / bpm
    bars = 16
    total = bars * 4 * beat
    n = int(total * SR) + int(3 * SR)
    pad = np.zeros(n)
    bass = np.zeros(n)
    drums = np.zeros(n)
    lead = np.zeros(n)
    prog = [(50, (50, 53, 57, 62)), (46, (46, 50, 53, 58)), (43, (43, 46, 50, 55)), (45, (45, 49, 52, 57))]
    for bar in range(bars):
        root, chord = prog[bar % 4]
        st = bar * 4 * beat
        _place(pad, _pad(chord, 4 * beat + 0.6, cutoff=700, voices=2), st)
        for e in range(8):
            f = midi(root - 12 + (12 if e % 4 == 3 else 0))
            s = osc(f, beat * 0.5, "saw") * env_exp(int(beat * 0.5 * SR), 0.09)
            _place(bass, fft_filter(s, hi=500 + 300 * (e % 2)), st + e * beat / 2)
        for b in range(4):
            _place(drums, _kick(), st + b * beat)
            if b in (1, 3):
                _place(drums, _snare(), st + b * beat)
            _place(drums, _hat(), st + b * beat + beat / 2)
            _place(drums, _hat() * 0.5, st + b * beat + beat * 0.25)
        if bar >= 8 and bar % 2 == 0:
            for i, p in enumerate([3, 2, 1, 2]):
                _place(lead, _pluck(midi(chord[p] + 12), beat, bright=1800), st + i * beat)
    lead = delay(lead, beat * 0.75, 0.35, 3)
    L = pad * 0.35 + bass * 0.45 + drums * 0.5 + lead * 0.16
    R = np.roll(pad, int(0.02 * SR)) * 0.35 + bass * 0.45 + drums * 0.5 + np.roll(lead, int(0.2 * SR)) * 0.16
    st = np.stack([reverb(L, 1.4, 0.2, 4), reverb(R, 1.4, 0.2, 5)], -1)
    st = st[: int(total * SR) + int(2 * SR)]
    return norm(loop_crossfade(st, 2.0), 0.75)


# ----------------------------------------------------------------------------
CATALOG = {
    "ui_hover": sfx_ui_hover, "ui_click": sfx_ui_click, "ui_back": sfx_ui_back, "ui_confirm": sfx_ui_confirm,
    "step_0": lambda: sfx_step(1), "step_1": lambda: sfx_step(2), "step_2": lambda: sfx_step(3),
    "step_3": lambda: sfx_step(4), "land": sfx_land, "jump": sfx_jump,
    "shot_pulsar": lambda: sfx_shot("pulsar"), "shot_faucon": lambda: sfx_shot("faucon"),
    "shot_tempete": lambda: sfx_shot("tempete"), "overheat": sfx_overheat, "ready": sfx_ready,
    "hitmarker": sfx_hitmarker, "kill": sfx_kill, "impact": sfx_impact, "drone_shot": sfx_drone_shot,
    "hurt": sfx_hurt, "explosion_0": lambda: sfx_explosion(1), "explosion_1": lambda: sfx_explosion(2),
    "pickup": sfx_pickup, "data": sfx_data, "beacon_tick": sfx_beacon_tick, "capture": sfx_capture,
    "wave_start": sfx_wave_start, "wave_clear": sfx_wave_clear, "victory": sfx_victory, "defeat": sfx_defeat,
    "heartbeat": sfx_heartbeat, "thunder_0": lambda: sfx_thunder(1), "thunder_1": lambda: sfx_thunder(2),
    "whoosh": sfx_whoosh,
    "loop_drone": loop_drone_hum, "loop_city": loop_city, "loop_rain": loop_rain,
    "music_menu": music_menu, "music_game": music_game,
}
