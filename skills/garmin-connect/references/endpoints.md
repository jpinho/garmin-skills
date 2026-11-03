# Garmin Connect Personal API: endpoints

Source: the official Swagger docs at https://developer.garmin.com/gc-developer-program/personal/swagger-docs/ (OpenAPI 3.0.1, "Garmin Connect Personal API" 1.0.0). For a full response schema, with field types and units, fetch the spec locally with `scripts/garmin_spec.py` (below). Summarised 2026-11-03.

## Facts that apply to every call

| What | Value |
|---|---|
| Base URL | `https://personal.connectapi.garmin.com` (China: `personal.connectapi.garmin.cn`) |
| Methods | GET only. The API is read-only. |
| Token | `POST /personalapitoken-service/personal-api/personal-api-key/token` with `Authorization: ApiKey <key>`. Returns a JWT as plain text. Valid 24 h, or until the key expires. |
| Data calls | `Authorization: Bearer <token>`, `Accept: */*`. `Accept: application/json` gets HTTP 406. |
| Token scopes | `CONNECT_READ`, `PERSONAL_API_FITNESS_READ`, `PERSONAL_API_WELLNESS_READ`, `PERSONAL_API_USER_READ`, `PERSONAL_API_NUTRITION_READ` |
| Rate limit | About 100 requests a minute. HTTP 429 carries `retryInSeconds`. `garmin_fetch.py` waits it out. |
| Empty day | HTTP 204, or `null`/`[]`. `Garmin.get()` returns `None` for 204. |
| Dates | `YYYY-MM-DD`, in the user's local calendar |

Range limits, from the spec's descriptions. `garmin_fetch.py archive` chunks to stay under them:

| Endpoint | Max range | Chunk used by `archive` |
|---|---|---|
| `/sleep-service/sleep/dailySleepSummariesByDate` | 31 days | 28 |
| `/usersummary-service/stats/hydration/daily/…` | 31 days | — |
| `/wellness-service/wellness/bodyBattery/reports/daily` | 31 days | — |
| `/usersummary-service/stats/steps/daily/…`, `/stats/stress/daily/…` | 28 days | — |
| `/usersummary-service/v2/dailysummaries` | 1 year | 28 |
| `/hrv-service/hrv/daily/…` | not stated | 28 |
| `/weight-service/weight/range/…` | not stated | 366 |
| `/activitylist-service/activities/search/activities` | paginated: `start`, `limit` (100 works) | pages of 100 |

## Not available in this API

Training status, training readiness, acute/chronic load, VO2 max history, endurance score, hill score, race predictor, the lactate-threshold and FTP history charts. Some exist only per activity: `lactateThresholdBpm` and `maxFtp` on the activity list (the spec also lists `vO2MaxValue`, but it was missing from every one of 2,000+ activities checked), and `lactateThresholdHeartRate`/`lactateThresholdSpeed` in `summaryDTO`. For the trend charts, ask the user for a Garmin Connect screenshot.

Nothing can be written either: no comments, no workout upload, no activity edits.

## Looking up a response field

```bash
python3 scripts/garmin_spec.py fetch /tmp/garmin-openapi.json          # once per session
python3 scripts/garmin_spec.py show /tmp/garmin-openapi.json SummaryDTO grade
# avgGradeAdjustedSpeed   double   The average grade adjusted speed for the activity, in meters per second
```

The schema names are the `Returns:` types below. Keep the downloaded spec local: it's Garmin's documentation.

## Endpoints

In the spec's order. The activity search's geo and dive filters are left out.

### `GET /activity-service/activity/{activityId}`

Retrieves the activity summary, metadata, measurements, and split summary information for the specified activity.

- Params: `activityId` (path, int64)
- Returns: `ActivitySummaryDTO` — top-level fields: `activityId`, `activityUUID`, `activityName`, `description`, `userProfileId`, `parentId`, `parentName`, `isMultiSportParent`, `activityTypeDTO`, `eventTypeDTO`, `accessControlRuleDTO`, `timeZoneUnitDTO`, `metadataDTO`, `summaryDTO`, `locationName`, `diveInfo`, `splitSummaries`, `videoGameInfo`, `deviceDisplayUnitsDTO`

### `GET /activity-service/activity/{activityId}/workouts`

Retrieves workouts performed during an activity

- Params: `activityId` (path, int64)
- Returns: `ActivityWorkoutDTO[]` — top-level fields: `index`, `workoutName`, `timeCreated`, `sport`, `manufacturer`, `multisportSet`, `steps`, `workoutPhrase`

### `GET /activitylist-service/activities/search/activities`

Searches activities using the supplied filters and returns matching paginated activity summaries.

