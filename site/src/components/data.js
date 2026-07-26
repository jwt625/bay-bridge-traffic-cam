export const colors = {
  left: "#5794f2",
  right: "#ff9830",
  good: "#73bf69",
  warn: "#fade2a",
  bad: "#f2495c",
  grid: "#2b3038",
  text: "#a7a9ac",
  muted: "#7b8088"
};

export const lightingPeriods = ["all", "pre_lights", "commissioning", "illuminated"];

export const countScalingModes = ["reference_scaled", "raw"];

export const countScalingLabels = {
  reference_scaled: "Reference-scaled: Oakland ×2.45 · SF ×1.36 (default)",
  raw: "Raw algorithmic detections"
};

export const directionalReferenceMultipliers = {
  left: 2.447544,
  right: 1.356866
};

export function countScalingLabel(value) {
  return countScalingLabels[value] ?? value;
}

export function countScaleFactor(direction, mode = "reference_scaled") {
  return mode === "reference_scaled"
    ? directionalReferenceMultipliers[direction] ?? 1
    : 1;
}

export function scaleCount(value, direction, mode = "reference_scaled") {
  return value == null ? value : value * countScaleFactor(direction, mode);
}

export const lightingPeriodLabels = {
  all: "All data (mixed lighting regimes)",
  pre_lights: "Pre-lights baseline · before Feb 19",
  commissioning: "Commissioning · Feb 19–Mar 19",
  illuminated: "Illuminated era · Mar 20 onward"
};

export function lightingPeriodLabel(value) {
  return lightingPeriodLabels[value] ?? value;
}

export function summaryObject(rows) {
  return Object.fromEntries(rows.map((row) => [row.key, row.value]));
}

export function asNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function parseHourly(rows) {
  return rows.map((row) => ({
    ...row,
    hour_utc: new Date(row.hour_utc),
    hour_local: new Date(row.hour_local),
    mean_flow: +row.mean_flow,
    median_flow: +row.median_flow,
    max_flow: +row.max_flow,
    estimated_detections: +row.estimated_detections,
    sample_count: +row.sample_count,
    coverage: +row.coverage
  }));
}

export function parseDaily(rows) {
  return rows.map((row) => {
    const localDate =
      row.local_date instanceof Date
        ? row.local_date.toISOString().slice(0, 10)
        : String(row.local_date).slice(0, 10);
    return {
      ...row,
      local_date: localDate,
      date: new Date(`${localDate}T12:00:00Z`),
      mean_flow: +row.mean_flow,
      median_flow: +row.median_flow,
      max_flow: +row.max_flow,
      sample_count: +row.sample_count,
      expected_samples: +row.expected_samples,
      coverage: +row.coverage,
      flow_integral_detections: +row.flow_integral_detections,
      counter_positive_increments: +row.counter_positive_increments,
      counter_resets: +row.counter_resets,
      complete_day: row.complete_day === true || row.complete_day === "True"
    };
  });
}

export function parseProfile(rows) {
  return rows.map((row) => ({
    ...row,
    weekday_number: +row.weekday_number,
    quarter_hour: +row.quarter_hour,
    mean: +row.mean,
    median: +row.median,
    p10: row.p10 == null ? null : +row.p10,
    p25: +row.p25,
    p75: +row.p75,
    p90: row.p90 == null ? null : +row.p90,
    sample_count: +row.sample_count
  }));
}

export function shortNumber(value, digits = 1) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: digits
  }).format(value);
}

export function fixed(value, digits = 1) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(value);
}

export function percent(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function isoDate(value) {
  return value instanceof Date
    ? value.toISOString().slice(0, 10)
    : String(value).slice(0, 10);
}

export const basePlotStyle = {
  background: "transparent",
  color: colors.text,
  fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
  fontSize: 11
};
