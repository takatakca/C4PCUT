"""Local audio onset detection and deterministic beat-cut suggestions."""
import array
import math
import statistics
import subprocess
import sys
import engine

MAX_MUSIC_BYTES = 64 * 1024 * 1024

def normalize(source, target, duration):
    engine.run(["ffmpeg","-nostdin","-v","error","-y","-threads","2","-i",str(source),
                "-map","0:a:0","-vn","-t",str(duration),"-ar","48000","-ac","2",
                "-c:a","pcm_s16le",str(target)], 90)
    if target.stat().st_size <= 100:
        raise ValueError("No usable audio")

def analyze(source, duration):
    rate = 8000
    pcm = subprocess.run(["ffmpeg","-nostdin","-v","error","-threads","2","-i",str(source),
                          "-map","0:a:0","-vn","-t",str(duration),"-ar",str(rate),
                          "-ac","1","-f","s16le","-"], check=True,capture_output=True,timeout=90).stdout
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    hop = rate // 50
    energy = [math.sqrt(sum(v*v for v in samples[i:i+hop])/hop)/32768
              for i in range(0,len(samples),hop)]
    beats = detect_onsets(energy, hop/rate)
    bins = min(600, max(1, math.ceil(duration*5)))
    peaks = []
    for i in range(bins):
        a,b = round(i*duration*rate/bins),round((i+1)*duration*rate/bins)
        peaks.append(round(max((abs(v) for v in samples[a:b]),default=0)/32768,3))
    intervals = [b-a for a,b in zip(beats,beats[1:]) if .25 <= b-a <= 1.5]
    bpm = round(60/statistics.median(intervals)) if len(intervals)>=3 else None
    return {"beats":beats,"peaks":peaks,"estimated_bpm":bpm}

def detect_onsets(energy, step):
    # Positive energy change against a trailing local baseline. A transient
    # detector, not a trained beat tracker; sustained tones are not beats.
    flux = [0.0] + [max(0,b-a) for a,b in zip(energy,energy[1:])]
    candidates = []
    for i in range(1,len(flux)-1):
        window = flux[max(0,i-50):i]
        baseline = statistics.median(window) if window else 0
        threshold = max(.012,baseline*3)
        if flux[i] >= threshold and flux[i] >= flux[i-1] and flux[i] > flux[i+1]:
            t = i*step
            if not candidates or t-candidates[-1][0]>=.24:
                candidates.append((t,flux[i]))
            elif flux[i]>candidates[-1][1]:
                candidates[-1]=(t,flux[i])
    return [round(t,3) for t,_ in candidates]

def beat_cuts(duration, beats, interval=2):
    if type(interval) is not int or interval not in (1,2,4,8):
        raise ValueError("Choose 1, 2, 4 or 8 onsets per cut")
    # Bound the number of segments; spread the cuts across the full source.
    usable = [t for t in beats if .35 <= t <= duration-.35]
    stride = max(interval, math.ceil(len(usable)/(engine.MAX_CLIPS-1)))
    return engine.segments(duration, usable[stride-1::stride])

def validate_gain(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Volume must be between zero and one")
    return value