- Params: `start` (query, int32), `limit` (query, int32), `favorite` (query, int32), `sortOrder` (query, string), `excludeChildren` (query, boolean), `sortBy` (query, string), `search` (query, string), `activityType` (query, string), `activitySubType` (query, string), `eventType` (query, string), `minDistance` (query, int64), `maxDistance` (query, int64), `minDuration` (query, int64), `maxDuration` (query, int64), `minElevation` (query, int64), `maxElevation` (query, int64), `startDate` (query, date), `endDate` (query, date), `minElapsedDuration` (query, int64), `maxElapsedDuration` (query, int64), `minAvgPower` (query, int64), `excludedActivitySubType` (query, array), `requiredField` (query, array)
- Returns: `SummarizedActivityDTO[]` — top-level fields: `activityId`, `activityName`, `description`, `startTimeLocal`, `startTimeGMT`, `activityType`, `eventType`, `comments`, `isFavorite`, `isPR`, `isAutoCalcCalories`, `isParent`, `parentId`, `distance`, `duration`, `elapsedDuration`, `movingDuration`, `elevationGain`, `elevationLoss`, `averageSpeed`, `maxSpeed`, `startLatitude`, `startLongitude`, `hasPolyline`, `hasImages` …

### `GET /biometric-service/heartRateZones/v2`

Retrieve the user's heart rate zone configuration.

- Params: `generateDefaults` (query, boolean)
- Returns: `HeartRateZonesDTO[]` — top-level fields: `trainingMethod`, `restingHeartRateUsed`, `lactateThresholdHeartRateUsed`, `zone1Floor`, `zone2Floor`, `zone3Floor`, `zone4Floor`, `zone5Floor`, `maxHeartRateUsed`, `restingHrAutoUpdateUsed`, `sport`

### `GET /download-service/files/activity/{activityId}`

Download an activity file in its original format.

- Params: `activityId` (path, int64)
- Returns: `application/x-zip-compressed`

### `GET /fitnessage-service/fitnessage/v2/{calendarDate}`

Returns the lastest Fitness Age information as of the target calendar date.

- Params: `calendarDate` (path, date), `fullHistoryScan` (query, boolean)
- Returns: `FitnessAgeDTO[]` — top-level fields: `chronologicalAge`, `fitnessAge`, `achievableFitnessAge`, `previousFitnessAge`, `components`, `lastUpdated`, `invalidReason`

### `GET /goal-service/goal/user/effective/weightgoal/{startDate}/{endDate}`

Returns the authenticated user's effective weight goals and weight goal ranges for the requested date interval.

- Params: `startDate` (path, date), `endDate` (path, date)
- Returns: `UserGoalsRangeDTO` — top-level fields: `userGoals`, `userGoalRanges`

### `GET /hrv-service/hrv/{calendarDate}`

Get HRV data for a specific date

- Params: `calendarDate` (path, date)
- Returns: `HrvChartDTO` — top-level fields: `userProfilePk`, `hrvSummary`, `hrvReadings`, `startTimestampGMT`, `endTimestampGMT`, `startTimestampLocal`, `endTimestampLocal`, `sleepStartTimestampGMT`, `sleepEndTimestampGMT`, `sleepStartTimestampLocal`, `sleepEndTimestampLocal`

### `GET /hrv-service/hrv/daily/{fromDate}/{toDate}`

Get HRV daily summaries for a date range

- Params: `fromDate` (path, date), `toDate` (path, date)
- Returns: `HrvDailySummaryDTO` — top-level fields: `hrvSummaries`, `userProfilePk`

### `GET /nutrition-service/food/logs/{date}`

Retrieves the user's daily nutrition summary for a specific calendar date. This includes the user's nutrition goals, nutrients consumed, and discrete events for the day. The response can optionally include meal-by-meal breakdowns of calories and other nutrients consumed by the user on the given date.

- Params: `includeGoals` (query, boolean), `includeNutrition` (query, boolean), `includeMedia` (query, boolean), `mealId` (query, int64), `date` (path, date)
- Returns: `DailyNutritionSummaryDTO` — top-level fields: `dailyNutritionContent`, `dailyNutritionGoals`, `dayEndTime`, `dayStartTime`, `loggedFoodsWithServingSizes`, `mealDate`, `mealDetails`

### `GET /periodichealth-service/menstrualcycle/summary/{calendarDate}`

Returns a summary of the user's menstrual cycle.

- Params: `calendarDate` (path, date)
- Returns: `MenstrualCycleSummaryDTO` — top-level fields: `analysis`, `currentPhase`, `cycleType`, `dayInCycle`, `daysUntilNextPhase`, `deliveryDate`, `dueDate`, `educationContentMod`, `endDate`, `feedbackPhrase`, `fertileWindowStart`, `isSkinTempMct`, `lengthOfCurrentPhase`, `lengthOfFertileWindow`, `lutealPhaseStart`, `numberOfWeek`, `overlapCycleList`, `periodLength`, `predictedCycle`, `predictedCycleLength`, `predictedOvulationDate`, `pregnancyCycle`, `startDate`

