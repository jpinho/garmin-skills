# garmin-skills

Agent skills for working with your own Garmin data.

## `garmin-connect`

Read-only access to your Garmin Connect data through Garmin's official [Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api/). It covers:
- activities and their detail records, and the original FIT files
- HRV and sleep
- daily wellness: resting HR, Body Battery, stress, calories
- weight and body composition
- the food log, HR zones and fitness age

It can also build a gzipped local archive of all of it, with GPS stripped.

```
skills/garmin-connect/
├── SKILL.md                  # when and how the agent uses it
├── scripts/
│   ├── garmin_fetch.py       # auth, single GETs, full archive (stdlib only)
│   ├── garmin_fit.py         # metrics from a FIT file (needs fitdecode, numpy)
│   └── garmin_spec.py        # fetches Garmin's OpenAPI spec and looks up schemas
└── references/
    ├── endpoints.md          # all 26 endpoints, params, range limits, auth facts
    └── data-model.md         # archive files, units, key fields, joins
```

### Setup

1. Create a personal API key in Garmin Connect: Settings → Personal API key.
2. Expose it as `GARMIN_API_KEY`:
   - In Claude Code cloud, set it as an **environment variable**, not a Network secret. The proxy would otherwise overwrite the bearer token on every call.
   - In Claude Code locally, copy `skills/garmin-connect` into your project's `.claude/skills/` (or `~/.claude/skills/`).
3. Check it works:

```bash
python3 skills/garmin-connect/scripts/garmin_fetch.py check
```

`check` prints the token scopes and expiry. It never prints the key or the token.

### Notes

- The API is read-only: there's no workout upload and no comments.
- Training status, readiness, VO2 max history and the race predictor aren't exposed.
- The rate limit is about 100 requests a minute, and the script backs off on HTTP 429.
- Garmin's API spec is their documentation. `garmin_spec.py` fetches it on demand instead of shipping a copy.
