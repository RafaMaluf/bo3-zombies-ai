# Guide ingestion

The ingestion tool turns one JSON manifest into a validated map directory. It
is intended for adding Zombies Chronicles guides without repeating the old
manual process for every screenshot.

## What it does

For every document in the manifest, the tool:

1. downloads the source page with redirects and bounded retries;
2. isolates the configured article element and removes page chrome;
3. converts headings, paragraphs, lists, tables, quotes, and images to Markdown;
4. rejects tiny icons and images outside the configured URL filters;
5. rotates and resizes images to a maximum of 1600 pixels;
6. encodes screenshots as WebP and deduplicates them by SHA-256;
7. writes `index.json` and a `sources.json` provenance ledger;
8. decodes every generated image and validates the staged knowledge base;
9. installs the map atomically only after validation succeeds.

An existing map is never overwritten by default. `--replace` first moves it to
`.cache/ingestion/backups/`.

## Manifest

Copy `ingestion/manifests/_template.json` and create one entry per source page.
A document entry supports:

- `path`, `category`, and `summary`, which are copied into `index.json`;
- `source_url`, the original guide page;
- `title`, an optional Markdown title override;
- `content_selector`, a CSS selector for the actual guide content;
- `remove_selectors`, CSS selectors for ads or unrelated widgets;
- `include_image_url_patterns` and `exclude_image_url_patterns`, regular
  expressions applied to resolved image URLs;
- `min_image_width`, `min_image_height`, and `max_images`.

When `content_selector` is empty, the importer tries `article`, `main`,
`[role=main]`, and `body`, in that order.

## Commands

First stage and inspect a map without touching `maps/`:

```bash
python -m scripts.ingest_map ingestion/manifests/nacht_der_untoten.json --dry-run
```

Install a new map:

```bash
python -m scripts.ingest_map ingestion/manifests/nacht_der_untoten.json
```

Replace an existing map while preserving a backup:

```bash
python -m scripts.ingest_map ingestion/manifests/nacht_der_untoten.json --replace
```

Generic extraction is deliberately only the first draft. Before committing,
review the generated facts, split an oversized guide when useful, improve
section headings, and remove images that do not help answer a player.
