# Bay Bridge Traffic Archive site

Static Observable Framework site for the historical traffic archive.

## Local development

From this directory:

```bash
npm install
npm run dev
```

Open `http://localhost:4173`. Port 4173 is deliberate so the archive preview
does not conflict with the existing local Grafana service on port 3000.

The current browser snapshot lives in `src/data/archive-v3/`; `archive-v1/` and
`archive-v2/` remain unchanged. Regenerate only into a new versioned directory
from the repository root:

```bash
uv run python scripts/prepare_static_site_data.py \
  --output-dir site/src/data/archive-v3
```

The preparation command refuses to overwrite an existing snapshot directory.
Update page attachments deliberately after validating a new version.

## Production build

```bash
npm run build
```

The disposable static output is written to `dist/`. The historical source
archive never lives in `dist/`.

## Data layers

- `archive-v3/` is the compact five-minute/half-hour browser snapshot.
- `validation-v1/` contains the third-party comparison tables and provenance.
- The public dataset release contains exact millisecond-resolution raw Parquet
  shards and these smaller derived tables.
- Native Prometheus TSDB and Grafana volume backups are deliberately not
  published because they may contain operational metadata or credentials.

Detector values are not ground truth. Count and flow plots default to a
reversible reference-scaling presentation; every affected page allows the user
to select raw detector values.
