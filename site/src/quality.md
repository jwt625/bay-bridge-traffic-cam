---
title: Data Quality
---

```js
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {basePlotStyle, colors, isoDate, parseDaily, percent} from "./components/data.js";

const dailyRows = await FileAttachment("./data/archive-v3/daily.csv").csv({typed: true});
const gapRows = await FileAttachment("./data/archive-v3/coverage-gaps.csv").csv({typed: true});
const resetRows = await FileAttachment("./data/archive-v3/counter-resets.csv").csv({typed: true});
const summaryRows = await FileAttachment("./data/archive-v3/summary.csv").csv({typed: true});
const nightRows = await FileAttachment("./data/archive-v3/night-noise.csv").csv({typed: true});
const impactRows = await FileAttachment("./data/archive-v3/lighting-impact-summary.csv").csv({typed: true});
const eventRows = await FileAttachment("./data/archive-v3/lighting-events.csv").csv({typed: true});
const daily = parseDaily(dailyRows);
const gaps = gapRows.map((row) => ({
  ...row,
  last_sample_local: new Date(row.last_sample_local),
  next_sample_local: new Date(row.next_sample_local),
  duration_minutes: +row.duration_minutes
}));
const resets = resetRows.map((row) => ({
  ...row,
  timestamp_local: new Date(row.timestamp_local),
  value: +row.value,
  delta: +row.delta
}));
const nightNoise = nightRows.map((row) => ({
  ...row,
  night_date: isoDate(row.night_date),
  date: new Date(`${isoDate(row.night_date)}T12:00:00Z`),
  mean_flow: +row.mean_flow,
  std_flow: +row.std_flow,
  p95_flow: +row.p95_flow,
  max_flow: +row.max_flow,
  spike_excess: +row.spike_excess,
  median_abs_change: +row.median_abs_change,
  coverage: +row.coverage
}));
const impact = impactRows.map((row) => ({
  ...row,
  nights: +row.nights,
  median_night_std: +row.median_night_std,
  median_night_max: +row.median_night_max,
  median_spike_excess: +row.median_spike_excess,
  median_abs_change: +row.median_abs_change
}));
const lightingEvents = eventRows.map((row) => ({
  ...row,
  local_date: isoDate(row.local_date),
  date: new Date(`${isoDate(row.local_date)}T12:00:00Z`)
}));

const dailyCoverage = d3
  .rollups(
    daily,
    (rows) => ({
      date: rows[0].date,
      coverage: d3.min(rows, (row) => row.coverage),
      complete: rows.every((row) => row.complete_day)
    }),
    (row) => row.local_date
  )
  .map(([local_date, values]) => ({local_date, ...values}))
  .sort((a, b) => d3.ascending(a.date, b.date));

const completeDays = dailyCoverage.filter((row) => row.complete).length;
const largestGap = d3.greatest(gaps, (row) => row.duration_minutes);
const completeNightNoise = nightNoise.filter((row) => row.coverage >= 0.95);
const combinedNightNoise = d3
  .rollups(
    completeNightNoise,
    (rows) => ({
      date: rows[0].date,
      lighting_period: rows[0].lighting_period,
      spike_excess: d3.mean(rows, (row) => row.spike_excess),
      median_abs_change: d3.mean(rows, (row) => row.median_abs_change),
      max_flow: d3.max(rows, (row) => row.max_flow)
    }),
    (row) => row.night_date
  )
  .map(([night_date, values]) => ({night_date, ...values}))
  .sort((a, b) => d3.ascending(a.date, b.date));
const preImpact = impact.filter((row) => row.lighting_period === "pre_lights");
const postImpact = impact.filter((row) => row.lighting_period === "illuminated");
const preSpike = d3.mean(preImpact, (row) => row.median_spike_excess);
const postSpike = d3.mean(postImpact, (row) => row.median_spike_excess);
const preMax = d3.mean(preImpact, (row) => row.median_night_max);
const postMax = d3.mean(postImpact, (row) => row.median_night_max);
const preStd = d3.mean(preImpact, (row) => row.median_night_std);
const postStd = d3.mean(postImpact, (row) => row.median_night_std);
```

