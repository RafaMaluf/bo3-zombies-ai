# Retrieval evaluations

The deterministic local-search baseline is split into two suites:

- `evals/queries.json` contains 90 bilingual questions for the six original
  Black Ops III maps;
- `evals/chronicles_queries.json` contains 48 bilingual questions for the
  eight Zombies Chronicles maps.

No Groq key or model call is involved.

Each case can verify:

- inferred or active map;
- expected document at rank 1;
- expected section within the first 3 chunks;
- minimum number of attached images within the first 3 chunks;
- whether clarification was requested.

Run the baseline:

```bash
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_retrieval \
  --suite evals/chronicles_queries.json \
  --report .cache/reports/chronicles-retrieval-eval.json
```

The command prints failed cases, enforces the thresholds stored in the suite,
and writes the complete result to `.cache/reports/retrieval-eval.json`.

When a map is added, include questions that cover setup, major quests,
equipment, side easter eggs, Portuguese and English wording. Expected results
must describe the correct guide, not merely copy whatever the current
retriever happens to return.
