# RFD-014: Historical Traffic Archive and Static Open-Data Site

**Authors:** Wentao Jiang, Codex  
**Date:** 2026-07-26  
**Status:** 🟡 PROPOSED — Inspection Complete, Source Preservation Pending  
**Related:** RFD-004 (Prometheus/Grafana Monitoring), RFD-006 (Data Persistence
Incident), RFD-007 (Historical Import), RFD-010 (Prometheus Retention), RFD-012
(Speed Metrics), RFD-013 (Traffic Pattern Analysis)

## Summary

This RFD documents the transition of the Bay Bridge traffic monitor from a live,
apartment-hosted Grafana service into a permanent static data exhibit. The
recommended system preserves the complete Prometheus archive, publishes exact
and normalized time-series data on Hugging Face, generates reproducible analysis
artifacts, and deploys a narrative Observable Framework site through Cloudflare
Pages at `bay-bridge-traffic.com`.

The initial inspection found approximately 351 days of application data,
197.6 million persisted Prometheus samples, and a critical storage hazard: the
running Prometheus container uses a 689.6 MB Docker volume associated with an
older Compose project, while the similarly named volume implied by the current
repository is empty. Preserving and verifying that exact active volume is the
required first implementation step.

This document also serves as the append-only development log for the archive
migration. New entries should record what was inspected or changed, evidence
collected, decisions made, validation results, and remaining risks.

## Goals

1. Preserve the complete source archive before changing or decommissioning the
   local monitoring stack.
2. Publish a lossless, reusable, well-documented open-data release.
3. Recompute analysis from the complete collection period with explicit
   coverage and data-quality handling.
4. Replace the live Grafana iframe with a fast, durable static data application.
5. Make the source, methodology, limitations, and derivations reproducible.
6. Remove the apartment Mac, Prometheus, Grafana, proxy, and Cloudflare Tunnel
   from the production request path.

## Non-Goals

- Claiming official or ground-truth Bay Bridge traffic counts.
- Converting pixel-per-second detector features into physical vehicle speed
  without an independent calibration.
- Preserving a continuous video archive; none was collected.
- Keeping a live operational dashboard after the camera is retired.

## Non-Destructive Preservation Policy

**Nothing from the existing system is to be deleted, truncated, overwritten, or
cleaned up as part of archive preparation.** This includes:

- Prometheus Docker volumes, TSDB blocks, WAL files, and historical samples.
- Grafana Docker volumes, SQLite state, dashboards, and datasource metadata.
- September 2025 Parquet caches, analysis metadata, and generated Plotly pages.
- Detector source, configuration, debug frames, logs, import artifacts, and
  counter-state files.
- Existing Cloudflare Tunnel, DNS, domain, and live-service configuration.

All archive and site work must be additive:

1. Inspect the source in place using read-only operations.
2. Copy source material into a new archive location.
3. Validate the copy before transforming it.
4. Write transformations into new versioned directories.
5. Preserve raw, normalized, and derived layers independently.
6. Record checksums, commands, versions, and row counts.

No Docker prune, volume removal, container recreation, TSDB compaction,
retention change, credential revocation, DNS change, tunnel removal, or local
source cleanup may occur without explicit approval after verified backups
exist.

The only files that tooling may routinely regenerate are explicitly disposable
build products such as `site/dist/`. Generated site output is never considered
the source archive and must not be the only copy of any data.

## Development Log — 2026-07-26

### Objective

Preserve the historical traffic dataset before the apartment move, retire the
Mac-hosted Grafana/Prometheus production path, publish the source and data where
practical, and replace the live dashboard with a static site containing
analysis, insights, methodology, and reproducible downloads.

### Inspection progress

- [x] Inspected the repository structure, documentation, web page, monitoring
  configuration, dashboard definition, exporters, cached analysis, and generated
  plots.
- [x] Checked the running Docker containers, mounts, volumes, health endpoints,
  Prometheus flags, TSDB blocks, series labels, and Grafana API.
- [x] Queried the historical traffic metrics to determine the real time range,
  coverage, counter behavior, outages, and preliminary traffic patterns.
- [x] Compared the live archive with the checked-in/generated September 2025
  analysis.
- [x] Checked tracked files and Git history for committed `.env`,
  `prometheus.yml`, key, or certificate files. None were found in history by the
  filename check. This is not a substitute for a full secret scan before making
  the repository public.
