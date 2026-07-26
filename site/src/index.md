---
title: Overview
toc: false
---

```js
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {
  basePlotStyle,
  colors,
  countScaleFactor,
  countScalingLabel,
  countScalingModes,
  fixed,
  isoDate,
  parseDaily,
  shortNumber,
  summaryObject
} from "./components/data.js";

const summaryRows = await FileAttachment("./data/archive-v3/summary.csv").csv({typed: true});
const dailyRows = await FileAttachment("./data/archive-v3/daily.csv").csv({typed: true});
const summary = summaryObject(summaryRows);
const daily = parseDaily(dailyRows);
const completeDaily = daily.filter((row) => row.complete_day);

const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
```

<div class="page-kicker">Historical system archive / snapshot v3</div>

# A year watching Bay Bridge traffic

<p class="lede">Algorithmic crossing detections from a window-facing camera, collected continuously from August 2025 through July 2026. The live system is now offline; this archive preserves the measurements, operating history, and limitations.</p>

<div class="status-line">
  <span class="status-item offline">Collection complete</span>
  <span class="status-item">Derived snapshot verified</span>
  <span class="status-item warn">Lossless TSDB archive pending</span>
  <span class="status-item warn">Night sensor regime changed Mar 2026</span>
  <span class="status-item">No source data deleted</span>
</div>

```js
const countScaling = view(
  Inputs.radio(countScalingModes, {
    label: "Traffic-count display",
    value: "reference_scaled",
    format: countScalingLabel
  })
);
```

```js
const displayDaily = completeDaily.map((row) => {
  const factor = countScaleFactor(row.direction, countScaling);
  return {
    ...row,
    counter_positive_increments: row.counter_positive_increments * factor,
    mean_flow: row.mean_flow * factor
  };
});

const combinedDaily = d3
  .rollups(
    displayDaily,
    (rows) => ({
      date: rows[0].date,
      detections: d3.sum(rows, (row) => row.counter_positive_increments),
      coverage: d3.min(rows, (row) => row.coverage)
    }),
    (row) => row.local_date
  )
  .map(([local_date, values]) => ({local_date, ...values}))
  .sort((a, b) => d3.ascending(a.date, b.date));

const weekdayMeans = d3
  .rollups(
    displayDaily,
    (rows) => d3.mean(rows, (row) => row.mean_flow),
    (row) => row.weekday,
    (row) => row.direction
  )
  .flatMap(([weekday, directions]) =>
    directions.map(([direction, mean_flow]) => ({weekday, direction, mean_flow}))
  );
```

```js
html`<div class="grid grid-cols-4">
  <div class="metric-card blue">
    <div class="metric-label">Algorithmic detections</div>
    <div class="metric-value">${shortNumber(+summary.positive_counter_increments_5min, 1)}</div>
    <div class="metric-detail">positive counter increments after first retained sample</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Observed span</div>
    <div class="metric-value">${fixed(+summary.observed_span_days, 0)} d</div>
    <div class="metric-detail">${isoDate(summary.collection_start_local)} → ${isoDate(summary.collection_end_local)}</div>
  </div>
  <div class="metric-card green">
    <div class="metric-label">Complete days</div>
    <div class="metric-value">${summary.complete_calendar_days}</div>
    <div class="metric-detail">≥95% directional five-minute coverage</div>
  </div>
  <div class="metric-card yellow">
    <div class="metric-label">Documented gaps</div>
    <div class="metric-value">${summary.coverage_gaps_over_10min}</div>
    <div class="metric-detail">interruptions longer than 10 minutes</div>
  </div>
</div>`
```

<div class="grid grid-cols-2">
  <div class="card chart-panel">
    <div class="panel-title">Daily traffic estimate</div>
    <div class="panel-subtitle">${countScalingLabel(countScaling)} · complete days only</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 320,
    marginLeft: 58,
    x: {label: null, grid: false},
    y: {label: countScaling === "raw" ? "detections / day" : "reference-scaled vehicles / day", grid: true, tickFormat: "s"},
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.areaY(combinedDaily, {
        x: "date",
        y: "detections",
        fill: colors.left,
        fillOpacity: 0.16
      }),
      Plot.lineY(combinedDaily, {
        x: "date",
        y: "detections",
        stroke: colors.left,
        strokeWidth: 1.2,
        tip: true
      })
    ]
  })
)
```
  </div>

  <div class="card chart-panel">
    <div class="panel-title">Mean flow by weekday</div>
    <div class="panel-subtitle">${countScalingLabel(countScaling)} · direction-resolved average</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 320,
    marginLeft: 54,
    x: {domain: weekdayOrder, label: null, tickFormat: (day) => day.slice(0, 3)},
    y: {label: countScaling === "raw" ? "detections / min" : "reference-scaled vehicles / min", grid: true},
    color: {
      domain: ["left", "right"],
      range: [colors.left, colors.right],
      legend: true
    },
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.barY(weekdayMeans, {
        x: "weekday",
        y: "mean_flow",
        fill: "direction",
        fx: "direction",
        tip: true
      })
    ]
  })
)
```
  </div>
</div>

## Directional signature

```js
html`<div class="grid grid-cols-2">
  <div class="metric-card blue">
    <div class="metric-label"><span class="swatch left"></span>Left / Oakland-bound</div>
    <div class="metric-value">${fixed(+summary.left_mean_flow * countScaleFactor("left", countScaling), 1)}</div>
    <div class="metric-detail">${countScalingLabel(countScaling)} per minute · broad midday/afternoon peak</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label"><span class="swatch right"></span>Right / SF-bound</div>
    <div class="metric-value">${fixed(+summary.right_mean_flow * countScaleFactor("right", countScaling), 1)}</div>
    <div class="metric-detail">${countScalingLabel(countScaling)} per minute · strong weekday morning peak</div>
  </div>
</div>`
```

<div class="note warning">
These are outputs from a motion-tracking algorithm, not official bridge counts.
No labeled validation set exists, so false-positive and false-negative rates
are unknown. Public Caltrans data is nearly directionally balanced while this
camera reports roughly 65% SF-bound / 35% Oakland-bound, demonstrating strong
direction-dependent measurement bias. See <a href="./validation">External
Validation</a>. Relative speed is recorded in pixels per second and is not
converted to mph.
</div>

<div class="note danger">
The Bay Lights commissioning and March 20, 2026 public relighting created a
major nighttime measurement discontinuity. Animated LEDs are detected as
motion, producing substantially noisier nighttime counts after relighting.
Use the period controls in Explorer, Typical Week, and Notable Days rather than
mixing the regimes for night-sensitive comparisons.
</div>

## What to inspect next

<div class="grid grid-cols-4">
  <div class="card">
    <h3><a href="./explorer">Historical explorer →</a></h3>
    <p>Filter the complete hourly series by date and direction.</p>
  </div>
  <div class="card">
    <h3><a href="./patterns">Typical week →</a></h3>
    <p>September-style weekday profiles with percentile envelopes.</p>
  </div>
  <div class="card">
    <h3><a href="./notable">Notable days →</a></h3>
    <p>Rank complete days and inspect directional imbalance.</p>
  </div>
  <div class="card">
    <h3><a href="./validation">External validation →</a></h3>
    <p>Official counts, directional bias, and interpretation limits.</p>
  </div>
</div>

<p class="provenance">SOURCE: Prometheus query-range snapshot · STEP: 300 s · TIMEZONE: America/Los_Angeles · SNAPSHOT: archive-v3</p>
