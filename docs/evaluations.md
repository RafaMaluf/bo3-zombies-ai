# Retrieval evaluations

`evals/queries.json` is the deterministic quality baseline for local search.
It contains 90 bilingual, player-style questions: 15 for each current map.
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
```

The command prints failed cases, enforces the thresholds stored in the suite,
and writes the complete result to `.cache/reports/retrieval-eval.json`.

When a map is added, add roughly 15 questions that cover setup, major quests,
equipment, side easter eggs, Portuguese and English wording. Expected results
must describe the correct guide, not merely copy whatever the current
retriever happens to return.
