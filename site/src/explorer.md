---
title: Historical Explorer
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
  isoDate,
  lightingPeriodLabel,
  lightingPeriods,
  parseHourly,
  percent
} from "./components/data.js";

const hourlyRows = await FileAttachment("./data/archive-v3/hourly.csv").csv({typed: true});
const halfHourRows = await FileAttachment("./data/archive-v3/half-hour.csv").csv();
const eventRows = await FileAttachment("./data/archive-v3/lighting-events.csv").csv({typed: true});
const hourly = parseHourly(hourlyRows);
const halfHourly = halfHourRows.map((row) => {
  const local = String(row.half_hour_local);
  const localDate = local.slice(0, 10);
  const hour = Number(local.slice(11, 13));
  const minute = Number(local.slice(14, 16));
  return {
    ...row,
    date: new Date(`${localDate}T12:00:00Z`),
    half_hour: hour * 2 + (minute >= 30 ? 1 : 0),
    mean_flow: +row.mean_flow,
    sample_count: +row.sample_count,
    coverage: +row.coverage
  };
});
const lightingEvents = eventRows.map((row) => ({
  ...row,
  local_date: isoDate(row.local_date),
  date: new Date(`${isoDate(row.local_date)}T12:00:00Z`)
}));
const minDate = d3.min(hourly, (row) => row.hour_local);
const maxDate = d3.max(hourly, (row) => row.hour_local);

function createHourlyBrush(data, metric, metricLabel, fallbackDomain) {
  const control = document.createElement("div");
  control.className = "time-brush";
  const observedDomain = d3.extent(data, (row) => row.hour_local);
  const fullDomain =
    observedDomain[0] && observedDomain[1]
      ? observedDomain
      : fallbackDomain;
  control.value = fullDomain;

  if (!observedDomain[0] || !observedDomain[1]) {
    control.textContent = "No observations in the current selection.";
    return control;
  }

  const header = document.createElement("div");
  header.className = "time-brush-header";
  const readout = document.createElement("span");
  readout.className = "time-brush-readout";
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "time-brush-reset";
  reset.textContent = "Reset zoom";
  header.append(readout, reset);
  control.append(header);

  const navigatorWidth = 1100;
  const navigatorHeight = 104;
  const marginTop = 8;
  const marginRight = 14;
  const marginBottom = 24;
  const marginLeft = 52;
  const navigator = Plot.plot({
    ...basePlotStyle,
    width: navigatorWidth,
    height: navigatorHeight,
    marginTop,
    marginRight,
    marginBottom,
    marginLeft,
    x: {domain: fullDomain, label: null, ticks: 6},
    y: {axis: null, label: null},
    color: {
      domain: ["left", "right"],
      range: [colors.left, colors.right]
    },
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.lineY(data, {
        x: "hour_local",
        y: metric,
        stroke: "direction",
        strokeOpacity: 0.72,
        strokeWidth: 0.75
      })
    ]
  });
  navigator.classList.add("time-brush-navigator");
  control.append(navigator);

  const x = d3.scaleTime()
    .domain(fullDomain)
    .range([marginLeft, navigatorWidth - marginRight]);
  const formatDate = d3.timeFormat("%b %-d, %Y %H:%M");
  const updateReadout = ([start, end]) => {
    readout.textContent =
      `${formatDate(start)} — ${formatDate(end)} · ${metricLabel}`;
  };
  updateReadout(fullDomain);

  let initializing = true;
  const brush = d3.brushX()
    .extent([
      [marginLeft, marginTop],
      [navigatorWidth - marginRight, navigatorHeight - marginBottom]
    ])
    .on("end", (event) => {
      if (initializing) return;
      const selection = event.selection;
      if (!selection) {
        brushLayer.call(brush.move, x.range());
        return;
      }
      const window = selection.map(x.invert);
      if (+window[1] <= +window[0]) return;
      control.value = window;
      updateReadout(window);
      control.dispatchEvent(new Event("input", {bubbles: true}));
    });
  const brushLayer = d3.select(navigator)
    .append("g")
    .attr("class", "hourly-brush")
    .call(brush);
  brushLayer.call(brush.move, x.range());
  initializing = false;

  reset.addEventListener("click", () => {
    brushLayer.call(brush.move, x.range());
  });
  navigator.addEventListener("dblclick", (event) => {
    event.preventDefault();
    brushLayer.call(brush.move, x.range());
  });
  return control;
}
```

<div class="page-kicker">Archive explorer / hourly resolution</div>

# Historical explorer

<p class="lede">Inspect hourly traffic flow across the full retained period. The site uses a compact five-minute-derived snapshot; exact raw scrape samples will be published separately after the immutable TSDB copy is verified.</p>

```js
const startDate = view(Inputs.date({label: "Start date", value: minDate}));
const endDate = view(Inputs.date({label: "End date", value: maxDate}));
const direction = view(
  Inputs.select(["both", "left", "right"], {
    label: "Direction",
    value: "both",
    format: (value) =>
      value === "both" ? "Both directions" : value === "left" ? "Left / Oakland-bound" : "Right / SF-bound"
  })
);
const metric = view(
  Inputs.select(["mean_flow", "estimated_detections", "coverage"], {
    label: "Metric",
    value: "mean_flow",
    format: (value) =>
      ({
        mean_flow: "Mean detections / min",
        estimated_detections: "Estimated hourly detections",
        coverage: "Sample coverage"
      })[value]
  })
);
const countScaling = view(
  Inputs.select(countScalingModes, {
    label: "Traffic-count display",
    value: "reference_scaled",
    format: countScalingLabel
  })
);
const lightingPeriod = view(
  Inputs.select(lightingPeriods, {
    label: "Lighting regime",
    value: "all",
    format: lightingPeriodLabel
  })
);
```

```js
const startBoundary = new Date(startDate);
startBoundary.setHours(0, 0, 0, 0);
const endBoundary = new Date(endDate);
endBoundary.setHours(23, 59, 59, 999);

