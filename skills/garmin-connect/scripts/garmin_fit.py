#!/usr/bin/env python3
"""Extract training metrics from one Garmin FIT file (needs `fitdecode` and `numpy`).

  garmin_fit.py FILE.fit        # prints the metrics as JSON

Per activity:
- peak power, HR and speed over standard durations (5 s ... 4 h), on a 1 Hz grid; gaps up to
  10 s are held, longer pauses are dropped and the recorded segments joined
- runs: fastest time over standard distances (400 m ... marathon), from the distance channel
- aerobic decoupling (first vs second half of moving time) for steady sessions >= 60 min
- a curated slice of the session message (running dynamics, L/R balance, swim strokes,
  training effect, temperature) and strength sets
No GPS, no device serials.
"""
import json
import sys

import fitdecode
import numpy as np

DURS = [5, 10, 30, 60, 120, 180, 300, 600, 1200, 1800, 3600, 5400, 7200, 10800, 14400]
DISTS = [400, 1000, 1609, 5000, 10000, 15000, 21097, 30000, 42195]
REC = ("timestamp", "heart_rate", "power", "enhanced_speed", "speed", "distance", "cadence",
       "enhanced_altitude", "altitude", "temperature")
SESSION_KEEP = (
    "sport", "sub_sport", "total_timer_time", "total_elapsed_time", "total_distance", "total_ascent",
    "total_descent", "avg_heart_rate", "max_heart_rate", "avg_power", "max_power", "normalized_power",
    "threshold_power", "training_stress_score", "intensity_factor", "left_right_balance",
    "avg_cadence", "avg_running_cadence", "avg_vertical_oscillation", "avg_stance_time",
    "avg_stance_time_balance", "avg_step_length", "avg_vertical_ratio", "avg_temperature",
    "max_temperature", "total_training_effect", "total_anaerobic_training_effect",
    "training_load_peak", "num_lengths", "pool_length", "avg_stroke_distance", "avg_swolf",
    "total_strokes", "swim_stroke", "num_active_lengths", "total_calories", "avg_left_torque_effectiveness",
    "avg_right_torque_effectiveness", "avg_left_pedal_smoothness", "avg_right_pedal_smoothness",
    "avg_left_pco", "avg_right_pco", "avg_respiration_rate", "avg_flow", "avg_grit",
)


def _jsonable(v):
    if isinstance(v, (int, float, str)) or v is None:
        return v if not (isinstance(v, float) and (v != v)) else None
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return str(v)


def read(path):
    recs, session, sets = [], {}, []
    with fitdecode.FitReader(path, check_crc=fitdecode.CrcCheck.DISABLED) as fr:
        for frame in fr:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            if frame.name == "record":
                r = {}
                for f in frame.fields:
                    if f.name in REC and f.value is not None:
                        r[f.name] = f.value
                if "timestamp" in r:
                    recs.append(r)
            elif frame.name == "session" and not session:
                session = {f.name: _jsonable(f.value) for f in frame.fields if f.name in SESSION_KEEP and f.value is not None}
            elif frame.name == "set":
                s = {f.name: _jsonable(f.value) for f in frame.fields
                     if f.name in ("set_type", "duration", "repetitions", "weight", "category", "category_subtype") and f.value is not None}
                if s.get("set_type") in ("active", 1):
                    sets.append(s)
    return recs, session, sets


def grid(recs):
    """1 Hz arrays from the first record; gaps <= 10 s are held, longer gaps are NaN."""
    t0 = recs[0]["timestamp"]
    secs = np.array([(r["timestamp"] - t0).total_seconds() for r in recs])
    n = int(secs[-1]) + 1
    if n <= 1 or n > 60 * 3600:
        return None
    idx = secs.astype(int)
    out = {}
    for key in ("heart_rate", "power", "speed", "distance", "altitude"):
        src = {"speed": ("enhanced_speed", "speed"), "altitude": ("enhanced_altitude", "altitude")}.get(key, (key,))
        vals = np.full(n, np.nan)
        have = False
        for i, r in zip(idx, recs):
            v = next((r[s] for s in src if s in r and isinstance(r[s], (int, float))), None)
            if v is not None:
                vals[i] = v
                have = True
        if not have:
            continue
        # hold values across short gaps only
        last, last_i = np.nan, -99
        for i in range(n):
            if not np.isnan(vals[i]):
                last, last_i = vals[i], i
            elif i - last_i <= 10:
                vals[i] = last
        out[key] = vals
    return out


def peak(arr, dur):
    """Best mean over `dur` seconds of recorded time. Paused stretches (NaN) are dropped and the
    recorded segments joined, as TrainingPeaks and WKO do with auto-pause."""
    if arr is None:
        return None
    a = arr[~np.isnan(arr)]
    if len(a) < dur:
        return None
    cs = np.concatenate(([0.0], np.cumsum(a)))
    return float(np.max(cs[dur:] - cs[:-dur]) / dur)


def best_distance(dist, target):
    """Fastest time (s) to cover `target` metres, from the 1 Hz cumulative distance."""
    if dist is None:
        return None
    d = dist.copy()
    ok = ~np.isnan(d)
    if not ok.any() or np.nanmax(d) - np.nanmin(d) < target:
        return None
    t = np.arange(len(d))[ok]
    d = d[ok]
    d = np.maximum.accumulate(d)
    j = np.searchsorted(d, d + target)
    valid = j < len(d)
    if not valid.any():
        return None
    times = t[j[valid]] - t[valid]
    gaps = (t[j[valid]] - t[valid]) > 0
    return int(times[gaps].min()) if gaps.any() else None


def decoupling(g):
    hr = g.get("heart_rate")
    load = g.get("power") if g.get("power") is not None and np.nanmean(g["power"]) > 50 else g.get("speed")
    if hr is None or load is None:
        return None
    ok = ~np.isnan(hr) & ~np.isnan(load) & (load > 0) & (hr > 60)
    if ok.sum() < 3600:
        return None
    i = np.where(ok)[0]
    half = len(i) // 2
    a, b = i[:half], i[half:]
    r1 = np.mean(load[a]) / np.mean(hr[a])
    r2 = np.mean(load[b]) / np.mean(hr[b])
    return round((r1 / r2 - 1) * 100, 1)


def metrics(path):
    recs, session, sets = read(path)
    out = {"session": session}
    if sets:
        out["sets"] = sets
    if len(recs) < 30:
        return out
    g = grid(recs)
    if not g:
        return out
    for key, name in (("power", "peakPower"), ("heart_rate", "peakHr"), ("speed", "peakSpeed")):
        arr = g.get(key)
        if arr is None or np.nanmax(arr) <= 0:
            continue
        vals = {str(d): (round(v, 1) if key != "speed" else round(v, 3)) for d in DURS if (v := peak(arr, d)) is not None}
        if vals:
            out[name] = vals
    if g.get("distance") is not None and str(session.get("sport", "")).startswith("running"):
        bd = {str(d): v for d in DISTS if (v := best_distance(g["distance"], d)) is not None}
        if bd:
            out["bestTime"] = bd
    dc = decoupling(g)
    if dc is not None:
        out["decoupling"] = dc
    return out


if __name__ == "__main__":
    print(json.dumps(metrics(sys.argv[1]), indent=1))
