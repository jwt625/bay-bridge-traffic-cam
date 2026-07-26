---
title: External Validation
---

```js
import * as Plot from "npm:@observablehq/plot";
import {basePlotStyle, colors, percent, shortNumber} from "./components/data.js";

const directionRows = await FileAttachment("./data/validation-v1/direction-summary.csv").csv({typed: true});
const monthlyRows = await FileAttachment("./data/validation-v1/westbound-monthly-match.csv").csv({typed: true});
const peakRows = await FileAttachment("./data/validation-v1/official-peak-hour-reference.csv").csv({typed: true});

const directions = directionRows.map((row) => ({
  ...row,
  official_reference_daily: +row.official_reference_daily,
  detector_daily_mean: +row.detector_daily_mean,
  detector_direction_share: +row.detector_direction_share,
  official_direction_share: +row.official_direction_share,
  indicative_multiplier_mean: +row.indicative_multiplier_mean
}));
const monthly = monthlyRows.map((row) => ({
  ...row,
  date: new Date(`${String(row.month).slice(0, 10)}T12:00:00Z`),
  official_westbound_daily_mean: +row.official_westbound_daily_mean,
  detector_daily_mean: +row.detector_daily_mean,
  indicative_multiplier: +row.indicative_multiplier
}));
const preLightsMonthly = monthly.filter((row) => row.lighting_period === "pre_lights");
const left = directions.find((row) => row.direction === "left");
const right = directions.find((row) => row.direction === "right");
const officialTotal = directions.reduce((sum, row) => sum + row.official_reference_daily, 0);
const peak = peakRows[0];
```

<div class="page-kicker">Third-party cross-check / validation-v1</div>

# External validation

<p class="lede">The detector has no manually labeled test set, so its precision, recall, false-positive rate, and false-negative rate are unknown. Public bridge counts expose a large, direction-dependent undercount; they do not make the camera measurements ground truth.</p>

<div class="note danger">
Analysis pages default to a reference-scaled estimate using the two directional
ratios below and provide a Raw detector option. The scaled view is an
approximate presentation layer—not ground truth or a calibrated correction.
These ratios average across different years, locations, sampling definitions,
weather, congestion, and camera conditions.
</div>

```js
html`<div class="grid grid-cols-4">
  <div class="metric-card green">
    <div class="metric-label">Official two-way AADT</div>
    <div class="metric-value">${shortNumber(officialTotal, 0)}</div>
    <div class="metric-detail">2024 west span reference near Treasure Island</div>
  </div>
  <div class="metric-card blue">
    <div class="metric-label">Official directional split</div>
    <div class="metric-value">${percent(left.official_direction_share, 1)} / ${percent(right.official_direction_share, 1)}</div>
    <div class="metric-detail">Oakland-bound / SF-bound · nearly balanced</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Camera directional split</div>
    <div class="metric-value">${percent(left.detector_direction_share, 1)} / ${percent(right.detector_direction_share, 1)}</div>
    <div class="metric-detail">complete pre-lights days · strongly biased</div>
  </div>
  <div class="metric-card yellow">
    <div class="metric-label">Known labeled detections</div>
    <div class="metric-value">0</div>
    <div class="metric-detail">no retained video corpus or manual audit set</div>
  </div>
</div>`
```

## Direction-specific reference ratios

```js
html`<div class="grid grid-cols-2">
  ${directions.map((row) => html`<div class="metric-card ${row.direction === "left" ? "blue" : "orange"}">
    <div class="metric-label">${row.destination}</div>
    <div class="metric-value">${row.indicative_multiplier_mean.toFixed(2)}×</div>
    <div class="metric-detail">
      official ${shortNumber(row.official_reference_daily, 0)}/day ÷ camera
      ${shortNumber(row.detector_daily_mean, 0)}/complete day
    </div>
  </div>`)}
</div>`
```

The difference is too large to use one global scale factor. A rough
pre-lights, full-day comparison gives **2.45× for Oakland-bound** and **1.36×
for SF-bound**. Likely mechanisms include deck visibility, perspective, lane
occlusion, tracker merging, speed/congestion dependence, and different
projected motion on the upper and lower decks. Without labeled frames, their
individual contributions cannot be separated.