- [x] Verified current Hugging Face dataset, Observable Framework, and
  Cloudflare Pages constraints from their official documentation.
- [x] Wrote the initial archive and static-site proposal below.
- [x] Adopted an explicit non-destructive preservation policy.
- [x] Approved the proposed Observable Framework, Cloudflare Pages, and Hugging
  Face architecture for implementation.
- [ ] Create immutable backups of the active Prometheus and Grafana volumes.
- [ ] Implement the exact-sample export and normalization pipeline.
- [ ] Regenerate analysis from the full archive.
- [ ] Build, validate, and deploy the static site.
- [ ] Publish the dataset and open-source release.
- [ ] Retire the live tunnel and monitoring containers after verification.

No containers, Docker volumes, repository configuration, remote services, or
datasets were changed during the inspection.

### Repository state observed

- Repository size was approximately 988 MB, mostly because of ignored local
  outputs and generated artifacts.
- Tracked Git data was small: approximately 784 KiB of loose objects.
- The worktree was clean at the beginning of the inspection.
- The public page is `public/index.html`. It contains a header and footer around
  an iframe pointing to the live Grafana dashboard.
- The Grafana dashboard is also represented in
  `grafana/dashboards/grafana-dashboard.json`.
- The existing analysis cache contains four September 20, 2025 Parquet files:
  vehicle counters, flow rate, current pixel speed, and average pixel speed.
- That cache covers only August 7 through September 20, 2025: approximately 44
  days and 341,794 one-minute points.
- The existing analysis output contains nine standalone Plotly documents plus an
  index. The plots total approximately 44 MB because each document embeds a
  large Plotly bundle and its own data.
- No continuous video or still-image archive was found. The ignored `outputs/`
  directory contains only a small number of development/debug frames.
- There is no code license, data license, or citation file.

### Live service state observed

| Service | State | Notes |
| --- | --- | --- |
| Grafana | Running for approximately five weeks | Local port 3000; health API returned HTTP 200 |
| Prometheus | Running for approximately five weeks | Local port 9090; readiness returned HTTP 200 |
| Detector metrics endpoint | Down | Port 9091 refused connections |
| Local proxy | Running | Port 8080 returned the iframe landing page |
| Public domain | Reachable | `https://bay-bridge-traffic.com` returned the same live landing page |

Prometheus is currently retaining data for ten years. It is no longer receiving
application metrics, but it continues scraping/recording its small set of
internal scrape-health series.

The Grafana dashboard contains 12 panels and defaults to a three-hour live
window. Because the detector endpoint is down, the live dashboard is no longer
an appropriate permanent presentation.

### Critical storage finding

The active Prometheus container does **not** use the empty volume implied by
running Compose from the current repository.

Active volume:

```text
20250802_bay_bridge_traffic_cam_prometheus-storage
```

Observed size:

```text
approximately 689.6 MB
```

The running container also binds its Prometheus configuration from an older
checkout:

```text
/Users/wentaojiang/Documents/GitHub/PlayGround/20250802_bay_bridge_traffic_cam/prometheus.yml
```

The volume named for the current Compose project,
`bay-bridge-traffic-cam_prometheus-storage`, was observed to be empty.

Do not run Docker volume pruning or recreate the Prometheus container from the
current checkout until the exact active volume has been copied, verified, and
checksummed. A Compose recreation could attach an empty volume while leaving the
real archive easy to overlook.

The active Grafana container uses:

```text
bay-bridge-traffic-cam_grafana-storage
```

Its observed size was approximately 52.8 MB.

### Historical data inventory

Prometheus reported 24 persisted blocks:

| Property | Observed value |
| --- | ---: |
| TSDB directory size inside the container | approximately 658 MiB |
| Docker volume accounting | approximately 689.6 MB |
| Samples in persisted blocks | 197,608,492 |
| Chunks in persisted blocks | 1,660,661 |
| Earliest application data | 2025-08-07 |
| Latest application data | 2026-07-25 04:20 UTC |
| Latest application data, Pacific time | 2026-07-24 21:20 PDT |
| Observed span | approximately 351.4 days |
| Approximate coverage at five-minute sampling | 97.4% |

The eight principal direct application metric families account for
approximately 108.6 million full-resolution samples over the retained period:

