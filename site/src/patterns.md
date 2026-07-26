---
title: Typical Week
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
  parseProfile
} from "./components/data.js";

const profileRows = await FileAttachment("./data/archive-v3/weekday-profile.csv").csv({typed: true});
const speedRows = await FileAttachment("./data/archive-v3/speed-profile.csv").csv({typed: true});
const profile = parseProfile(profileRows);
const speedProfile = parseProfile(speedRows);
const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const formatMinuteOfDay = (value) => {
  const minute = Math.max(0, Math.min(1439, Math.round(Number(value))));
  const hour = Math.floor(minute / 60);
  return `${String(hour).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
};
const profileTip = {format: {x: formatMinuteOfDay}};
```

<div class="page-kicker">Pattern analysis / complete days only</div>

# Typical week

<p class="lede">Day-of-week profiles reproduce and extend the September 2025 analysis over the complete collection period. Each line is a 15-minute median; the shaded band spans the 25th–75th percentiles.</p>

```js
const selectedDay = view(Inputs.select(weekdays, {label: "Weekday", value: "Monday"}));
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
const periodProfile = profile
  .filter((row) => row.analysis_period === lightingPeriod)
  .map((row) => {
    const factor = countScaleFactor(row.direction, countScaling);
    return {
      ...row,
      mean: row.mean * factor,
      median: row.median * factor,
      p10: row.p10 == null ? null : row.p10 * factor,
      p25: row.p25 * factor,
      p75: row.p75 * factor,
      p90: row.p90 == null ? null : row.p90 * factor
    };
  });
const selectedProfile = periodProfile.filter((row) => row.weekday === selectedDay);
const dayCounts = d3.rollup(selectedProfile, (rows) => d3.max(rows, (row) => row.sample_count), (row) => row.direction);
```

```js
html`<div class="grid grid-cols-2">
  <div class="metric-card blue">
    <div class="metric-label">Left / Oakland-bound profile samples</div>
    <div class="metric-value">${(dayCounts.get("left") || 0).toLocaleString()}</div>
    <div class="metric-detail">five-minute observations contributing to peak bin</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Right / SF-bound profile samples</div>
    <div class="metric-value">${(dayCounts.get("right") || 0).toLocaleString()}</div>
    <div class="metric-detail">five-minute observations contributing to peak bin</div>
  </div>
</div>`
```

<div class="card chart-panel">
  <div class="panel-title">${selectedDay} flow profile</div>
  <div class="panel-subtitle">${countScalingLabel(countScaling)} · median and IQR · 15-minute bins</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 440,
    marginLeft: 58,
    x: {
      label: "local time",
      domain: [0, 1440],
      ticks: 12,
      tickFormat: (minute) => `${String(Math.floor(minute / 60)).padStart(2, "0")}:00`
    },
    y: {label: countScaling === "raw" ? "detections / min" : "reference-scaled vehicles / min", grid: true},
    color: {
      domain: ["left", "right"],
      range: [colors.left, colors.right],
      legend: true
    },
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.areaY(selectedProfile, {
        x: "quarter_hour",
        y1: "p25",
        y2: "p75",
        fill: "direction",
        fillOpacity: 0.14
      }),
      Plot.lineY(selectedProfile, {
        x: "quarter_hour",
        y: "median",
        stroke: "direction",
        strokeWidth: 2,
        tip: profileTip
      }),
      Plot.lineY(selectedProfile, {
        x: "quarter_hour",
        y: "mean",
        stroke: "direction",
        strokeOpacity: 0.45,
        strokeDasharray: "4,3"
      })
    ]
  })
)
```
</div>

## All weekdays

<div class="card chart-panel">
  <div class="panel-title">Weekly comparison</div>
  <div class="panel-subtitle">${countScalingLabel(countScaling)} · both directions overlaid · solid median · shaded IQR · dashed mean · same y-scale across panels</div>
  <div class="weekly-direction-legend">
    <span><i class="swatch left"></i>Left / Oakland-bound</span>
    <span><i class="swatch right"></i>Right / SF-bound</span>
  </div>

```js
const weeklyYMax = d3.max(periodProfile, (row) => row.p75) || 1;
```

```js
resize((width) => {
  const columns = width >= 900 ? 3 : width >= 600 ? 2 : 1;
  const gap = 12;
  const panelWidth = Math.floor((width - gap * (columns - 1)) / columns);
  const panels = weekdays.map((weekday) => {
    const rows = periodProfile.filter((row) => row.weekday === weekday);
    const plot = Plot.plot({
      ...basePlotStyle,
      width: panelWidth,
      height: 300,
      marginTop: 10,
      marginRight: 12,
      marginBottom: 34,
      marginLeft: 46,
      x: {
        label: null,
        domain: [0, 1440],
        ticks: 5,
        tickFormat: (minute) => `${Math.floor(minute / 60)}h`
      },
      y: {
        label: null,
        domain: [0, weeklyYMax],
        grid: true,
        nice: true
      },
      color: {
        domain: ["left", "right"],
        range: [colors.left, colors.right]
      },
      marks: [
        Plot.ruleY([0], {stroke: colors.grid}),
        Plot.areaY(rows, {
          x: "quarter_hour",
          y1: "p25",
          y2: "p75",
          fill: "direction",
          fillOpacity: 0.15
        }),
        Plot.lineY(rows, {
          x: "quarter_hour",
          y: "median",
          stroke: "direction",
          strokeWidth: 1.8,
          tip: profileTip
        }),
        Plot.lineY(rows, {
          x: "quarter_hour",
          y: "mean",
          stroke: "direction",
          strokeOpacity: 0.44,
          strokeDasharray: "4,3"
        })
      ]
    });
    return html`<section class="weekly-small-panel">
      <div class="weekly-small-title">${weekday}</div>
      ${plot}
    </section>`;
  });
  return html`<div
    class="weekly-panel-grid"
    style=${`--weekly-columns: ${columns}; --weekly-gap: ${gap}px`}
  >${panels}</div>`;
})
```
</div>

## Relative pixel speed

```js
const selectedSpeed = speedProfile.filter(
  (row) => row.analysis_period === lightingPeriod && row.weekday === selectedDay
);
```

<div class="card chart-panel">
  <div class="panel-title">${selectedDay} relative speed profile</div>
  <div class="panel-subtitle">15-minute rolling detector metric · pixels per second, not physical speed</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 360,
    marginLeft: 58,
    x: {
      label: "local time",
      domain: [0, 1440],
      ticks: 12,
      tickFormat: (minute) => `${String(Math.floor(minute / 60)).padStart(2, "0")}:00`
    },
    y: {label: "pixels / second", grid: true},
    color: {
      domain: ["left", "right"],
      range: [colors.left, colors.right],
      legend: true
    },
    marks: [
      Plot.areaY(selectedSpeed, {
        x: "quarter_hour",
        y1: "p25",
        y2: "p75",
        fill: "direction",
        fillOpacity: 0.12
      }),
      Plot.lineY(selectedSpeed, {
        x: "quarter_hour",
        y: "median",
        stroke: "direction",
        strokeWidth: 1.8,
        tip: profileTip
      })
    ]
  })
)
```
</div>

<div class="note warning">
Profile statistics include only direction-days with at least 95% expected five-minute samples. This avoids treating system downtime as low traffic. Percentile envelopes represent observed detector variability, not measurement confidence intervals.
</div>

```js
lightingPeriod === "pre_lights"
  ? html`<div class="note">Pre-lights is the cleanest baseline for nighttime detector behavior.</div>`
  : html`<div class="note danger">This selection includes LED commissioning or operation. Nighttime motion counts and pixel-speed statistics are optically contaminated and should not be interpreted as comparable traffic measurements.</div>`
```
