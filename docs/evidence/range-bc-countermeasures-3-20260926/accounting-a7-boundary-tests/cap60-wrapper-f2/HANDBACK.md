# Frame-review F2 test-only follow-up

Four behavioural tests pass against the unchanged reviewed serial-runtime/safety.py (SHA256 0d140546fa17ef3cf4ca7e0006dbc5014cce3bd4ede2762be2a4cce89eb7d984).
$60 accepts; $60.01 refuses. Aggregate 69,120 seconds accepts; 69,121 refuses.
Isolated dollar-cap +one-cent and seconds-cap +one-second mutants each produce exactly one expected assertion failure. Logs and results.json retain the evidence. No textual substitution assertion is used to kill these mutants.

Run: python run_mutations.py from this directory. By default the reviewed cap60-wrapper packet is the sibling directory; SERIAL_SAFETY_SOURCE can select a relocated source for the individual test suite. The only mock relocates the synthetic Phase A anchor. Real hashing, ledger parsing, spend equality, projection and cap checks execute.

Mac Python 3.12.13. No paid work, product edits, corpus reads, or changes to the frozen cap60-wrapper packet. This test-only delta follows cap60 a7 commit 597b443155c0c863ae81cac99001750cbb1ef22c; it does not block the authorized fresh prefix.