### `GET /periodichealth-service/menstrualcycle/dayview/{calendarDate}`

Returns detailed menstrual cycle information for a single calendar day, combining the user's logged daily data (symptoms, flow, mood, etc.), the cycle summary for that day, and (for pregnancy tracking) weekly weight goal ranges.

- Params: `calendarDate` (path, date), `todayDate` (query, date), `reducedResponse` (query, boolean), `skipbm` (query, boolean), `includeAnalysis` (query, boolean)
- Returns: `DetailedMenstrualCycleDayDTO` — top-level fields: `dayLog`, `daySummary`, `weightGoals`

### `GET /sleep-service/sleep/dailySleep`

Retrieves daily sleep data for a calendar date

- Params: `date` (query, date)
- Returns: `DailySleepDTO` — top-level fields: `id`, `userProfilePK`, `calendarDate`, `sleepTimeSeconds`, `napTimeSeconds`, `sleepWindowConfirmed`, `sleepWindowConfirmationType`, `sleepStartTimestampGMT`, `sleepEndTimestampGMT`, `sleepStartTimestampLocal`, `sleepEndTimestampLocal`, `autoSleepStartTimestampGMT`, `autoSleepEndTimestampGMT`, `sleepQualityTypePK`, `sleepResultTypePK`, `unmeasurableSleepSeconds`, `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds`, `deviceRemCapable`, `sleepFromDevice`, `averageSpO2Value`, `lowestSpO2Value`, `highestSpO2Value` …

### `GET /sleep-service/sleep/dailySleepSummariesByDate`

Retrieves daily sleep summaries data for a date range, up to a maximum of 31 days.

- Params: `startDate` (query, date), `endDate` (query, date)
- Returns: `DailySleepDTO[]` — top-level fields: `id`, `userProfilePK`, `calendarDate`, `sleepTimeSeconds`, `napTimeSeconds`, `sleepWindowConfirmed`, `sleepWindowConfirmationType`, `sleepStartTimestampGMT`, `sleepEndTimestampGMT`, `sleepStartTimestampLocal`, `sleepEndTimestampLocal`, `autoSleepStartTimestampGMT`, `autoSleepEndTimestampGMT`, `sleepQualityTypePK`, `sleepResultTypePK`, `unmeasurableSleepSeconds`, `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds`, `deviceRemCapable`, `sleepFromDevice`, `averageSpO2Value`, `lowestSpO2Value`, `highestSpO2Value` …

### `GET /userprofile-service/userprofile/settings`

Retrieve the user profile settings.

- Params: none
- Returns: `UserSettingsDTO` — top-level fields: `displayName`, `preferredLocale`, `measurementSystem`, `firstDayOfWeek`, `numberFormat`, `timeFormat`, `dateFormat`, `powerFormat`, `heartRateFormat`, `timeZone`, `hydrationMeasurementUnit`, `hydrationContainers`, `glucoseMeasurementUnit`, `golfDistanceUnit`, `golfElevationUnit`, `golfSpeedUnit`, `wheelchairModeEnabled`, `availableTrainingDays`, `preferredLongTrainingDays`

### `GET /usersummary-service/stats/hydration/daily/{startDate}/{endDate}`

Get daily hydration data for a date range, up to a maximum of 31 days.

- Params: `startDate` (path, date), `endDate` (path, date)
- Returns: `UserDailyHydrationDTO[]` — top-level fields: `userId`, `calendarDate`, `valueInML`, `goalInML`, `lastEntryTimestampLocal`, `sweatLossInML`, `activityIntakeInML`

### `GET /usersummary-service/stats/steps/daily/{startDate}/{endDate}`

Get daily steps data for a date range, up to a maximum of 28 days.

- Params: `startDate` (path, date), `endDate` (path, date)
- Returns: `StepsDailyStatDTO[]` — top-level fields: `calendarDate`, `totalSteps`, `totalDistance`, `stepGoal`

### `GET /usersummary-service/stats/stress/daily/{startDate}/{endDate}`

Get daily stress data for a date range, up to a maximum of 28 days.

- Params: `startDate` (path, date), `endDate` (path, date)
- Returns: `MultiValueWellnessChartItemDTO[]` — top-level fields: `calendarDate`, `values`

### `GET /usersummary-service/usersummary/daily`

Get user summary data for a specific date. User summary data includes steps, calories, stress, Body Battery, and other wellness metrics for the given date.

