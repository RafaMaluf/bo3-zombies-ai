# Repository history rewrite

Gameplay screenshots are delivered from object storage and must not be stored
in Git. On 26 August 2026, the repository history was rewritten to remove
every object below `maps/*/images/` from all relevant refs.

## Why a fresh clone is required

History rewriting changes commit IDs, even when the source code in a commit is
otherwise identical. Existing clones still contain the retired binary blobs
and cannot safely pull the rewritten `main` branch.

After the force-push, collaborators should archive any uncommitted work and
create a fresh clone:

```bash
git clone https://github.com/RafaMaluf/zombies-ai.git
cd zombies-ai
cp .env.example .env
```

Copy only the required local secrets into the new `.env`. Do not copy the old
`.git` directory or merge an old branch into the rewritten history. A branch
with valuable uncommitted work should be exported as a patch and reapplied to
the fresh clone.

## Guardrails

`maps/*/images/` is ignored locally. CI also runs
`python -m scripts.check_repository_hygiene`, which rejects any tracked file
inside a map image directory and any image extension committed elsewhere
inside `maps/`.

New guide images are generated locally, migrated to object storage with
`python -m scripts.migrate_images all`, and represented in Git only by the
updated `assets/image-manifest.json`, guide references and provenance files.

## Rollback

Before the rewrite, a complete verified Git bundle was created. Restoring it
recreates the previous refs and all removed blobs. Object storage remains the
primary runtime source and can be independently verified with:

```bash
python -m scripts.migrate_images verify
```

If the Git host must be restored from the bundle, clone the bundle into an
isolated directory, validate production, and only then replace the remote
history. Never mix rollback refs into the cleaned repository accidentally.
