# Guard correction before full execution

15 September 2026. No new full follow-up outcome has been produced.

Independent review of source `14259d7f26ee852de6139fef9c1ea361132c75d6`
found that execution sealing did not compare the current baseline-ledger and
qualification-seal hashes with the completed qualification receipt. A changed
cached historical count could therefore be accepted between qualification and
execution. The reviewer reproduced this on temporary copies, changing no real
source or evidence.

The original checkout and its qualification files are retained unchanged.
This successor changes only runner guards and regression tests, plus this
amendment. Before sealing, it verifies both parent hashes, verifies every
original qualification source in its preserved checkout, and requires all
scientific sources and PROTOCOL.md in the successor to match qualification
byte-for-byte. Only runner.py and test_guards.py may differ. The new execution
seal binds the corrected source and fresh independent review.

The 15 completed short runs remain reusable qualification evidence. Their
commands, sources, input/output hashes, receipts and original qualification
seal remain unchanged. There is no evaluator, policy, validator, analysis,
protocol, tolerance, seed, actor, hardware or statistical-design change.
No short or full run is repeated because of this guard correction.
