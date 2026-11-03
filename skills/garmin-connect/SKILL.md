---
name: garmin-connect
description: Read the user's own Garmin Connect data through Garmin's official Personal API. Covers activities and their detail records, original FIT files, HRV, sleep, daily wellness (resting HR, Body Battery, stress, calories burned), weight and body composition, the food log, HR zones and fitness age, plus a gzipped local archive of all of it. Use it whenever a question or task needs Garmin data, even if the user doesn't say "Garmin". That includes recovery or readiness checks (HRV status, sleep score, resting HR, Body Battery), an activity's training effect or training load, grade-adjusted pace, running dynamics, power, HR or pace peaks from FIT files, the weight trend, logged nutrition vs calories burned, building or refreshing a Garmin data archive, and debugging a Garmin Personal API key or token. The API is read-only. It can't create workouts or post anything to Garmin.
---

# Garmin Connect

Garmin's **official Personal API** gives read-only access to a user's own Garmin Connect data. The bundled `scripts/garmin_fetch.py` wraps it: the key-for-token exchange, the retries, the rate limit, and a privacy scrub for anything archived. Paths below are relative to this skill's directory. The scripts use only the standard library, except `garmin_fit.py`, which needs `pip install fitdecode numpy`.

If the project already holds an archive (`find . -name 'garmin_*.json.gz'`), read that first. Call the API only for days after its end date, or for data it doesn't hold.

## Before anything

1. **Key:** the user creates a personal API key at connect.garmin.com → Settings → Personal API key. It starts with `GCDC_`. It goes in the environment variable `GARMIN_API_KEY` (`GARMIN_PERSONAL_API_KEY` also works), or in a file passed with `--key-file`. Check it with `python3 scripts/garmin_fetch.py check`, which prints the token scopes and the hours left. Never print, echo or commit the key or the token (a JWT), and never ask for either in chat.
2. **If the check or a call fails:**

   | Symptom | Cause | Fix |
   |---|---|---|
   | `No key` | The variable isn't set | The user sets it. In a Claude Code cloud environment, that's an environment variable in the environment settings, picked up by the next session. |
   | `Token exchange failed: HTTP 401/403` | The key expired or was revoked | The user creates a new key in Garmin Connect |
   | The token works, but **every** data call returns 403, and a valid token and a garbage one get the same 403 | Something between you and Garmin is rewriting `Authorization`. In Claude Code cloud, a **Network secret** for `personal.connectapi.garmin.com` makes the proxy replace the `Bearer` header with `ApiKey <key>` on every request (`X-Proxy-Error: upstream denied the request`). | Delete the network secret, and pass the key as an environment variable instead |
   | HTTP 406 | `Accept: application/json` was sent | Send `Accept: */*`. The script already does. |
   | HTTP 429 | Over the limit of about 100 requests a minute | The script waits as long as `retryInSeconds` says. Prefer range endpoints over per-day calls. |

## Where to get the data

| Need | Use |
|---|---|
| History already archived | The archive files. Their fields, units and joins are in `references/data-model.md`. |
| Anything recent, or one-off | `python3 scripts/garmin_fetch.py get "PATH"`. All 26 endpoints are in `references/endpoints.md`. |
| A response field you don't recognise | `python3 scripts/garmin_spec.py fetch <tmp>/spec.json` once, then `show <tmp>/spec.json SCHEMA [TEXT]` for Garmin's description and unit |
| Peak power, HR or pace, best times by distance, decoupling, from a FIT file | `python3 scripts/garmin_fit.py FILE.fit`, or `archive --fit` for every activity |

## Recipes

Replace `D` with the date (`YYYY-MM-DD`) and `ID` with the `activityId`:

```bash
# This morning's readiness: HRV, sleep, resting HR and Body Battery
python3 scripts/garmin_fetch.py get /hrv-service/hrv/daily/D/D
python3 scripts/garmin_fetch.py get "/sleep-service/sleep/dailySleep?date=D"
python3 scripts/garmin_fetch.py get "/usersummary-service/usersummary/daily?calendarDate=D"

# The latest activities, then one in full (training effect, load, GAP, running dynamics)
python3 scripts/garmin_fetch.py get "/activitylist-service/activities/search/activities?start=0&limit=10"
python3 scripts/garmin_fetch.py get /activity-service/activity/ID

# One day's food log (kcal and macros in dailyNutritionContent)
python3 scripts/garmin_fetch.py get "/nutrition-service/food/logs/D?includeMedia=false"

# The original FIT file, as a zip: unzip it in a temp dir, run garmin_fit.py on it, then delete it
python3 scripts/garmin_fetch.py get /download-service/files/activity/ID -o <tmp>/ID.zip
```

**Build or refresh an archive.** Pull the whole range in the background, into a temp directory:

```bash
python3 scripts/garmin_fetch.py archive FIRST_DAY YESTERDAY --details --fit -d <tmp>/garmin --work <tmp>/garmin-work
```

- `--details` makes one call per activity, and `--fit` makes one more. At about 100 requests a minute, a few thousand activities take upwards of half an hour. `--work` makes it resumable.
- Once it finishes, swap the new files in for the old ones.
- Check the row counts didn't drop before you commit anything.

## Reading the numbers

- **Units are raw SI:** metres, seconds, m/s, and **grams** for weight. Convert to km, min/km, min/100 m and kg before you show anything.
- **Training effect:** an aerobic TE of 3.0 or more on a run that was meant to be easy means it wasn't easy.
- **HRV `status`** is judged against Garmin's own baseline (`baseline.balancedLow`–`balancedUpper`). Trust the trend over a single night. Two or more `LOW` or `UNBALANCED` nights in a row is the signal, not one.
- **Garmin's training load is its own model.** It isn't TrainingPeaks' TSS, and it isn't CTL/ATL. Never mix them in one series or one table.
- **Not in the API:** training status, training readiness, VO2 max history, endurance and hill scores, the race predictor, and the LT and FTP trend charts. Ask the user for a Garmin Connect screenshot rather than estimating.

## Rules

- **Read-only.** You can't comment on, edit or upload anything to Garmin. Structured workouts reach the watch through another platform (e.g. TrainingPeaks or Garmin's own app).
- **Privacy:**
  - `archive` scrubs GPS, place names and owner fields, but `get` does not.
  - Keep raw `get` output in a temp directory. Commit only summaries, or data passed through `garmin_fetch.scrub()`.
  - Never commit FIT files: they contain the GPS track.
  - Don't call the women's-health endpoints unless the user asks.
- **Missing is missing.** A night without HRV, a day without a food log, an activity without a FIT file: report it as missing. Never interpolate or estimate it.
- **Name the source and date** of every number you report ("Garmin, night of 2 Nov"). Garmin often disagrees with other platforms on FTP, thresholds and load.
