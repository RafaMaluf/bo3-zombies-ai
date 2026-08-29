# Repository history policy

Gameplay screenshots are delivered from object storage and must not be stored
in Git. The repository history was rewritten before its public release to
remove every object below `maps/*/images/` from all relevant refs.

## Effect on older clones

History rewriting changes commit IDs, even when the source code in a commit is
otherwise identical. Existing clones still contain the retired binary blobs
and cannot safely pull the rewritten `main` branch.

Clones created before the rewrite retain the old objects and commit IDs. They
should be replaced with a fresh clone:

```bash
git clone https://github.com/RafaMaluf/zombies-ai.git
cd zombies-ai
cp .env.example .env
```

Local configuration can then be recreated from `.env.example`. Old `.git`
directories and branches must not be merged back into the cleaned history.

## Guardrails

`maps/*/images/` is ignored locally. CI also runs
`python -m scripts.check_repository_hygiene`, which rejects any tracked file
inside a map image directory and any image extension committed elsewhere
inside `maps/`.

New guide images are generated locally, migrated to object storage with
`python -m scripts.migrate_images all`, and represented in Git only by the
updated `assets/image-manifest.json`, guide references and provenance files.

## Asset verification

Object storage is the runtime source for gameplay images and can be verified
independently against the committed manifest with:

```bash
python -m scripts.migrate_images verify
```

This policy keeps the public source history focused on code, guides and
reproducible metadata while preserving stable asset references at runtime.
