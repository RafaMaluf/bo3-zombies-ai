# Knowledge base structure

Each map has its own directory under `maps/<map_id>/`.

```text
maps/
  der_eisendrache/
    index.json
    general.md
    main_ee.md
    images/
      main_ee/
        teleporter_ready.jpg
```

## `index.json`

The map index contains:

- `map_id`: stable `snake_case` identifier;
- `display_name`: name shown in the interface;
- `release_order`: optional display order; maps without one appear last;
- `aliases`: names and abbreviations used by players;
- `summary`: short map description;
- `files`: every searchable Markdown guide.

Each file entry requires `path`, `category` and `summary`. Validation fails if
a Markdown guide is missing from the index or an indexed path does not exist.

## Markdown

Use `#` for the document title and `##` for independently retrievable sections:

```markdown
# Rocket Shield

## part 1 - first courtyard

Description and exact locations.

Related images:
- images/shield/part_1_location_a.jpg
- images/shield/part_1_location_b.jpg
```

During ingestion and curation, source images live in the map's `images/`
directory. File names must not contain spaces. After the object-storage
pipeline runs, local binaries are ignored and only
`assets/image-manifest.json` is versioned. Supported formats are:

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`
- `.gif`

There is no need to repeat a complete gallery at the end of a guide. The
loader supports legacy galleries, but placing image references next to the
relevant section produces more precise answers.

## Validation

After importing or editing content, run:

```bash
python -m scripts.validate_kb
python -m pytest
```

The validator detects:

- invalid indexes;
- missing or unindexed documents;
- paths that escape the map directory;
- broken image references;
- orphaned images;
- duplicate IDs.

## Provenance

Every imported source should retain its origin URL. This makes later reviews,
corrections and asset replacements reproducible.

For new maps, use the pipeline described in [ingestion.md](ingestion.md). It
creates `sources.json` with each page URL and hash, plus the URL, dimensions
and hash of each imported image. See [assets.md](assets.md) for publishing new
assets without adding their binaries to Git.