const displayHourly = hourly.map((row) => {
  const factor = countScaleFactor(row.direction, countScaling);
  return {
    ...row,
    mean_flow: row.mean_flow * factor,
    median_flow: row.median_flow * factor,
    max_flow: row.max_flow * factor,
    estimated_detections: row.estimated_detections * factor
  };
});

const filtered = displayHourly.filter(
  (row) =>
    row.hour_local >= startBoundary &&
    row.hour_local <= endBoundary &&
    (lightingPeriod === "all" || row.lighting_period === lightingPeriod) &&
    (direction === "both" || row.direction === direction)
);

const metricLabel = {
  mean_flow: countScaling === "raw" ? "detections / min" : "reference-scaled vehicles / min",
  estimated_detections: countScaling === "raw" ? "estimated detections / hour" : "reference-scaled vehicles / hour",
  coverage: "sample coverage"
}[metric];

const meanCoverage = d3.mean(filtered, (row) => row.coverage);
const maxValue = d3.max(filtered, (row) => row[metric]);
const visibleLightingEvents = lightingEvents.filter(
  (row) =>
    row.date >= startBoundary &&
    row.date <= endBoundary &&
    (
      lightingPeriod === "all" ||
      (lightingPeriod === "commissioning" && row.date < new Date("2026-03-20T12:00:00Z")) ||
      (lightingPeriod === "illuminated" && row.date >= new Date("2026-03-20T12:00:00Z"))
    )
);
```

```js
html`<div class="grid grid-cols-3">
  <div class="metric-card green">
    <div class="metric-label">Selected rows</div>
    <div class="metric-value">${filtered.length.toLocaleString()}</div>
    <div class="metric-detail">hour × direction observations</div>
  </div>
  <div class="metric-card blue">
    <div class="metric-label">Mean coverage</div>
    <div class="metric-value">${percent(meanCoverage || 0, 1)}</div>
    <div class="metric-detail">within selected hourly observations</div>
  </div>
  <div class="metric-card orange">
    <div class="metric-label">Maximum</div>
    <div class="metric-value">${metric === "coverage" ? percent(maxValue || 0, 0) : (maxValue || 0).toFixed(1)}</div>
    <div class="metric-detail">${metricLabel}</div>
  </div>
</div>`
```

<div class="card chart-panel">
  <div class="panel-title">Hourly time series</div>
  <div class="panel-subtitle">Drag across the navigator to zoom · drag the selected window to pan · resize either handle · double-click or reset to show all · hover the main chart for exact values</div>

```js
const zoomWindow = view(
  createHourlyBrush(
    filtered,
    metric,
    metricLabel,
    [startBoundary, endBoundary]
  )
);
```

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 460,
    marginLeft: 66,
    x: {label: null, domain: zoomWindow},
    y: {
      label: metricLabel,
      grid: true,
      domain: metric === "coverage" ? [0, 1] : [0, maxValue]
    },
    color: {
      domain: ["left", "right"],
      range: [colors.left, colors.right],
      legend: true
    },
    marks: [
      Plot.ruleY([0], {stroke: colors.grid}),
      Plot.ruleX(visibleLightingEvents, {
        x: "date",
        stroke: (row) => row.event_type === "derived" ? colors.warn : colors.bad,
        strokeDasharray: "5,4",
        tip: true
      }),
      Plot.lineY(filtered, {
        x: "hour_local",
        y: metric,
        stroke: "direction",
        strokeWidth: 1,
        tip: true
      })
    ]
  })
)
```
</div>

