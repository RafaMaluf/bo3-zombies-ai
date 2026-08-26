# Retrieval evaluations

The deterministic retrieval baseline is split into three versioned suites:

- `evals/queries.json` contains 90 bilingual questions for the six original
  Black Ops III maps;
- `evals/chronicles_queries.json` contains 49 bilingual questions for the
  eight Zombies Chronicles maps;
- `evals/multilingual_queries.json` contains an explicit matrix of equivalent
  Portuguese, English and French questions.

No Groq key or model call is involved.

Each case can verify:

- inferred or active map;
- expected document at rank 1;
- all required documents within the first 10 chunks for multi-guide requests;
- expected section within the first 3 chunks;
- minimum number of attached images within the first 3 chunks;
- whether clarification was requested.

Run the baseline:

```bash
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_retrieval \
  --suite evals/chronicles_queries.json \
  --report .cache/reports/chronicles-retrieval-eval.json
python -m scripts.evaluate_retrieval \
  --suite evals/multilingual_queries.json \
  --report .cache/reports/multilingual-retrieval-eval.json
```

Run the same multilingual matrix against hybrid retrieval when Voyage is
configured in the local environment:

```bash
python -m scripts.evaluate_retrieval \
  --hybrid \
  --suite evals/multilingual_queries.json \
  --report .cache/reports/multilingual-hybrid-eval.json
```

The command prints failed cases, enforces the thresholds stored in the suite,
and writes the complete result to `.cache/reports/retrieval-eval.json`. Version
2 suites additionally report and enforce thresholds per language. Every
`group_id` must contain exactly one case for each `required_languages` entry,
and equivalent cases must share the same expectations.

When a map is added, include questions that cover setup, major quests,
equipment, side easter eggs, Portuguese and English wording. Expected results
must describe the correct guide, not merely copy whatever the current
retriever happens to return.

When adding a multilingual intent, add all required language variants in the
same group. Include generic clarification, canonical game terms, translated
paraphrases, short follow-ups and multi-guide requests. The matrix evaluates
retrieval only: answer generation and translation remain outside this suite.
