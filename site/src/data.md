---
title: Data
---

```js
const manifest = await FileAttachment("./data/archive-v3/manifest.csv").csv({typed: true});
const summaryFile = FileAttachment("./data/archive-v3/summary.csv");
const hourlyFile = FileAttachment("./data/archive-v3/hourly.csv");
const halfHourFile = FileAttachment("./data/archive-v3/half-hour.csv");
const dailyFile = FileAttachment("./data/archive-v3/daily.csv");
const weekdayFile = FileAttachment("./data/archive-v3/weekday-profile.csv");
const speedFile = FileAttachment("./data/archive-v3/speed-profile.csv");
const gapsFile = FileAttachment("./data/archive-v3/coverage-gaps.csv");
const resetsFile = FileAttachment("./data/archive-v3/counter-resets.csv");
const monthlyFile = FileAttachment("./data/archive-v3/monthly.csv");
const nightNoiseFile = FileAttachment("./data/archive-v3/night-noise.csv");
const lightingImpactFile = FileAttachment("./data/archive-v3/lighting-impact-summary.csv");
const lightingEventsFile = FileAttachment("./data/archive-v3/lighting-events.csv");
const provenanceFile = FileAttachment("./data/archive-v3/provenance.json");
const validationManifest = await FileAttachment("./data/validation-v1/manifest.csv").csv({typed: true});
const directionValidationFile = FileAttachment("./data/validation-v1/direction-summary.csv");
const monthlyValidationFile = FileAttachment("./data/validation-v1/westbound-monthly-match.csv");
const peakValidationFile = FileAttachment("./data/validation-v1/official-peak-hour-reference.csv");
const validationProvenanceFile = FileAttachment("./data/validation-v1/provenance.json");
```

<div class="page-kicker">Files / provenance / open-data status</div>

# Data

<p class="lede">The site is backed by an immutable versioned analytical snapshot. The complete 108,644,312-sample Parquet archive is published on <a href="https://huggingface.co/datasets/jwt625/bay-bridge-traffic-cam">Hugging Face</a>; verified native Prometheus and Grafana copies remain private preservation artifacts.</p>

<div class="status-line">
  <span class="status-item">Derived snapshot available</span>
  <span class="status-item">Checksums available</span>
  <span class="status-item">Source volumes preserved</span>
  <span class="status-item">MIT / CC BY 4.0</span>
  <span class="status-item">Exact raw release published</span>
</div>

## Derived snapshot v3

```js
Inputs.table(manifest, {
  columns: ["path", "bytes", "sha256"],
  header: {path: "File", bytes: "Bytes", sha256: "SHA-256"},
  format: {
    bytes: (value) => value.toLocaleString("en-US"),
    sha256: (value) => `${value.slice(0, 16)}…`
  },
  width: {path: 250, bytes: 110, sha256: 210}
})
```

### Download files

```js
const downloads = [
  ["summary.csv", summaryFile],
  ["hourly.csv", hourlyFile],
  ["half-hour.csv", halfHourFile],
  ["daily.csv", dailyFile],
  ["weekday-profile.csv", weekdayFile],
  ["speed-profile.csv", speedFile],
  ["monthly.csv", monthlyFile],
  ["night-noise.csv", nightNoiseFile],
  ["lighting-impact-summary.csv", lightingImpactFile],
  ["lighting-events.csv", lightingEventsFile],
  ["coverage-gaps.csv", gapsFile],
  ["counter-resets.csv", resetsFile],
  ["provenance.json", provenanceFile]
];
```

```js
html`<div class="grid grid-cols-3">
  ${downloads.map(([name, file]) => html`<div class="card">
    <div class="metric-label">${name}</div>
    <p><a href=${file.href} download>Download file →</a></p>
  </div>`)}
</div>`
```

## Exact-data release

<div class="card">
  <div class="metric-label">PUBLIC DATASET / CC BY 4.0</div>
  <p><a href="https://huggingface.co/datasets/jwt625/bay-bridge-traffic-cam">Browse exact Parquet and derived tables on Hugging Face →</a></p>
  <p class="muted">108,644,312 exact samples · 94 metric/month Parquet shards · 616,522,063-byte checksummed package</p>
</div>

The public dataset package contains:

```text
raw/          exact sample timestamps, values, and original labels
derived/      reconciled five-minute through daily analysis products
validation/   third-party comparison tables and provenance
*.json/*.csv  schemas, export provenance, and SHA-256 manifests
```

The native Prometheus TSDB and Grafana database remain private: those operational
formats can contain credentials, users, or unrelated service metadata. Public
raw Parquet preserves the eight application metric families, exact millisecond
timestamps, values, every original label, and a `source_series` field that
distinguishes direct from historically imported series.

Licenses:

- Code: MIT
- Published data: CC BY 4.0

Both the complete Git history and the publication candidate tree passed a
Gitleaks scan. The ignored live Prometheus configuration is neither tracked nor
included in the release.

## Example analysis

```python
import pandas as pd

daily = pd.read_csv("daily.csv", parse_dates=["local_date"])
complete = daily[
    daily["complete_day"]
    & (daily["lighting_period"] == "pre_lights")
]

weekday = (
    complete.groupby(["weekday", "direction"])["mean_flow"]
    .mean()
    .unstack()
)
print(weekday)
```

Use `lighting_period == "commissioning"` or `"illuminated"` for the other
optical regimes. Omitting the filter deliberately combines incompatible
nighttime detector conditions.

<div class="note warning">
The downloadable CSV snapshot is a five-minute/half-hour browser derivation, not the lossless layer. Use the exact Parquet release for full-resolution reuse. Native service backups are preservation artifacts and are intentionally not public data.
</div>

## External validation snapshot v1

This additive snapshot contains the high-level comparison with MTC and Caltrans
public statistics. It does not contain or imply calibrated vehicle counts.

```js
Inputs.table(validationManifest, {
  columns: ["path", "bytes", "sha256"],
  header: {path: "File", bytes: "Bytes", sha256: "SHA-256"},
  format: {
    bytes: (value) => value.toLocaleString("en-US"),
    sha256: (value) => `${value.slice(0, 16)}…`
  },
  width: {path: 280, bytes: 110, sha256: 210}
})
```

```js
const validationDownloads = [
  ["direction-summary.csv", directionValidationFile],
  ["westbound-monthly-match.csv", monthlyValidationFile],
  ["official-peak-hour-reference.csv", peakValidationFile],
  ["provenance.json", validationProvenanceFile]
];
```

```js
html`<div class="grid grid-cols-2">
  ${validationDownloads.map(([name, file]) => html`<div class="card">
    <div class="metric-label">${name}</div>
    <p><a href=${file.href} download>Download file →</a></p>
  </div>`)}
</div>`
```
