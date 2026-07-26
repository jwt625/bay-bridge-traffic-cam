# Archive workspace

This directory contains additive, versioned archive metadata. Nothing here
replaces the active Prometheus or Grafana Docker volumes.

## Preservation rule

Do not delete, prune, recreate, compact, or modify the live Docker volumes.
Create and verify an immutable copy before attempting an exact-sample export.

The canonical local backup is stored in ignored, versioned directories under
`archive/source-*`. These directories must never be committed, uploaded
publicly, modified, compacted, or deleted. Exact exports are made from separate
copy-on-write workspaces under `archive/export-work-*`.

## Metadata inventory

`metadata-v1/` is a read-only capture of:

- Sanitized container identity and mount information
- Prometheus build information and runtime flags
- Prometheus TSDB status and block inventory
- Application-series label inventory
- Grafana health and dashboard JSON
- SHA-256 manifest

No container environment variables are captured.

Regenerate only into a new version:

```bash
uv run python scripts/capture_archive_inventory.py \
  --output-dir archive/metadata-v2
```

The script refuses to overwrite an existing directory.

## Publication boundary

Only sanitized metadata, exact application-metric Parquet exports, derived
analysis tables, and their checksums are eligible for public release. Native
Prometheus TSDB files and the Grafana database remain local/private because
they may contain operational metadata, users, or credentials.
