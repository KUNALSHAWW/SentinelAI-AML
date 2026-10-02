# Contributing

```bash
pip install -e ".[dev]"
make test lint          # pytest (incl. benchmark floors) + ruff
make evaluate           # regenerate documentation/BENCHMARK.md
make docs-sync          # refresh the GitHub-Pages copy of frontend/
```

Guidelines
- **Claims need evidence.** A new detector ships with unit tests *and* generator cases so the benchmark and ablation show whether it helps.
- Keep the engine deterministic and offline; LLM code must degrade loudly (`llm_status`, `warnings`) and may only *add* evidence.
- Don't weaken a regression floor in `tests/test_migrations_cli_eval.py` to make a change pass - explain the trade-off in the PR.
- Reference data (jurisdictions, typologies) must cite a public source.

Good first issues: see the roadmap in the README.