The camera’s apparent two-to-one SF-bound/Oakland-bound volume ratio is
therefore contradicted by the official near-even split. It is principally a
measurement response, not a traffic conclusion.

## Monthly westbound cross-check

MTC publishes monthly toll-bridge totals for the one-way toll direction. For
the Bay Bridge this is westbound/SF-bound, so it provides a useful monthly
comparison with the camera’s `right` series. Across the six complete
pre-lights months below, the ratio ranges from approximately 1.23× to 1.43×.
That stability is encouraging for relative trend analysis, but it still does
not establish accuracy at hourly resolution.

<div class="card chart-panel">
  <div class="panel-title">SF-bound daily mean: public count vs camera detections</div>
  <div class="panel-subtitle">Pre-lights months only · MTC monthly toll count divided by calendar days</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 340,
    marginLeft: 62,
    x: {label: null},
    y: {label: "daily mean", grid: true, tickFormat: "s"},
    color: {
      domain: ["MTC official", "Camera detector"],
      range: [colors.good, colors.right],
      legend: true
    },
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.lineY(preLightsMonthly, {
        x: "date",
        y: "official_westbound_daily_mean",
        stroke: colors.good,
        strokeWidth: 2,
        tip: true
      }),
      Plot.dot(preLightsMonthly, {
        x: "date",
        y: "official_westbound_daily_mean",
        fill: colors.good,
        r: 3
      }),
      Plot.lineY(preLightsMonthly, {
        x: "date",
        y: "detector_daily_mean",
        stroke: colors.right,
        strokeWidth: 2,
        tip: true
      }),
      Plot.dot(preLightsMonthly, {
        x: "date",
        y: "detector_daily_mean",
        fill: colors.right,
        r: 3
      })
    ]
  })
)
```
</div>

## Which conclusions survive

| Site observation | External check | Publication boundary |
| --- | --- | --- |
| SF-bound has a strong weekday morning peak | Qualitatively corroborated: Caltrans’ 2024 toll-plaza record identifies westbound as the AM peak direction | The camera’s exact peak hour is not externally validated |
| Oakland-bound has a broad afternoon peak | Qualitatively corroborated: Caltrans identifies eastbound as the PM peak direction, with a 2 PM peak-hour record | Do not generalize the exact camera profile to every day |
| Camera reports about twice as many SF-bound detections | Contradicted as a traffic split: Caltrans AADT is approximately 51% SF-bound / 49% Oakland-bound | Interpret the ratio as direction-dependent detector bias |
| Sunday is quieter in the camera series | Plausible but not independently checked with a current day-of-week source | Report only as an internal detector observation |
| Post-relighting nighttime values are noisy | Strongly supported by the detector’s own discontinuity and known Bay Lights timing | Treat as optical contamination, not a traffic surge |

For context, the Caltrans peak-hour reference used here records westbound
${(+peak.AM_WAY_PHV).toLocaleString("en-US")} vehicles at ${+peak.AM_HOUR}:00
for its AM record and eastbound ${(+peak.PM_WAY_PHV).toLocaleString("en-US")}
vehicles at ${+peak.PM_HOUR}:00 for its PM record. These are reference records,
not a simultaneous directional survey or a calibration set.

## Public sources

- [MTC Monthly Transportation Statistics](https://mtc.ca.gov/tools-resources/data-tools/monthly-transportation-statistics) — Bay Bridge monthly one-way toll-direction totals.
- [MTC monthly statistics workbook](https://mtc.ca.gov/sites/default/files/documents/2026-07/Monthly-Transportation-Statistics-07-11-2026.xlsx?cb=dfd1a873) — machine-readable monthly values used in `validation-v1`.
- [Caltrans Traffic Census Program](https://dot.ca.gov/programs/traffic-operations/census) — definitions and access to annual traffic volumes.
- [Caltrans 2024 AADT workbook](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/2024/2024-traffic-volumes-ca-a11y.xlsx) — directional west-span reference at Treasure Island.
- [Caltrans 2024 peak-hour workbook](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/2024/2024-ca-peak-hours-a11y.xlsx) — AM/PM peak directions at the toll plaza.

<p class="provenance">DETECTOR BASELINE: 191 COMPLETE PRE-LIGHTS DAYS · PUBLIC REFERENCES: MTC 2025–2026 / CALTRANS 2024 · SNAPSHOT: validation-v1</p>