<div class="page-kicker">Integrity / coverage / limitations</div>

# Data quality

<p class="lede">The archive is highly complete but not continuous. Coverage, restarts, imported series, and algorithmic limitations are first-class data—not cleanup details.</p>

```js
html`<div class="grid grid-cols-4">
  <div class="metric-card green">
    <div class="metric-label">Complete days</div>
    <div class="metric-value">${completeDays}</div>
    <div class="metric-detail">both directions ≥95% coverage</div>
  </div>
  <div class="metric-card yellow">
    <div class="metric-label">Gaps &gt;10 min</div>
    <div class="metric-value">${gaps.length}</div>
    <div class="metric-detail">explicitly retained in coverage metadata</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Largest gap</div>
    <div class="metric-value">${(largestGap.duration_minutes / 60).toFixed(1)} h</div>
    <div class="metric-detail">${largestGap.last_sample_local.toLocaleDateString("en-US")}</div>
  </div>
  <div class="metric-card blue">
    <div class="metric-label">Counter reset events</div>
    <div class="metric-value">${resets.length / 2}</div>
    <div class="metric-detail">one shared reset represented by two directions</div>
  </div>
</div>`
```

<div class="card chart-panel">
  <div class="panel-title">Daily sample coverage</div>
  <div class="panel-subtitle">Minimum of both directions · 95% completeness threshold</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 330,
    marginLeft: 52,
    x: {label: null},
    y: {label: "coverage", domain: [0, 1], grid: true, tickFormat: (value) => percent(value, 0)},
    marks: [
      Plot.ruleY([0.95], {stroke: colors.warn, strokeDasharray: "5,4"}),
      Plot.areaY(dailyCoverage, {
        x: "date",
        y: "coverage",
        fill: colors.good,
        fillOpacity: 0.18
      }),
      Plot.lineY(dailyCoverage, {
        x: "date",
        y: "coverage",
        stroke: colors.good,
        strokeWidth: 1.2,
        tip: true
      })
    ]
  })
)
```
</div>

## Bay Lights optical regime change

The 48,000-LED installation entered a 24/7 burn-in approximately February 19,
2026, according to a February 26 report in the
[San Francisco Chronicle](https://www.sfchronicle.com/sf/article/bay-lights-return-bay-bridge-21944006.php/).
The [official Grand Lighting](https://illuminate.org/2026/02/19/the-bay-lights-to-return-friday-march-20-2026/)
followed on March 20, after which the primary installation was scheduled to run
nightly from dusk until dawn.

The camera data shows a pronounced nighttime detector discontinuity during
commissioning, with a sharp high-noise onset around March 8–12 and persistent
elevation after March 20. The timing and night-only signature are consistent
with animated LEDs creating false motion tracks. This is strong observational
evidence, not a controlled causal experiment.

```js
html`<div class="grid grid-cols-3">
  <div class="metric-card orange">
    <div class="metric-label">Night spike excess</div>
    <div class="metric-value">${(postSpike / preSpike).toFixed(1)}×</div>
    <div class="metric-detail">post-launch / pre-lights median · both directions averaged</div>
  </div>
  <div class="metric-card yellow">
    <div class="metric-label">Median nightly maximum</div>
    <div class="metric-value">${(postMax / preMax).toFixed(1)}×</div>
    <div class="metric-detail">${preMax.toFixed(0)} → ${postMax.toFixed(0)} detections/min</div>
  </div>
  <div class="metric-card blue">
    <div class="metric-label">Within-night variability</div>
    <div class="metric-value">${(postStd / preStd).toFixed(1)}×</div>
    <div class="metric-detail">post-launch / pre-lights median nightly σ</div>
  </div>
</div>`
```

<div class="card chart-panel">
  <div class="panel-title">Nighttime spike excess</div>
  <div class="panel-subtitle">22:00–05:00 Pacific · mean of directions · nightly p95 minus median</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 390,
    marginLeft: 58,
    x: {label: null},
    y: {label: "p95 − median detections / min", grid: true},
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.ruleX(lightingEvents, {
        x: "date",
        stroke: (row) => row.event_type === "derived" ? colors.warn : colors.bad,
        strokeDasharray: "5,4",
        tip: true
      }),
      Plot.lineY(combinedNightNoise, {
        x: "date",
        y: "spike_excess",
        stroke: colors.right,
        strokeWidth: 1.2,
        tip: true
      })
    ]
  })
)
```
</div>