| Metric | Approximate raw sample count |
| --- | ---: |
| `traffic_vehicles_total` | 11,825,364 |
| `traffic_vehicles_created` | 11,825,364 |
| `traffic_flow_rate_per_minute` | 11,824,714 |
| `traffic_speed_current_pixels_per_second` | 10,875,020 |
| `traffic_speed_average_pixels_per_second` | 32,636,700 |
| `motion_detector_fps` | 5,912,659 |
| `tracked_objects_active` | 5,912,659 |
| `system_status` | 17,738,046 |

The difference between these samples and the full TSDB total consists of
Prometheus/self-scrape metrics and historical imported series.

### Data-quality notes

#### Counts are detector outputs, not verified vehicle ground truth

`traffic_vehicles_total` increments when a tracked object crosses the configured
counting line with a stable left/right direction. It should be described as an
algorithmic crossing detection. Public copy should avoid implying Caltrans-grade
ground-truth vehicle counts.

Use wording such as:

> Approximately 46 million algorithmic vehicle-crossing detections from a
> window-facing camera.

#### One counter reset was detected

At five-minute sampling, the direct counters had one negative step on August 9,
2025:

| Direction | Observed drop |
| --- | ---: |
| Left / Oakland-bound | -272,378 |
| Right / SF-bound | -575,292 |

The implementation ignores a persisted counter state if it is older than 24
hours. This explains how a long interruption can cause the Prometheus counter to
restart.

Final displayed counter values were approximately:

| Direction | Final counter |
| --- | ---: |
| Left / Oakland-bound | 14,914,082 |
| Right / SF-bound | 30,769,612 |

These values must not simply be summed and presented as the exact lifetime total.
The canonical dataset should identify reset segments and calculate event totals
from non-negative deltas. A preliminary five-minute calculation found about
14.99 million positive left increments and 30.92 million positive right
increments after the first sampled point. Exact results must be recomputed from
the raw sample export.

#### Historical imports created duplicate-looking label series

Early historical imports created series with labels such as:

```text
exported_job="imported_data"
exported_exported_instance="import_..."
```

The first TSDB block had 614 series while later steady-state blocks had about 34.
Dashboard queries that omit import-label filtering can mix imported and direct
series. The normalization pipeline must preserve the original series in the raw
layer, then reconcile imported history into one documented canonical timeline.

The existing collector deduplicates on timestamp, metric, direction, app, and
exported instance. It was designed for the earlier import incident, but it must
be revalidated before using it on the complete archive.

#### Speed is not physically calibrated

The speed metrics are pixels per second and should be presented as relative
motion/detector features. They are not mph or km/h. The dataset contains 1-minute,
5-minute, and 15-minute rolling speed windows.

#### Known availability gaps

The five-minute flow series had 29 gaps longer than ten minutes. The two largest
were:

- November 28, 2025 23:15 PST through December 1, 2025 13:25 PST:
  approximately 62 hours.
- May 14, 2026 21:35 PDT through May 20, 2026 06:50 PDT:
  approximately 129 hours.

There was also an approximately 11.6-hour interruption on March 27–28, 2026 and
several shorter intermittent periods. Analyses should carry an explicit coverage
mask and never interpolate across outages without labeling that choice.

#### Existing RFD claims need revision

The September analysis describes "6.4 million vehicle records." The 6.4 million
figure was a counter value, not the number of stored time-series rows. The
September cache actually contains 341,794 time-series points. Public
documentation must keep detections, samples, and time buckets separate.

### Preliminary traffic patterns

These are inspection-level results from five-minute samples. They are useful for
selecting site stories, but they are not the final published analysis.

| Metric | Left / Oakland-bound | Right / SF-bound |
| --- | ---: | ---: |
| Mean flow | 29.9 detections/min | 61.1 detections/min |
| Median flow | 20.0 detections/min | 59.0 detections/min |
| 95th percentile | 84.0 detections/min | 135.0 detections/min |

Average flow by weekday:

| Day | Left / Oakland-bound | Right / SF-bound |
| --- | ---: | ---: |
| Monday | 29.7 | 60.5 |
| Tuesday | 31.9 | 61.5 |
| Wednesday | 31.8 | 62.4 |
| Thursday | 31.2 | 63.2 |
| Friday | 32.0 | 65.9 |
| Saturday | 28.0 | 61.3 |
| Sunday | 24.6 | 52.7 |

Initial pattern hypotheses:

- Right/SF-bound traffic has a strong weekday peak around 8–10 AM.
- Left/Oakland-bound traffic peaks later, around noon–2 PM, with a broader
  afternoon shoulder.
- Weekend right/SF-bound demand shifts later toward late morning.
- Sunday is the quietest average day in both directions.
- Mean weekend flow is below mean weekday flow.

Each of these should be recomputed from reset-aware, coverage-aware canonical
data with uncertainty bands and complete-day filters.

## Proposal

### Recommendation

Build a permanent narrative data exhibit with:

- **Static data app:** Observable Framework.
- **Charts:** Observable Plot/D3, with compact build-time data snapshots.
- **Hosting:** Cloudflare Pages at `bay-bridge-traffic.com`.
- **Raw/open data:** A public Hugging Face dataset using partitioned Parquet.
- **Source:** This GitHub repository, made public after cleanup, licensing, and
  a full secret scan.
- **Preservation:** An immutable Prometheus TSDB archive in addition to the
  convenient Parquet representation.

This removes the Mac, Grafana, Prometheus, Python proxy, nginx, and Cloudflare
Tunnel from the production request path.

```text
Immutable Prometheus TSDB copy
        |
        +-- exact raw samples ----------> Hugging Face raw Parquet
        |                                      |
        |                                      +--> public download/query
        |
        +-- normalization and QA -------> canonical/derived Parquet
                                               |
                                               +--> Observable static build
                                                        |
                                                        +--> Cloudflare Pages
```

### Why Observable Framework

Observable Framework is an open-source static-site generator for data apps. It
supports narrative Markdown, reactive JavaScript, Observable Plot/D3, and
build-time data loaders written in Python. The current Python analysis can
therefore remain the statistics/ETL implementation while the presentation
becomes a compact static application.

This is preferable to preserving the current Plotly export because the existing
nine plots repeat multi-megabyte JavaScript/data bundles. It is also preferable
to a static Grafana snapshot because the project is now an archive and story,
not an operational monitoring dashboard.

References:

- https://observablehq.com/framework/
- https://observablehq.com/framework/data-loaders
- https://observablehq.com/framework/deploying

### Why Cloudflare Pages

The domain and DNS are already on Cloudflare. Pages can serve the generated
static output globally without a tunnel or home machine. The full-resolution
dataset should not be bundled into the site: Cloudflare Pages currently limits
individual static assets to 25 MiB. The site should contain only compact derived
datasets, while Hugging Face serves the complete archive.

Reference:

- https://developers.cloudflare.com/pages/platform/limits/

### Open-data package

Proposed Hugging Face dataset layout:

```text
README.md
LICENSE-DATA
CITATION.cff

source/
  prometheus-tsdb.tar.zst
  grafana-dashboard.json
  prometheus-flags.json
  tsdb-block-manifest.json

raw/
  metric=traffic_vehicles_total/year=2025/month=08/part-*.parquet
  metric=traffic_flow_rate_per_minute/year=2025/month=08/part-*.parquet
  metric=traffic_speed_current_pixels_per_second/year=2025/month=09/part-*.parquet
  metric=traffic_speed_average_pixels_per_second/year=2025/month=09/part-*.parquet
  metric=motion_detector_fps/year=2025/month=08/part-*.parquet
  metric=tracked_objects_active/year=2025/month=08/part-*.parquet
  metric=system_status/year=2025/month=08/part-*.parquet

normalized/
  traffic_flow_5s/
  vehicle_counters_5s/
  relative_speed_5s/
  system_metrics_5s/

derived/
  traffic_5min.parquet
  hourly.parquet
  daily.parquet
  weekday_profiles.parquet
  coverage_intervals.parquet
  notable_days.parquet

metadata/
  schema.json
  quality-report.json
  processing-provenance.json
  manifest.sha256
```

The raw Parquet layer should preserve the exact timestamp, metric name, value,
and complete original label set. The normalized layer should have stable column
names, canonical direction names, reset segment identifiers, import provenance,
and explicit quality flags.

Hugging Face recommends Parquet for tabular datasets and supports browsing it in
Dataset Viewer/Data Studio. A dataset card is required for large public
datasets and should document provenance, intended reuse, bias, limitations, and
the distinction between detections and ground truth.

References:

- https://huggingface.co/docs/hub/en/datasets-adding
- https://huggingface.co/docs/hub/storage-limits
- https://huggingface.co/docs/hub/datasets-cards
- https://huggingface.co/docs/hub/main/datasets-data-files-configuration

