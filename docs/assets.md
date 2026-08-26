# Image asset storage

Kronochat keeps image metadata and provenance in Git while serving gameplay
image binaries from Cloudflare R2. The public application never receives R2
credentials.

## Layout

`assets/image-manifest.json` is the canonical, versioned mapping from the
stable `img_*` IDs used by the knowledge base to content-addressed objects:

```text
images/v1/<original-sha256>/original.<extension>
images/v1/<original-sha256>/full.webp
images/v1/<original-sha256>/thumb.webp
```

The original object preserves the exact source bytes. `full.webp` is bounded
to 2560 x 2560 at quality 88, and `thumb.webp` is bounded to 960 x 640 at
quality 80. Object keys are immutable and responses use a one-year immutable
cache policy.

The manifest records hashes, dimensions, MIME types, byte sizes, captions,
guide locations and source URLs when provenance was available. It contains no
credentials.

## Runtime configuration

Production only needs the public delivery base URL:

```dotenv
ASSET_BASE_URL=https://your-public-r2-domain.example
```

The API returns direct `thumbnail_url`, `full_url` and `cover_image_url`
values. The legacy `/media/{image_id}` route redirects to the same immutable
object. If `ASSET_BASE_URL` is empty and local files exist, `/media` retains
the deterministic local-file behavior used by development and tests.

R2 write credentials are migration-only and must never be configured in the
frontend or committed:

```dotenv
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET_NAME=krono
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
```

## Build, upload and verify

Install development dependencies, then run:

```bash
python -m scripts.migrate_images build
python -m scripts.migrate_images upload
python -m scripts.migrate_images verify
```

`build` validates local files, creates deterministic variants under the
ignored `.cache/r2-assets` directory, and writes the committed manifest.
`upload` compares remote metadata before every write, so repeated executions
do not create duplicates or rewrite matching objects. `verify` checks every
expected object against its size and hashes and exits non-zero for missing or
inconsistent objects. `python -m scripts.migrate_images all` runs all three
operations.

The Docker build explicitly excludes `maps/*/images/**`; it packages only the
guides, asset manifest and application code.

## Backup, ownership and provider migration

The R2 bucket is owned by the Cloudflare account that created it. Keep billing
alerts enabled and review the current R2 free-tier limits in Cloudflare's
official pricing documentation. Public image delivery means anyone who knows
an object URL can download it.

Until the separate Git-history cleanup is complete, the current repository is
an additional local source for the originals. Before that destructive cleanup,
retain an offline archive or export the bucket with an S3-compatible tool such
as `rclone`.

To migrate providers, copy every key without renaming it to another
S3-compatible bucket, verify it against the committed manifest, and change
`ASSET_BASE_URL`. No guide, image ID or retrieval index needs to change.