```js
lightingPeriod === "pre_lights"
  ? html`<div class="note">Pre-lights excludes the documented commissioning interval and the illuminated era.</div>`
  : html`<div class="note danger">Animated Bay Lights contaminate nighttime motion detection during commissioning and after public relighting. Treat nighttime count and speed changes as detector artifacts unless independently validated.</div>`
```

## Day × half-hour activity

```js
const heatDirection = view(
  Inputs.radio(["right", "left"], {
    label: "Heatmap direction",
    value: "right",
    format: (value) => (value === "left" ? "Left / Oakland-bound" : "Right / SF-bound")
  })
);
```

```js
const heatData = halfHourly
  .filter(
    (row) =>
      row.date >= startBoundary &&
      row.date <= endBoundary &&
      (lightingPeriod === "all" || row.lighting_period === lightingPeriod) &&
      row.direction === heatDirection
  )
  .map((row) => ({
    ...row,
    mean_flow:
      row.mean_flow * countScaleFactor(row.direction, countScaling)
  }));

const heatValues = heatData
  .map((row) => row.mean_flow)
  .filter(Number.isFinite)
  .sort(d3.ascending);
const heatThresholds = [0.2, 0.4, 0.6, 0.8].map(
  (quantile) => d3.quantileSorted(heatValues, quantile) ?? 0
);
const heatPalette = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"];
for (const row of heatData) {
  row.intensity = d3.bisectRight(heatThresholds, row.mean_flow);
}
```

<div class="card chart-panel">
  <div class="panel-title">Day × half-hour activity</div>
  <div class="panel-subtitle">${countScalingLabel(countScaling)} · six five-minute samples per complete bin</div>

```js
resize((width) =>
  Plot.plot({
    ...basePlotStyle,
    width,
    height: 520,
    marginLeft: 42,
    x: {
      type: "band",
      label: null,
      tickSize: 0,
      tickFormat: (date, index) =>
        index === 0 || date.getDate() === 1 ? d3.timeFormat("%b")(date) : ""
    },
    y: {
      label: "half-hour",
      domain: d3.range(48),
      reverse: true,
      tickSize: 0,
      tickFormat: (slot) =>
        slot % 6 === 0
          ? `${String(Math.floor(slot / 2)).padStart(2, "0")}:00`
          : ""
    },
    color: {
      type: "ordinal",
      domain: [0, 1, 2, 3, 4],
      range: heatPalette
    },
    marks: [
      Plot.cell(heatData, {
        x: "date",
        y: "half_hour",
        fill: "intensity",
        inset: 0.15,
        stroke: "#0d1117",
        strokeWidth: 0.15,
        tip: true
      })
    ]
  })
)
```

```js
html`<div class="heatmap-legend" aria-label="Heatmap intensity legend">
  <span>Less</span>
  ${heatPalette.map((color, index) => html`<span
    class="heatmap-swatch"
    style=${`--heat-color: ${color}`}
    title=${`Quintile ${index + 1}`}
  ></span>`)}
  <span>More</span>
</div>`
```
</div>

<div class="note">
GitHub-style color buckets are relative quintiles within the active heatmap
selection; they show temporal structure, not a fixed absolute scale. Each cell
is a real 30-minute mean derived from up to six five-minute samples. Hover for
the underlying mean rate and coverage. Incomplete bins remain visible;
complete-day analyses use a stricter ≥95% daily threshold.
</div>