- Params: `calendarDate` (query, date)
- Returns: `UserDailySummaryDto` — top-level fields: `userProfileId`, `displayName`, `totalKilocalories`, `activeKilocalories`, `bmrKilocalories`, `consumedKilocalories`, `remainingKilocalories`, `totalSteps`, `netCalorieGoal`, `totalDistanceMeters`, `wellnessDistanceMeters`, `userDailySummaryId`, `calendarDate`, `uuid`, `dailyStepGoal`, `dailyPushesGoal`, `totalPushDistance`, `totalPushes`, `wellnessStartTimeGmt`, `wellnessStartTimeLocal`, `wellnessEndTimeGmt`, `wellnessEndTimeLocal`, `durationInMilliseconds`, `wellnessDescription`, `highlyActiveSeconds` …

### `GET /usersummary-service/v2/dailysummaries`

Get user daily summaries for a date range, up to a maximum of 1 year.

- Params: `startDate` (query, date), `endDate` (query, date)
- Returns: `ApiDocumentListUserDailySummaryV2DTO` — top-level fields: `data`

### `GET /weight-service/weight/all/{startDate}/{endDate}`

Retrieve all weight entries for a specified date range.

- Params: `startDate` (path, date), `endDate` (path, date)
- Returns: `DateWeightDTO[]` — top-level fields: `date`, `calendarDate`, `weight`, `bmi`, `bodyFat`, `bodyWater`, `boneMass`, `muscleMass`, `physiqueRating`, `visceralFat`, `metabolicAge`, `timestampGMT`, `weightDelta`

### `GET /weight-service/weight/range/{startDate}/{endDate}`

Retrieve weight summaries for a date range, including daily latest weights, the range average, and adjacent weights.

- Params: `startDate` (path, date), `endDate` (path, date), `includeAll` (query, boolean)
- Returns: `WeightRangeDTO` — top-level fields: `dailyWeightSummaries`, `totalAverage`, `previousDateWeight`, `nextDateWeight`

### `GET /wellness-service/wellness/bodyBattery/reports/daily`

Returns daily Body Battery reports for a date range, up to a maximum of 31 days.

- Params: `startDate` (query, date), `endDate` (query, date), `chunks` (query, int32)
- Returns: `BodyBatteryDailyReportDTO[]` — top-level fields: `date`, `charged`, `drained`, `startTimestampGMT`, `endTimestampGMT`, `startTimestampLocal`, `endTimestampLocal`, `bodyBatteryValuesArray`, `bodyBatteryValueDescriptorDTOList`, `bodyBatteryDynamicFeedbackEvent`, `bodyBatteryActivityEvent`, `endOfDayBodyBatteryDynamicFeedbackEvent`

### `GET /wellness-service/wellness/daily/spo2acclimation/{calendarDate}`

Returns daily SpO2 readings data for a given calendar date.

- Params: `calendarDate` (path, date)
- Returns: `DailySpO2AndAcclimationDTO` — top-level fields: `userProfilePK`, `calendarDate`, `startTimestampGMT`, `endTimestampGMT`, `startTimestampLocal`, `endTimestampLocal`, `sleepStartTimestampGMT`, `sleepEndTimestampGMT`, `sleepStartTimestampLocal`, `sleepEndTimestampLocal`, `tomorrowSleepStartTimestampGMT`, `tomorrowSleepEndTimestampGMT`, `tomorrowSleepStartTimestampLocal`, `tomorrowSleepEndTimestampLocal`, `averageSpO2`, `lowestSpO2`, `lastSevenDaysAvgSpO2`, `latestSpO2`, `latestSpO2TimestampGMT`, `latestSpO2TimestampLocal`, `avgSleepSpO2`, `avgTomorrowSleepSpO2`, `spO2SingleValuesDescriptorList`, `spO2SingleValues`, `spO2HourlyAveragesDescriptorList` …

### `GET /wellness-service/wellness/dailyHeartRate`

Returns daily heart rate data for a given date.

- Params: `date` (query, date)
- Returns: `DailyHeartRateDTO` — top-level fields: `userProfilePK`, `calendarDate`, `startTimestampGMT`, `endTimestampGMT`, `startTimestampLocal`, `endTimestampLocal`, `maxHeartRate`, `minHeartRate`, `restingHeartRate`, `lastSevenDaysAvgRestingHeartRate`, `abnormalHrThresholdValue`, `lowAbnormalHrThresholdValue`, `abnormalHRValuesArray`, `heartRateValueDescriptors`, `heartRateValues`

### `GET /wellnessactivity-service/activity/summary/range/{fromDate}/{untilDate}`

Returns a list of wellness activity summaries for the given date range. The fromDate and untilDate are inclusive.

- Params: `fromDate` (path, date), `untilDate` (path, date)
- Returns: `WellnessActivitySummaryDTO[]` — top-level fields: `userProfilePk`, `activityUuid`, `calendarDate`, `rulePK`, `activityName`, `notes`, `wellnessActivityType`, `startTimestampGMT`, `endTimestampGMT`, `startTimestampLocal`, `endTimestampLocal`, `summaryTypeDataList`, `timeInZoneList`, `deviceMetaData`
