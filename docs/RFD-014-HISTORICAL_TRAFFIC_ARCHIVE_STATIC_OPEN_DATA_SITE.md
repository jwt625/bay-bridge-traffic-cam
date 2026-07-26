# RFD-014: Historical Traffic Archive and Static Open-Data Site

**Authors:** Wentao Jiang, Codex  
**Date:** 2026-07-26  
**Status:** 🟡 RELEASE — Pages Production Verified, Apex DNS Cutover Pending
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
- [x] Create verified backups of the active Prometheus and Grafana volumes.
- [~] Implement the exact-sample export and normalization pipeline. A read-only
  five-minute derived snapshot exists; exact full-resolution export must run
  against an immutable TSDB copy.
- [x] Regenerate the first analysis snapshot from the full observed period.
- [~] Build, validate, and deploy the static site. The approved build is
  verified on the Cloudflare Pages production hostname; the apex DNS cutover
  remains pending.
- [x] Publish the dataset. The code release is prepared and scanned; making the
  currently private GitHub repository public remains a separate approval gate.
- [ ] Retire the live tunnel and monitoring containers after verification.

No containers, Docker volumes, remote services, or published datasets were
changed during inspection or implementation. All repository work is additive,
except for disposable static build output.

### Implementation progress — 2026-07-26

#### Preservation and inventory

- [x] Added the explicit non-destructive preservation policy above. No existing
  source archive, TSDB block, dashboard, September analysis artifact, container,
  domain configuration, or remote service is to be deleted or replaced.
- [x] Added `scripts/capture_archive_inventory.py`, which captures a sanitized,
  read-only service inventory into a new versioned directory and refuses to
  overwrite an existing capture.
- [x] Captured `archive/metadata-v1/`, including container/image/mount metadata,
  Prometheus flags, build information, TSDB status, block inventory,
  application series, Grafana health, dashboard search results, the exported
  dashboard, and a checksum manifest.
- [x] Omitted container environment variables from the inventory to avoid
  copying credentials into the repository.
- [x] Copied the active Prometheus TSDB and Grafana data volumes into
  `archive/source-v1/` after explicit user approval. The copy operation paused
  each container only while its volume was copied, always resumed both
  containers, and then checked Prometheus readiness and Grafana health.
- [x] Verified all 371 files against the generated SHA-256/byte-size manifest:
  689,516,685 bytes of Prometheus state plus 52,795,392 bytes of Grafana state,
  for 742,312,077 bytes total.
- [x] Ran SQLite `PRAGMA quick_check` on the copied Grafana database; it
  returned `ok`.
- [x] Created a separate APFS copy-on-write export workspace under
  `archive/export-work-v1/`. `promtool tsdb list` and an exact-sample dump both
  succeeded there. The canonical source backup remained unchanged and all 371
  checksums were reverified afterward.
- [x] Added ignore rules for `archive/source-*` and
  `archive/export-work-*`, preventing native operational backups from entering
  Git or a public data release.

#### Exact export and release safety — 2026-07-26

- [x] Added `scripts/backup_runtime_volumes.py`, which resolves the two exact
  expected volumes, refuses an existing output directory, pauses for the
  shortest copy interval, resumes in a `finally` path, verifies health, and
  writes checksums.
- [x] Added `scripts/export_exact_tsdb.py`. It streams the eight application
  metric families from the copied TSDB through the exact Prometheus image,
  preserves millisecond timestamps and original label JSON, writes
  metric/month Zstandard Parquet shards, refuses overwrite, and produces
  provenance plus a SHA-256 manifest.
- [x] Validated a ten-minute smoke export: 240 exact flow samples, both
  directions, 14 typed columns, and a first timestamp of
  `2026-07-25T02:00:02.483Z`.
- [x] Added `scripts/validate_exact_dataset.py` to independently check every
  manifest entry, Parquet schema, row count, metric set, and timestamp
  statistics before upload.
- [x] Completed the export from the copy-on-write workspace into a separate
  sibling staging directory. It did not read from the live volume. The result
  contains 108,644,312 exact samples across 94 metric/month Parquet shards and
  all eight intended metric families.
- [x] Independently validated all 95 staging manifest entries, schemas, row
  counts, metric names, and timestamp statistics. The exact observed range is
  `2025-08-07T18:00:00.471Z` through
  `2026-07-25T02:24:42.527Z`.