<div class="note danger">
Do not compare mixed-regime nighttime statistics as though the sensor were
stable. Use pre-lights, commissioning, illuminated-era, or all-data controls on
the analysis pages. Pre-lights is the preferred baseline for traffic-pattern
interpretation; commissioning should generally be treated as a transition
period.
</div>

## Longest interruptions

```js
Inputs.table(
  gaps
    .slice()
    .sort((a, b) => d3.descending(a.duration_minutes, b.duration_minutes))
    .slice(0, 12),
  {
    columns: ["last_sample_local", "next_sample_local", "duration_minutes"],
    header: {
      last_sample_local: "Last sample",
      next_sample_local: "Next sample",
      duration_minutes: "Gap (min)"
    },
    format: {
      last_sample_local: (value) => value.toLocaleString("en-US"),
      next_sample_local: (value) => value.toLocaleString("en-US"),
      duration_minutes: (value) => value.toFixed(0)
    },
    width: {
      last_sample_local: 230,
      next_sample_local: 230,
      duration_minutes: 110
    }
  }
)
```

## Counter reset

```js
Inputs.table(resets, {
  columns: ["timestamp_local", "direction", "value", "delta"],
  header: {
    timestamp_local: "Timestamp",
    direction: "Direction",
    value: "New counter",
    delta: "Observed drop"
  },
  format: {
    timestamp_local: (value) => value.toLocaleString("en-US"),
    value: (value) => value.toLocaleString("en-US"),
    delta: (value) => value.toLocaleString("en-US")
  }
})
```

The reset occurred on August 9, 2025 after an interruption. The detector ignores persisted counter state older than 24 hours, allowing both directional counters to restart. Published lifetime totals must therefore use reset-aware positive deltas, not the final counter value alone.

## Known limitations

- Counts are motion-tracker crossing events, not manually labeled vehicles.
- There is no labeled validation set and therefore no measured precision,
  recall, false-positive rate, or false-negative rate.
- False positives, missed objects, occlusion, merged tracks, and fragmented
  tracks are possible and can vary with direction, traffic density, daylight,
  weather, and optical regime.
- External counts show direction-dependent undercount: rough full-day
  pre-lights reference ratios are 2.45× Oakland-bound and 1.36× SF-bound. These
  are diagnostics, not correction factors. See
  [External Validation](./validation).
- Direction labels are camera-relative and mapped to destinations by installation geometry.
- Pixel-speed metrics are not calibrated to physical speed.
- Animated Bay Lights materially contaminate nighttime motion counts and
  relative-speed features beginning during February–March 2026 commissioning.
- Early historical imports created extra `exported_*` label series. The raw archive will preserve them; the canonical release must reconcile them explicitly.
- Five-minute site data is a Prometheus range-query snapshot, not a lossless export of exact scrape timestamps.
- No continuous source imagery was retained, so retrospective visual relabeling is not possible.

<div class="note danger">
Preservation status: the active 689.6 MB Prometheus Docker volume has been identified but not yet frozen into an immutable verified copy. No volume, block, or historical artifact should be deleted or recreated before that backup exists.
</div>
