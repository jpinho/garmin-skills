# The Garmin archive: files, fields and units

`scripts/garmin_fetch.py archive START END -d DIR [--details] [--fit]` writes everything the Personal API holds for a date range to `DIR/garmin_<kind>_<START>_<END>.json.gz`. GPS, place names and owner fields are stripped by `scrub()`. Single `get` calls return the same shapes, unscrubbed.

Read a file with:

```python
import gzip, json, glob
path = sorted(glob.glob("DIR/garmin_activities_*.json.gz"))[-1]
acts = json.load(gzip.open(path, "rt"))
```

Glob the file names rather than hard-coding the dates: the end date moves on every refresh.

## Files

| kind | Shape | Key | One row is |
|---|---|---|---|
| `activities` | list, **newest first** | `activityId` | one activity, from the activity search |
| `activity_details` | dict, `--details` | `str(activityId)` | `activityTypeDTO`, `eventTypeDTO`, `summaryDTO`, `isMultiSportParent` (+ `splitSummaries` where present) |
| `fit_metrics` | dict, `--fit` | `str(activityId)` | metrics computed from the original FIT file by `garmin_fit.py`; swim, bike, run and strength types only |
| `hrv` | list | `calendarDate` | one night's HRV summary |
| `sleep` | list | `calendarDate` | one night's sleep |
| `daily` | list | `calendarDate` | one day's wellness summary |
| `weight` | list | `summaryDate` | one day with at least one weigh-in |
| `fitnessage` | dict | — | the latest fitness age, as of END |
| `hrzones` | list | `sport` | the HR zone setup per sport (`DEFAULT`, `RUNNING`, `CYCLING`, …) |

## Units

Garmin stores raw SI units, so convert before showing anything:

| Field | Unit | Convert |
|---|---|---|
| `distance` | m | ÷ 1000 → km |
| `duration`, `movingDuration`, `elapsedDuration`, `*Seconds` | s | |
| `averageSpeed`, `maxSpeed`, `avgGradeAdjustedSpeed`, `peakSpeed` | m/s | run pace min/km = 1000 / 60 / v; swim min/100 m = 100 / 60 / v |
| weight `weight`, `boneMass`, `muscleMass` | **g** | ÷ 1000 → kg |
| `bodyFat`, `bodyWater` | % | |
| `*TimestampGMT`, `date` (weight) | ms since epoch | |
| `startTimeLocal` | `"YYYY-MM-DD HH:MM:SS"`, local time | `[:10]` is the date |

For any other field, `scripts/garmin_spec.py show SPEC SCHEMA FIELD` prints Garmin's own description, which usually names the unit.

## Fields worth knowing

**activities** (`SummarizedActivityDTO`): `activityName`, `startTimeLocal`, `activityType.typeKey`, `distance`, `duration`, `movingDuration`, `averageSpeed`, `averageHR`, `maxHR`, `avgPower`, `normPower`, `calories`, `aerobicTrainingEffect`, `anaerobicTrainingEffect`, `activityTrainingLoad`, `lactateThresholdBpm`, `maxFtp`, `isParent`. The spec also lists `vO2MaxValue`, but it was missing from every one of 2,000+ activities checked.

Common `activityType.typeKey` values:
- Run: `running`, `trail_running`, `treadmill_running`, `track_running`
- Bike: `cycling`, `road_biking`, `virtual_ride`, `indoor_cycling`, `mountain_biking`, `gravel_cycling`
- Swim: `lap_swimming`, `open_water_swimming`, `swimming`
- `multi_sport`: the parent of a triathlon or brick, with `isParent: true`. Its legs are separate activities.
- Other: `strength_training`, `walking`, `hiking`, `yoga`, `hiit`, `indoor_rowing`, …

**activity_details → `summaryDTO`** has the fields the list lacks:
- `trainingEffect` (aerobic) and `anaerobicTrainingEffect`, with `trainingEffectLabel` and the messages
- `activityTrainingLoad`
- `avgGradeAdjustedSpeed`
- the running dynamics: `groundContactTime`, `strideLength`, `verticalOscillation`, `verticalRatio`
- `normalizedPower`, `totalWork`
- the stamina fields
- `directWorkoutRpe` and `directWorkoutFeel`, the user's own post-workout rating, when entered
- `differenceBodyBattery`

**fit_metrics** (from `garmin_fit.py`, 1 Hz grid):
- `peakPower`, `peakHr` and `peakSpeed`: `{"<seconds>": value}` for 5 s … 4 h
- `bestTime` (runs): `{"<metres>": seconds}` for 400 m … marathon
- `decoupling`: for steady sessions of 60 min or more
- `session`: a curated slice of the FIT session message, including running dynamics, L/R balance, swim strokes, training effect and temperature
- `sets`: strength sets
- `error`: when the file couldn't be parsed

**hrv**: `lastNightAvg` and `lastNight5MinHigh` (ms), `weeklyAvg`, `baseline.{lowUpper, balancedLow, balancedUpper}`, and `status`: `BALANCED`, `UNBALANCED`, `LOW`, or `NONE` while the baseline is still being built.

**sleep**:
- `sleepTimeSeconds`, and `deep`/`light`/`rem`/`awakeSleepSeconds`
- `sleepScores.overall.value`, with the `qualifierKey` per component
- `avgSleepStress`, `avgHeartRate`
- `averageRespirationValue`, `averageSpO2Value`
- `sleepNeed`

**daily**:
- `heartRate.restingValue`
- `bodyBattery.{minValue, maxValue, chargedValue, drainedValue}`
- `stress.avgLevel`
- `calories.{burnedTotal, burnedActive, burnedResting}`
- `intensityMinutes.{moderate, vigorous}`
- `movement.steps.value`
- `respiration` and `pulseOx`

**weight → `latestWeight`**: `weight` (g), `bmi`, `bodyFat`, `muscleMass` (g), and `sourceType` (`INDEX_SCALE` is Garmin's smart scale).

## Joins

- `activities.activityId` ↔ `activity_details` / `fit_metrics` keys (as strings).
- Daily files join on `calendarDate`. HRV and sleep rows are dated by the morning the night *ends*. A poor reading dated Tuesday reflects Monday's load.
- Other platforms (TrainingPeaks, Strava) don't carry the Garmin `activityId`. Match on the start date plus the sport, and check the duration (within about 5%) when there are two sessions of the same sport in a day.

## Known gaps

- Days with no watch worn have no `hrv` or `sleep` row. Report them as missing; never interpolate them.
- `daily` and `sleep` rows still carry `userProfilePk`/`userProfilePK`, because `scrub()` only drops keys containing `owner`. It's the user's numeric Garmin ID. Strip it before publishing an archive.