- [x] Audited all 190 unique raw label sets. Values were limited to the expected
  detector app, directions, speed windows, component names, local scrape
  endpoint, and historical import identifiers. Direct samples number
  108,630,056; imported-label samples number 14,256.
- [x] Reverified all 371 canonical source-backup checksums after the export.
- [x] Built a separate sanitized public package: 119 manifested files totaling
  616,522,063 bytes. All 94 published Parquet shards are byte-identical to the
  validated staging export. The package contains no absolute local paths.
- [x] Ran Gitleaks over the complete 616 MB release; zero findings.
- [x] Published the new public Hugging Face dataset
  [`jwt625/bay-bridge-traffic-cam`](https://huggingface.co/datasets/jwt625/bay-bridge-traffic-cam).
  Hugging Face committed all 120 local release files (616.5 MB); its generated
  `.gitattributes` is the only additional repository file.
- [x] Verified that all 120 remote paths match the local release, downloaded
  the remote dataset card, manifest, and export provenance byte-for-byte, and
  downloaded five representative Parquet shards spanning metrics/months.
  Their SHA-256 values match the local validated package.
- [x] User inspected and approved the hosted site preview for production
  release.
- [x] Committed and pushed the archive/site implementation to the private
  GitHub `main` branch as commit `0cd2cb3`. Making the source repository public
  is intentionally separate from publishing the already public dataset.
- [x] Deployed the built `site/dist/` to an isolated temporary Cloudflare
  Workers preview without using the production account, DNS, domain, or
  tunnel. All eight page routes and representative hashed JS, CSS, and data
  assets returned HTTP 200 after propagation; a remotely fetched half-hour CSV
  matched the local build checksum.
- [x] Completed Cloudflare Wrangler OAuth after the initial callback attempt
  timed out. Declined Wrangler's unrelated optional AI-agent skill
  installation.
- [x] Created the durable Cloudflare Pages project
  `bay-bridge-traffic-archive` and deployed commit `7467dd2` to the isolated
  `archive-preview` branch.
- [x] Verified all eight durable preview routes plus representative hashed JS,
  CSS, and data assets over HTTPS. The remotely served half-hour CSV is
  byte-identical to the local build. The macOS system `curl` required TLS 1.2
  because its older LibreSSL failed against the current Pages TLS handshake;
  OpenSSL 3 and normal browsers validate the Pages certificate successfully.
- [x] Promoted the exact approved build at Git commit `265809d` to the
  Cloudflare Pages `main` production branch. Cloudflare reused all 73 already
  verified files and created production deployment
  `f4acfddc-dbc7-4e5c-a960-90a613668cfd`.
- [x] Verified the stable Pages production hostname
  `https://bay-bridge-traffic-archive.pages.dev`: all eight routes returned
  HTTP 200 and the remotely fetched half-hour CSV SHA-256
  (`28ae4fbed4de847975de546738a493f77db6bc7c4a2fe7f7114d07b58f5eb6e7`)
  matched the local approved build.
- [x] Added `bay-bridge-traffic.com` to the Pages project through the
  Cloudflare API. Cloudflare accepted the association, but reports
  `verification_data.error_message: "CNAME record not set"` because the
  existing proxied apex DNS record still routes to the legacy Cloudflare
  Tunnel.
- [ ] Change the existing apex DNS record target to
  `bay-bridge-traffic-archive.pages.dev`, then verify TLS, all routes, and the
  representative data checksum on the apex. Wrangler OAuth has Pages-write
  permission but no DNS-read/write permission, so this final DNS edit cannot be
  performed with the authenticated CLI session.
- [x] Kept the legacy Cloudflare Tunnel, proxy, Grafana, Prometheus, Docker
  volumes, and verified backups intact and running as rollback sources. Nothing
  was deleted, stopped, or reconfigured during this release attempt.
- [x] Confirmed Hugging Face CLI authentication as user `jwt625`; the target
  dataset repository does not currently exist, so upload cannot accidentally
  overwrite an existing dataset.
- [x] Confirmed the ignored local `prometheus.yml` is not tracked and has no
  Git history. It contains a live remote-write credential and is therefore
  excluded from backups intended for publication. Rotate that credential only
  as a later explicit production-retirement action.
- [x] Scanned all 15 Git commits and the complete tracked/untracked publication
  candidate tree with Gitleaks 8.30.1. Both scans returned zero findings.
- [x] Added an MIT software license, CC BY 4.0 data-license notice, and
  `CITATION.cff`; preserved the original live-system README as a clearly
  labeled historical section.

#### Derived archive preparation

- [x] Added `scripts/prepare_static_site_data.py`.
- [x] Queried the live Prometheus API read-only in 21-day chunks at five-minute
  resolution, selecting only direct application series with
  `exported_job=""`.
- [x] Wrote the derived snapshot into the new immutable directory
  `site/src/data/archive-v1/`; the script refuses to overwrite an existing
  snapshot directory.
- [x] Preserved `archive-v1` unchanged and generated `archive-v2` after adding
  the Bay Lights optical-regime segmentation and nighttime diagnostics.
- [x] Preserved both earlier snapshots unchanged and generated `archive-v3`
  after adding a real 30-minute activity series from the five-minute source.
- [x] Generated summary, hourly, daily, monthly, weekday-profile, speed-profile,
  coverage-gap, counter-reset, provenance, and manifest artifacts.
- [x] Handled DST by aggregating UTC timestamps first and adding explicit Pacific
  display labels. Expected daily samples correctly use 23-hour and 25-hour
  local days.
- [x] Marked the snapshot as a five-minute Prometheus query-range derivation,
  not a lossless full-resolution TSDB export.

Derived snapshot inventory:

| Artifact | Rows / result |
| --- | ---: |
| `hourly.csv` | 16,466 |
| `half-hour.csv` (archive-v3) | 32,926 directional half-hour bins |
| `daily.csv` | 690 directional days |
| `weekday-profile.csv` | 1,344 profile points |
| `speed-profile.csv` | 1,344 profile points |
| `coverage-gaps.csv` | 29 gaps over ten minutes |
| Complete two-direction days | 335 |
| Positive five-minute counter increments | 45,910,702 |
| Observed period | 2025-08-07 11:05 PDT through 2026-07-24 21:20 PDT |

#### Static site

- [x] Added an Observable Framework site under `site/`.
- [x] Implemented a Grafana-inspired near-black theme with Grafana blue/orange
  direction colors, monospaced operational labels, compact panels, sharp
  corners, and no decorative shadows.
- [x] Added Overview, Historical Explorer, Typical Week, Notable Days, Data
  Quality, External Validation, Methodology, and Data/Download pages.
- [x] Recreated the September-style weekday and relative-speed analyses using
  the full-period snapshot, with median/interquartile envelopes and coverage
  qualification.
- [x] Added date, direction, metric, scaling, and lighting controls to the
  explorer. With the optional half-hour grid, its uncompressed data payload is
  approximately 5.0 MB and is composed of immutable, cacheable static files.
- [x] Made local preview use port 4173 so it does not conflict with Grafana on
  port 3000.
- [x] Kept the site independent of the live Prometheus and Grafana services; all
  page data is bundled into static output.
- [x] Restyled the Explorer day-by-hour heatmap as a GitHub contribution-style
  grid: five discrete dark-mode green intensity buckets, visible cell gaps,
  compact square-like marks, and a Less→More legend. Buckets are selection-local
  quintiles and are labeled as relative rather than absolute traffic levels.
- [x] Decoupled the heatmap direction control from the main time-series
  direction control so either bridge direction remains inspectable without
  creating an accidental empty heatmap.
- [x] Upgraded the activity grid from hourly to genuine half-hour resolution.
  `archive-v3/half-hour.csv` contains 32,926 direction-resolved bins; each
  complete bin aggregates six five-minute Prometheus samples and retains its
  sample count and coverage.
- [x] Bucketed half-hours in UTC before conversion to Pacific time so the
  repeated half-hour during daylight-saving fallback remains unambiguous.
- [x] Added a half-hour aggregation unit test and switched all site analysis
  inputs consistently from `archive-v2` to the additive `archive-v3`.
- [x] Added an interactive x-axis navigator to the Explorer hourly time series.
  Dragging across the navigator selects a zoom window; dragging the selection
  pans it; either edge resizes it; and double-click or **Reset zoom** restores
  the full active date/filter range. The primary chart and its y-domain update
  to the visible window while preserving exact hover values and data gaps.
- [x] Rebuilt, browser-rendered, and redeployed the zoomable Explorer to the
  durable `archive-preview` alias from commit `dffc59a`. All eight routes,
  the updated Explorer markup, and the new hashed stylesheet returned HTTP 200.
- [x] Merged the two direction columns in the all-weekdays comparison into one
  overlaid panel per weekday. Each panel now matches the large selected-day
  chart semantics: direction-colored median lines, 25th–75th percentile
  variation bands, and dashed means on a shared weekly y-scale.
- [x] Rearranged the weekly comparison into a responsive small-multiples grid:
  three columns by three rows on wide screens, two columns on medium screens,
  and one on mobile. The seven weekday panels are now 300 pixels tall, making
  within-day variation and direction overlap substantially more legible while
  retaining a common y-domain.
- [x] Formatted the x channel in all 15-minute profile hover tooltips as
  zero-padded local time (`HH:MM`) instead of the underlying numeric
  minute-of-day value. This applies to the selected-day flow chart, every
  weekly small multiple, and the relative pixel-speed chart.
- [x] Added final public Hugging Face links after publishing the raw-data
  release.
- [ ] Deploy or alter DNS. No public infrastructure change has been made.

#### Validation

- [x] `tests/test_static_site_data.py` passes its DST, direction-specific
  counter-reset, lighting-boundary, and cross-midnight night-window tests.
- [x] The Observable production build succeeds for all eight pages.
- [x] Runtime browser checks found no JavaScript exceptions on the site pages.
- [x] Desktop and mobile layouts were visually inspected; the mobile content
  width was corrected to prevent horizontal clipping.
- [x] The two external-validation tests and five static-site derivation tests
  pass. A full discovery run reached the pre-existing live metrics integration
  test but could not bind its fixed port 9092 because it was already in use;
  this is unrelated to the archive/validation code.
- [x] Production runtime dependencies report no known npm vulnerabilities.
- [ ] Observable Framework's development-only dependency tree reports one low
  and five high advisories in transitive build tooling. The suggested forced
  remediation downgrades Framework, so it was not applied. Reassess before a
  hosted build; static output contains no Node runtime.

#### Bay Lights detector discontinuity — 2026-07-26

The user identified the 2026 Bay Lights relighting as a likely camera-detector
regime change. Contemporary sources establish two external milestones:

- A February 26, 2026 *San Francisco Chronicle* report said 48,000 LEDs had
  entered a 24/7 burn-in approximately one week earlier. The analysis uses
  **2026-02-19** as an explicitly approximate commissioning boundary.
- Illuminate announced and held the official public Grand Lighting on
  **2026-03-20**, after which the primary north-facing installation was
  scheduled to operate nightly from dusk until dawn.

Sources:

- <https://www.sfchronicle.com/sf/article/bay-lights-return-bay-bridge-21944006.php/>
- <https://illuminate.org/2026/02/19/the-bay-lights-to-return-friday-march-20-2026/>

Read-only analysis of the detector archive confirms a night-specific
discontinuity. The strongest onset occurs during commissioning around March
8–12, not as one perfectly clean step on the approximate February 19 boundary.
At five-minute resolution, comparing complete 22:00–05:00 Pacific nights before
commissioning with nights after the official launch:

| Detector-stability diagnostic | Pre-lights | Illuminated era | Ratio |
| --- | ---: | ---: | ---: |
| Median nightly spike excess, directions averaged | 20.4 detections/min | 60.3 detections/min | 3.0× |
| Median nightly maximum, directions averaged | 47.0 detections/min | 160.5 detections/min | 3.4× |
| Median within-night standard deviation, directions averaged | 9.8 detections/min | 27.2 detections/min | 2.8× |

A one-minute read-only diagnostic over February 1 through April 14 provides a
stronger-resolution cross-check: the combined nightly median maximum increased
from approximately 85 to 305 detections/min, median 95th-percentile excess from
approximately 22 to 134 detections/min, and median minute-to-minute absolute
change from 4.5 to 22. Median `tracked_objects_active` increased from 1 before
commissioning to 4 after launch. Daytime flow did not exhibit a comparable
spike-noise increase.

This pattern is consistent with animated LEDs being segmented and tracked as
motion. It is strong observational evidence, but not a controlled causal test;
seasonality, weather, camera exposure, and real traffic remain possible
contributors.

Implementation response:

- [x] Added `pre_lights`, `commissioning`, and `illuminated` fields to hourly
  and daily data.
- [x] Added segmented weekday-flow and pixel-speed profiles plus an `all`
  aggregate.
- [x] Added `night-noise.csv`, `lighting-impact-summary.csv`, and
  `lighting-events.csv` to immutable `archive-v2`.
- [x] Added All, Pre-lights, Commissioning, and Illuminated-era controls to
  Explorer, Typical Week, and Notable Days.
- [x] Defaulted pattern and notable-day analysis to the cleaner pre-lights
  regime while retaining an explicit combined-data option.
- [x] Added event annotations, source links, warnings, methodology, and a
  dedicated Bay Lights diagnostic chart to Data Quality.

Analytical policy: do not use mixed-regime nighttime measurements for traffic
inference without explicitly accepting the detector discontinuity. Treat
commissioning as a transition/exclusion interval. Prefer pre-lights for
nighttime traffic-pattern claims; use illuminated-era data primarily for
detector-behavior analysis unless independently calibrated.

#### External traffic-count validation — 2026-07-26

The detector has no retained continuous imagery or manually labeled audit set.
Its precision, recall, false-positive rate, and false-negative rate are
therefore unknown. To constrain interpretation without inventing an accuracy
claim, a new read-only analysis compared complete pre-lights detector days with
official public traffic statistics.

Sources and scope:

- [MTC Monthly Transportation Statistics](https://mtc.ca.gov/tools-resources/data-tools/monthly-transportation-statistics)
  supplies monthly Bay Bridge totals for the one-way toll direction. On the Bay
  Bridge this is westbound/SF-bound.
- [Caltrans Traffic Census Program](https://dot.ca.gov/programs/traffic-operations/census)
  publishes annual average daily traffic and peak-hour workbooks.
- The [Caltrans 2024 AADT workbook](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/2024/2024-traffic-volumes-ca-a11y.xlsx)
  reports approximately 115,000 lower-deck/eastbound and 118,000
  upper-deck/westbound vehicles per day on the west span near Treasure Island.
- The [Caltrans 2024 peak-hour workbook](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/2024/2024-ca-peak-hours-a11y.xlsx)
  identifies westbound as the AM peak direction and eastbound as the PM peak
  direction at the toll plaza.

Comparison baseline: 191 complete detector days before the approximate
February 19, 2026 Bay Lights commissioning boundary.

| Direction | Camera pre-lights daily mean | Official 2024 AADT reference | Indicative ratio |
| --- | ---: | ---: | ---: |
| Oakland-bound / `left` | 46,986 detections | 115,000 vehicles | 2.45× |
| SF-bound / `right` | 86,965 detections | 118,000 vehicles | 1.36× |

The camera assigns 35.1% of pre-lights detections to Oakland-bound and 64.9% to
SF-bound. The official directional reference is nearly balanced at 49.4% and
50.6%. This falsifies any interpretation of the camera's apparent two-to-one
directional ratio as the bridge's actual traffic split and shows that a single
global scale factor is inappropriate.

For SF-bound traffic, monthly MTC comparisons from August 2025 through January
2026 produce detector-to-official reference multipliers between 1.23× and
1.43×. This suggests the SF-bound detector series can support cautious relative
trend analysis before the lighting change. It does not validate hourly values
or establish a correction factor. The Oakland-bound ratio is larger and less
stable, consistent with a stronger view/occlusion response on that deck.

High-level conclusion audit:

| Existing observation | Audit result |
| --- | --- |
| SF-bound weekday morning peak | Qualitatively corroborated; exact detector peak hour is not |
| Oakland-bound afternoon peak | Qualitatively corroborated; exact profile is not |
| Camera's roughly 2:1 directional volume | Contradicted as a traffic claim; retained only as detector behavior |
| Sunday appears quieter | Camera-only observation; no current third-party day-of-week validation obtained |
| Post-relighting night surge/noise | Optical detector discontinuity, not evidence of traffic growth |

Implementation response:

- [x] Added `scripts/prepare_external_validation.py`, which downloads the public
  workbooks, reads the immutable derived detector snapshot, and refuses to
  overwrite an existing output directory.
- [x] Created additive `site/src/data/validation-v1/` tables, provenance, and
  SHA-256 manifest. No source data or prior snapshot was modified.
- [x] Added a dedicated External Validation page, source links, downloadable
  comparison tables, and prominent accuracy/correction-factor warnings.
- [x] Added the same calibration boundary to Overview, Data Quality,
  Methodology, and Data.

Analytical policy, revised at user request: publish the original algorithmic
detections unchanged, but default count/flow plots to a reversible
direction-specific presentation transform of 2.447544× Oakland-bound and
1.356866× SF-bound. Every affected page must offer a Raw detector option and
label scaled values as reference-scaled estimates rather than corrected or
ground-truth traffic. Do not scale coverage, pixel-speed, validation, or
detector-noise diagnostics, and do not derive a separate post-Bay-Lights
nighttime factor from these comparisons.

Implementation response:

- [x] Centralized the factors and display-mode labels in
  `site/src/components/data.js`.
- [x] Defaulted Overview, Explorer, Typical Week, and Notable Days traffic
  plots to reference-scaled estimates.
- [x] Added per-page controls to remove the transform and inspect raw detector
  values.
- [x] Kept immutable CSV snapshots unchanged; scaling occurs only in browser
  presentation code.

#### Test-safety incident

While validating the pre-existing `tests/test_metrics.py --unit` suite, the
test instantiated `TrafficMetrics` with the production default
`persist_state=True`. It wrote the ignored local
`traffic_metrics_state.json`, replacing its contents with test counters
`left=2` and `right=1`. The test was terminated, and the state file has not been
restored, overwritten again, or deleted.

The Prometheus TSDB, Grafana data, containers, and derived archive are
unaffected. The old `.bak` file predates most collection and is not a suitable
automatic restore source. A reconstruction from the final Prometheus counter
samples is possible, but writing that reconstruction is intentionally pending
explicit approval.

The unit-test configuration now sets `persist_state=False`, and its worker test
uses a bounded mocked wait. The suite subsequently passed seven tests in 0.002
seconds with the collector state file SHA-256 unchanged before and after. No
production persistence behavior was modified.

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

- [x] Record container IDs, image digests, mounts, volume names, Prometheus
  version, Grafana version, and final timestamps.
- [ ] Copy the active Prometheus TSDB using a consistency-safe process.
- [ ] Copy the active Grafana data volume/SQLite database.
- [x] Export the live Grafana dashboard and datasource metadata through the API.
- [x] Save Prometheus flags, build information, block inventory, and series
  inventory.
- [x] Generate checksums for the captured metadata.
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

- [x] Replace the September-only discovery metadata in the static snapshot.
- [x] Recompute complete-day/hour/week profiles over the full period.
- [x] Quantify missingness before every aggregate.
- [x] Generate headline statistics from one versioned analysis module.
- [x] Identify notable complete days separately from coverage failures.
- [x] Write the first quality report and limitations section.

Exit criterion: every public statistic can be traced to a script, dataset
version, and testable computation.

### Phase 3 — Static site

- [x] Add Observable Framework alongside the Python project.
- [x] Implement shared page layout and navigation.
- [x] Build Home, Explorer, Typical Week, Notable Days, Methodology, and Download
  pages.
- [x] Generate compact site data through the Python preparation script.
- [~] Add responsive and accessibility checks. Responsive layouts were inspected;
  a formal accessibility audit remains.
- [x] Ensure the site functions without Prometheus, Grafana, or network access to
  Hugging Face except for download links.
- [x] Verify asset sizes and page-load behavior.

Exit criterion: the complete site can be served from the generated static
directory with all analytical views working.

### Phase 4 — Publish

- [x] Create and populate the Hugging Face dataset repository.
- [x] Verify remote paths, schemas, checksums, and representative downloads.
- [x] Add code/data licenses and citation files.
- [~] Complete full-history secret scanning and rotate credentials. Scans are
  complete with zero findings; retirement-time credential rotation remains.
- [ ] Make the GitHub repository public.
- [x] Configure and verify Cloudflare Pages production deployment.
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
| 2026-07-26 | Do not bake reference multipliers into source data | Directional ratios do not measure precision, recall, or time-varying error; presentation scaling must remain reversible |
| 2026-07-26 | Default plots to reversible reference scaling | User requested estimated traffic as the primary view; raw detector values remain selectable and source files remain unchanged |

## Next action

In the Cloudflare dashboard DNS records for `bay-bridge-traffic.com`, edit the
existing apex (`@`) record so its target is
`bay-bridge-traffic-archive.pages.dev` and keep it proxied. Do not create a
second apex record and do not delete the Pages custom-domain association. This
replaces only the production request route; it does not stop or delete the old
Tunnel or any local service.

After that single DNS edit, poll the Pages custom-domain status until active and
verify TLS, all eight routes, the expected site content, and the representative
data checksum on `https://bay-bridge-traffic.com`. Keep the old Tunnel and local
monitoring stack intact until the apex verification passes and their later
retirement is separately approved.