### Exact export method

Do not treat a Prometheus `query_range` result as the full-resolution source.
Range queries evaluate at aligned steps and are suitable for derived/resampled
data, not a lossless archive.

The installed Prometheus tooling supports:

```text
promtool tsdb dump
promtool tsdb dump-openmetrics
```

The archive procedure should:

1. Freeze the final collection cutoff.
2. Make an immutable copy of the active TSDB while following a consistency-safe
   shutdown/snapshot procedure.
3. Verify the copied TSDB with `promtool tsdb list`.
4. Generate an OpenMetrics dump from the copy, partitioned by metric and time.
5. Convert exact samples to Parquet with bounded row groups and page indexes.
6. Generate row counts, min/max timestamps, schemas, and SHA-256 checksums.
7. Compare raw sample counts with the TSDB block inventory.
8. Keep both the native TSDB archive and Parquet export.

### Static-site content

#### 1. Home: "A Year Watching the Bay Bridge"

- One representative bridge photograph or detector frame.
- Collection dates, coverage, and approximate algorithmic detections.
- A short explanation of the apartment view, old iPhone, and detector.
- Three defensible headline findings.
- Clear links to Explore, Methodology, Data, and Source.

#### 2. Traffic Explorer

- Selectable date range.
- Both traffic directions.
- Five-minute and hourly resolution choices.
- Calendar heatmap of daily traffic.
- Daily volume with a coverage overlay.
- Explicit outage/reset annotations.

#### 3. Typical Week

- Seven weekday profiles.
- Median and percentile bands rather than only mean and standard deviation.
- Weekday/weekend comparison.
- Directional morning/afternoon asymmetry.
- Sample-count and completeness indicators for every aggregate.

#### 4. Notable Days

- Highest and lowest complete days.
- Holidays and known special events, if separately sourced and cited.
- Directional imbalance outliers.
- Detector anomalies shown separately from traffic anomalies.

#### 5. Relative Speed and Detector Behavior

- Pixel-speed distributions and rolling trends.
- Detector FPS and active tracked-object behavior.
- Explicit statement that speed is not physically calibrated.

#### 6. Methodology and Data Quality

- Camera geometry, ROI, counting line, and direction mapping.
- Motion segmentation and persistent object tracking.
- Coverage timeline and outage list.
- Counter-reset reconstruction.
- Historical-import reconciliation.
- Known false-positive/false-negative modes.
- No claim that the dataset is official bridge traffic data.

#### 7. Download and Reproduce

- Hugging Face dataset.
- GitHub source.
- Dataset schema and checksums.
- Exact processing version/commit.
- Citation instructions.
- Minimal DuckDB, Polars, and pandas query examples.

### Browser data budget

The site should not query the 100M-plus raw rows interactively. Suggested static
artifacts:

- Five-minute two-direction flow series for the date-range explorer.
- Hourly and daily aggregates for overview charts.
- Precomputed weekday/profile percentile tables.
- Coverage intervals and reset annotations.
- Small JSON metadata with headline values and provenance.

Keep every deployed asset below 25 MiB and target an initial page payload below
2 MB. Load explorer data only when that page is opened.

### Licensing proposal

- **Code:** MIT, unless there is a reason to prefer Apache-2.0.
- **Data:** CC BY 4.0.
- **Documentation/site text:** CC BY 4.0 or the repository code license, stated
  explicitly.
- Add `CITATION.cff` and dataset-card citation text.
- Optionally archive a versioned release with Zenodo if a DOI is desirable.

Before making the repository public:

1. Run a full secret scanner across all Git history.
2. Revoke/rotate the Grafana Cloud and Prometheus credentials in the ignored
   `.env`.
3. Remove local absolute paths from user-facing setup documentation.
4. Confirm that any published bridge photograph is owned by the project and
   contains no unintended personal information.

## Implementation plan

### Phase 0 — Preserve before modifying

- [ ] Record container IDs, image digests, mounts, volume names, Prometheus
  version, Grafana version, and final timestamps.
- [ ] Copy the active Prometheus TSDB using a consistency-safe process.
- [ ] Copy the active Grafana data volume/SQLite database.
- [ ] Export the live Grafana dashboard and datasource metadata through the API.
- [ ] Save Prometheus flags, build information, block inventory, and series
  inventory.
