# Accounting Amendment 8: extraction reservation

Lead-approved pre-result amendment, 2026-09-27. Land now; independent review follows,
per dd2b978 and the lead's explicit time-box decision. This packet is not a launch
approval and does not write an approval ledger.

Only `EXTRACTION_HOLD_SECONDS` changes, from 2220 to 2320, in the owner and fanout
copies of `cm3_budget_plan.py`. Work allowance is 1900 seconds, startup 300 and
cleanup 120. Caps remain 69,120 seconds and $60, rate remains $0.00071784/second;
forecast, admission, timeout and settlement formulas remain unchanged.

## Rationale and measured inputs

Modal-port's `handoff/modal/budget04-hold-diagnostic/guard-diagnostic.json`
(SHA256 `d3fb6419b146a38b0908d8f7e9957d65a765ab0facd18e2b2e5fdb22e74a233e`),
copied here byte-for-byte, documents smoke05's extraction rate of about 262.758
views/second. Extracting 173,698 frames through both views takes 1322.111673 seconds.
The required allowance is `1.25 * (1322.111673 + 172) + 300 + 120 = 2287.639591`
seconds, exceeding the old 2220-second hold. The approved 2320-second hold covers it.
The source packet manifest is
`c4923cf040e6530d12e39a507aa87fa771bdf240e15c4240ae93d256fd3f8117`.

Using canonical accounting's 34 settled attempts (26,317 seconds / $22.11141756),
the unchanged Writer forecasts **64,004.017956 seconds / $52.913912**, leaving
5,115.982044 seconds / $7.086088 below the hard caps. The lead's approximate
64,104-second figure includes an extra 100 seconds; increasing a reservation does
not add 100 seconds to the measured-work eligibility formula. The informational
sum of maximum future holds does increase by 100 seconds.

## Integration and closure

Use either new plan copy as the `cm3_budget_plan.py` overlay. Both LF blobs have
SHA256 `1b76ee9707580beec7bb71f9b7b766bfb0b8f3a42ea849e7f767697a87ef59af`.
There are no other changed overlay files. Reuse the unchanged Writer and its
accounting/timeout dependencies from `../accounting-a7/owner/`.
Production `cm3_run.py`, production `cm3_accounting.py`, and common context are
unchanged; their hashes are recorded in `unchanged-closure.json`. This amendment
does not change the capture06 through smoke05 owner code/context closure.
Modal-port regenerates budget04/extract02 allocations from these new plan bytes.
Earlier evidence, ledger and approvals remain untouched.

## Verification

`python -B -m pytest docs/evidence/range-bc-countermeasures-3-20260926/accounting-a8/test_a8.py -q -p no:cacheprovider`

Five tests pass. They execute the unchanged real Writer forecast, budget and
allocation functions on smoke05 numerical metadata, isolate historical receipt
and ledger reads, demonstrate the old hold's refusal, verify the new forecast
fits both caps, and retain refusal on forecasts above either cap. A byte comparison
proves the single-constant delta and identical owner/fanout copies. Source hashes
for the extracted numerical fixture are in `budget04-numbers.json`. These are
arithmetic regression tests, not fresh authentication or real-data runs.
