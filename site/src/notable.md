---
title: Notable Days
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
  lightingPeriodLabel,
  lightingPeriods,
  parseDaily,
  shortNumber
} from "./components/data.js";

const dailyRows = await FileAttachment("./data/archive-v3/daily.csv").csv({typed: true});
const daily = parseDaily(dailyRows).filter((row) => row.complete_day);
```

```js
const lightingPeriod = view(
  Inputs.select(lightingPeriods, {
    label: "Lighting regime",
    value: "pre_lights",
    format: lightingPeriodLabel
  })
);
const countScaling = view(
  Inputs.select(countScalingModes, {
    label: "Traffic-count display",
    value: "reference_scaled",
    format: countScalingLabel
  })
);
```

```js
const selectedDaily = daily.filter(
  (row) => lightingPeriod === "all" || row.lighting_period === lightingPeriod
);
const byDate = d3
  .rollups(
    selectedDaily,
    (rows) => {
      const directions = Object.fromEntries(rows.map((row) => [row.direction, row]));
      const left =
        (directions.left?.counter_positive_increments ?? 0) *
        countScaleFactor("left", countScaling);
      const right =
        (directions.right?.counter_positive_increments ?? 0) *
        countScaleFactor("right", countScaling);
      return {
        date: rows[0].date,
        weekday: rows[0].weekday,
        left,
        right,
        total: left + right,
        imbalance: (right - left) / Math.max(left + right, 1),
        coverage: d3.min(rows, (row) => row.coverage)
      };
    },
    (row) => row.local_date
  )
  .map(([local_date, values]) => ({local_date, ...values}));

const rankedHigh = d3.sort(byDate, (a, b) => d3.descending(a.total, b.total)).slice(0, 10);
const rankedLow = d3.sort(byDate, (a, b) => d3.ascending(a.total, b.total)).slice(0, 10);
const directional = d3.sort(
  byDate,
  (a, b) => d3.descending(Math.abs(a.imbalance), Math.abs(b.imbalance))
).slice(0, 20);
```

<div class="page-kicker">Ranked complete days / archive-v3</div>

# Notable days

<p class="lede">A compact anomaly review of complete calendar days. Rankings use reset-aware positive counter increments and exclude days below 95% coverage in either direction.</p>

<div class="note warning">
Rankings identify unusual detector output, not necessarily unusual real-world traffic. Weather, lighting, camera motion, occlusion, and tracking behavior can all change the count.
</div>

```js
lightingPeriod === "pre_lights"
  ? html`<div class="note">Defaulting to the pre-lights baseline so LED-driven night motion does not dominate the rankings.</div>`
  : html`<div class="note danger">This ranking includes optically contaminated nighttime observations from Bay Lights commissioning or operation.</div>`
```

<div class="grid grid-cols-2">
  <div class="card chart-panel">
    <div class="panel-title">Highest-count complete days</div>
    <div class="panel-subtitle">${countScalingLabel(countScaling)} · both directions combined</div>

```js
Plot.plot({
  ...basePlotStyle,
  height: 350,
  marginLeft: 92,
  x: {label: countScaling === "raw" ? "algorithmic detections" : "reference-scaled vehicles", grid: true, tickFormat: "s"},
  y: {label: null, domain: rankedHigh.map((row) => row.local_date)},
  marks: [
    Plot.ruleX([0], {stroke: colors.grid}),
    Plot.barX(rankedHigh, {
      x: "total",
      y: "local_date",
      fill: colors.left,
      sort: {y: "-x"},
      tip: true
    })
  ]
})
```
  </div>

  <div class="card chart-panel">
    <div class="panel-title">Lowest-count complete days</div>
    <div class="panel-subtitle">${countScalingLabel(countScaling)} · low-volume candidates</div>

```js
Plot.plot({
  ...basePlotStyle,
  height: 350,
  marginLeft: 92,
  x: {label: countScaling === "raw" ? "algorithmic detections" : "reference-scaled vehicles", grid: true, tickFormat: "s"},
  y: {label: null, domain: rankedLow.map((row) => row.local_date)},
  marks: [
    Plot.ruleX([0], {stroke: colors.grid}),
    Plot.barX(rankedLow, {
      x: "total",
      y: "local_date",
      fill: colors.right,
      sort: {y: "x"},
      tip: true
    })
  ]
})
```
  </div>
</div>

## Directional imbalance

<div class="card chart-panel">
  <div class="panel-title">Daily right versus left detections</div>
  <div class="panel-subtitle">Diagonal indicates equal directional counts · highlighted points are the 20 most imbalanced complete days</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 440,
    marginLeft: 64,
    x: {label: `Left / Oakland-bound ${countScaling === "raw" ? "detections" : "reference-scaled vehicles"}`, grid: true, tickFormat: "s"},
    y: {label: `Right / SF-bound ${countScaling === "raw" ? "detections" : "reference-scaled vehicles"}`, grid: true, tickFormat: "s"},
    color: {
      type: "diverging",
      domain: [-1, 1],
      range: [colors.left, colors.text, colors.right],
      legend: true,
      label: "Directional imbalance"
    },
    marks: [
      Plot.dot(byDate, {
        x: "left",
        y: "right",
        fill: "imbalance",
        r: 3.4,
        fillOpacity: 0.72,
        tip: true
      }),
      Plot.dot(directional, {
        x: "left",
        y: "right",
        stroke: colors.warn,
        strokeWidth: 1.5,
        r: 5,
        tip: true
      })
    ]
  })
)
```
</div>

```js
html`<div class="grid grid-cols-3">
  <div class="metric-card blue">
    <div class="metric-label">Highest complete day</div>
    <div class="metric-value">${shortNumber(rankedHigh[0].total, 1)}</div>
    <div class="metric-detail">${rankedHigh[0].local_date} · ${rankedHigh[0].weekday}</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Lowest complete day</div>
    <div class="metric-value">${shortNumber(rankedLow[0].total, 1)}</div>
    <div class="metric-detail">${rankedLow[0].local_date} · ${rankedLow[0].weekday}</div>
  </div>
  <div class="metric-card yellow">
    <div class="metric-label">Ranked days</div>
    <div class="metric-value">${byDate.length}</div>
    <div class="metric-detail">complete two-direction calendar days</div>
  </div>
</div>`
```

<p class="provenance">FILTER: ≥95% five-minute coverage per direction · DISPLAY: ${countScalingLabel(countScaling)} · NO EVENT CAUSALITY ASSIGNED</p>