- [ ] Generate checksums.
- [ ] Verify both local and second-location backups before any Docker cleanup.

Exit criterion: two verified copies of the source archive, plus a documented
restore test or successful `promtool tsdb list` on the copied TSDB.

### Phase 1 — Exact export and normalization

- [ ] Add a reproducible archive CLI under `scripts/`.
- [ ] Export exact samples from the immutable TSDB copy.
- [ ] Write metric/month Parquet shards.
- [ ] Preserve every original label in the raw layer.
- [ ] Reconcile imported/direct history in a canonical layer.
- [ ] Detect counter resets and create reset segments.
- [ ] Generate coverage intervals and quality flags.
- [ ] Produce manifest, schemas, row counts, time ranges, and checksums.
- [ ] Add tests for DST, duplicated imports, counter resets, and missing ranges.

Exit criterion: raw sample counts reconcile with Prometheus, canonical datasets
pass tests, and the export is reproducible from the archived TSDB.

### Phase 2 — Full-period analysis

- [ ] Replace the September-only discovery metadata.
- [ ] Recompute complete-day/hour/week profiles over the full period.
- [ ] Quantify missingness before every aggregate.
- [ ] Generate headline statistics from one versioned analysis module.
- [ ] Identify notable complete days and distinguish operational failures.
- [ ] Write a final quality report and limitations section.

Exit criterion: every public statistic can be traced to a script, dataset
version, and testable computation.

### Phase 3 — Static site

- [ ] Add Observable Framework alongside the Python project.
- [ ] Implement shared page layout and navigation.
- [ ] Build Home, Explorer, Typical Week, Notable Days, Methodology, and Download
  pages.
- [ ] Generate compact site data through Python build-time loaders.
- [ ] Add responsive and accessibility checks.
- [ ] Ensure the site functions without Prometheus, Grafana, or network access to
  Hugging Face except for download links.
- [ ] Verify asset sizes and page-load behavior.

Exit criterion: the complete site can be served from the generated static
directory with all analytical views working.

### Phase 4 — Publish

- [ ] Create and populate the Hugging Face dataset repository.
- [ ] Verify Dataset Viewer, schemas, checksums, and download examples.
- [ ] Add code/data licenses and citation files.
- [ ] Complete full-history secret scanning and rotate credentials.
- [ ] Make the GitHub repository public.
- [ ] Configure Cloudflare Pages build/deployment.
- [ ] Attach and test `bay-bridge-traffic.com`.
- [ ] Test links, mobile layout, cache behavior, and a clean-browser session.

Exit criterion: public site, source, and data are reachable and mutually linked.

### Phase 5 — Decommission live infrastructure

- [ ] Keep the existing tunnel until the static custom domain is verified.
- [ ] Remove the DNS/tunnel route to the apartment-hosted proxy.
- [ ] Stop Grafana, Prometheus, proxy, and tunnel containers/processes.
- [ ] Retain verified offline archives before deleting any Docker volumes.
- [ ] Document what was removed and where recovery copies live.

Exit criterion: the domain is fully static, no home-hosted process is required,
and recovery does not depend on a Docker volume remaining on one laptop.

## Decision log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-07-26 | Preserve the exact active Docker volume before other work | The current Compose project points at an empty, differently named volume |
| 2026-07-26 | Replace live Grafana with a narrative static data app | Collection has ended and the three-hour operational view no longer represents the archive |
| 2026-07-26 | Use Observable Framework | Static, open-source, data-oriented, and compatible with Python build-time loaders |
| 2026-07-26 | Use Cloudflare Pages | Existing domain/DNS relationship and no runtime server requirement |
| 2026-07-26 | Use Hugging Face for full data | Good Parquet integration, public discovery, Dataset Viewer, and sufficient scale |
| 2026-07-26 | Preserve both native TSDB and Parquet | Native TSDB maximizes recoverability; Parquet maximizes reuse |
| 2026-07-26 | Publish derived data separately from raw data | Fast browser experience without compromising access to full-resolution samples |
| 2026-07-26 | Call records "algorithmic detections" | Avoid implying verified physical vehicle counts |

## Next action

Perform Phase 0 only: create and verify immutable backups without deleting,
recreating, or reconfiguring any running container. Once that source-of-truth
archive is safe, implement the exporter against the copy rather than the live
volume.
