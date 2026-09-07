# Public Analysis

- `verify_statistics.py` independently recomputes the paired E1, E2c and E2d Student-t summaries, the E2b factorial contrasts and the E2c→E2d sign reversal.
- `generate_figures.py` creates all committed figures from compact public CSV files.
- `validate_publication.py` checks required structure, JSON parsing, evidence checksums, local Markdown links, privacy patterns and exclusion of raw array files.

These scripts do not import or invoke the private evaluator and cannot run a scientific trace experiment.
