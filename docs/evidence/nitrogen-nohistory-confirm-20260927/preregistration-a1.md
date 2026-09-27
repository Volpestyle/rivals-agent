# Preregistration amendment A1 — review timing, before results

Lead approved the confirmation on 2026-09-27 with this one change. The original
preregistration had already landed as `c28d039`; it remains immutable.

Base document: `preregistration.md`, canonical-LF SHA256
`825c3852d82ac0eb3e994bb64bf995e3babb7b14017da9d86cb8f564a9294295`.
All its scientific rules, six runs, source `5673de101a398fa661be581e3c1dd041391e2a61`,
judge SHA256 `6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32`,
image, cap and operational constraints stand unchanged.

Replace its sentence beginning “Before launch, the independent reviewer checks this judge” with:

> The independent reviewer checks this judge before anyone reads a confirmation result;
> the launch does not wait for it.

The independent reviewer is frame-review, a different model family. The lead authorizes
launch immediately after this amendment commits and its SHA is sent, with global AppCreate
spacing at least 15 seconds from modal-port's phase1-03 creates. Fits run in parallel with
phase1-03. No confirmation run/result exists at amendment time. Judge review is already
requested; it does not block launch. No confirmation metric or checkpoint result may be
read before review clears. Lifecycle, resource, exit and spend monitoring remain active.

The lead's weekend ledger reports round 3 up to $42.31, completed explore approximately
$35.15 plus this $20 authorization, and IDM small, within James's $150 ceiling.

This amendment's canonical-LF SHA is the `prereg_sha256` propagated to all six runs
and supplied to the judge; it transitively pins the unchanged base document above.
