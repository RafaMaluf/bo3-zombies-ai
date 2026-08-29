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

`build` validates new or changed local files, creates deterministic variants
under the ignored `.cache/r2-assets` directory, and writes the committed
manifest. Existing records can be rebuilt from the manifest after their local
binaries have been removed.
`upload` compares remote metadata before every write, so repeated executions
do not create duplicates or rewrite matching objects. `verify` checks every
expected object against its size and hashes and exits non-zero for missing or
inconsistent objects. `python -m scripts.migrate_images all` runs all three
operations.

The Docker build explicitly excludes `maps/*/images/**`; it packages only the
guides, asset manifest and application code.

## Storage portability

Asset identity is independent of the storage provider. Object keys are derived
from content hashes, and the complete mapping is kept in the versioned
manifest. The Git repository therefore contains the metadata required to
verify the collection without storing gameplay image binaries.

The current public origin is Cloudflare R2, but migration only requires copying
the existing keys to another S3-compatible bucket and changing
`ASSET_BASE_URL`. Guide references, image IDs and retrieval indexes remain
unchanged. Because delivery is public, anyone with an object URL can download
that asset; write access remains protected by the migration-only credentials.
