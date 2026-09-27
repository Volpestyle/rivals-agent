# Command/effect inference and when control ambiguity matters

Research, 2026-09-26. This extends the [event-evidence investigation](event-evidence.md)
with an executable observation model and a limited identifiability result.
It uses synthetic inputs only. It changes no training, admission or live code.

## Result

Under the explicit cooldown model below, press-only and repeat-on-hold controls
have identical possible cast sequences when the cooldown is at least two bins.
With an unrestricted unknown command policy, even perfect cast observations
cannot identify which mechanism produced them. Nevertheless, a common pulse
sequence produces any feasible target cast sequence under both mechanisms.

Thus **unidentifiable command semantics need not imply unidentifiable successful
behavior**. The proposed research must demonstrate a task-relevant ambiguity,
not merely a better reconstruction of the demonstrator's hidden buttons.
This is a derived special-case lemma, not a claim of a new general theorem.

## Exact inference reference

Run the standalone standard-library probe:

```powershell
uv run --no-sync python docs/research/executable-imitation/command_effect_probe.py
```

The [implementation](command_effect_probe.py) separates:

1. Held control bits and rising edges. A supplied two-state Markov prior gives
   the probability of a held bit conditional on the previous bit.
2. Successful casts. A supplied mechanism accepts rising edges only, or fires
   whenever held and ready. A fixed cooldown advances through releases.
   Failed inputs are not buffered.
3. Visible reports. Each cast can produce one report after a fixed delay.
   A supplied visibility probability may depend on the held bit at report time.
4. Evidence. Distinct intervals constrain report times through injective
   matching. Arbitrary alternative match assignments are not extra observations.

The DP state contains previous held bit, cooldown, pending delayed casts and
the canonical earliest-deadline interval-match state. Its values accumulate
probability and command/onset/cast moments. Different stochastic command and
visibility histories contribute probability; alternative witnesses that the
same report path matches the same evidence do not multiply its weight.

The `complete` flag here means the entire report sequence is covered by the
given intervals: extra reports are forbidden. This is **not** the repository's
`complete` cast-window flag and must never be substituted for it. In incomplete
mode, extra reports are permitted; no positive intervals imposes no evidence.

For a specified predicate E over report sequences, the code exactly computes
P(E) and P(command bit | E) under its supplied model. It does not model how an
annotator or HUD reader chooses intervals, so this is not automatically the
likelihood of a real annotation record. There is no learned missingness model,
unknown latency distribution, false-positive detector model, camera motion,
pixel encoder or policy feedback through changing images.

## Verified numerical examples

Use three bins, cooldown two, no delay, perfect visibility, independent held
bits with probability one half, and exactly two reports at bins 0 and 2.

| Supplied mechanism | Evidence probability | Posterior held bits | Expected press onsets |
|---|---|---|---|
| Repeat while held | 1/4 | (1, 1/2, 1) | 3/2 |
| Rising edge only | 1/8 | (1, 0, 1) | 2 |
| Equal prior mixture of mechanisms | 3/16 | (1, 1/3, 1) | 5/3 |

Both mechanisms explain two casts. The mixture's posterior probability of repeat
is 2/3, but this depends on the stipulated command prior. It is not a discovered
mechanic or proof that repeat is true. A certain held path (1,1,1) produces two
casts with one onset under repeat, and the inference code accepts that path.

With one bin, prior hold probability 1/2 and known cast visibility 1/4, a complete
record with no reports gives posterior hold probability 3/7. Treating absence
as a known release would be wrong. If completeness is unknown and there are no
positive intervals, the posterior remains 1/2. Delayed reports similarly
constrain earlier commands rather than the command at the report's timestamp.

The DP and an independent oracle agree exactly, using rational arithmetic, on
**2,624 cases**. These exhaust all interval multisets of size zero through two
for horizons one through three, crossed with two mechanisms, periods one/two,
delays zero/one, two visibility profiles, two completeness modes and initial
cooldowns zero/one. The oracle enumerates command paths, report subsets and
injective assignments; it uses last-cast times rather than countdown states.
All command marginals and onset/cast moments agree, not just the evidence mass.
These small finite checks verify the implementation on those cases; they do
not establish that any supplied mechanism describes Marvel Rivals.

## Cooldown equivalence lemma

Assume a discrete horizon T; binary held-state commands u_t; initially released
and ready; cooldown P >= 2; at most one cast per bin; instantaneous, reliable
command delivery; no other cast conditions or control effects. A cast at t makes
the next allowed cast time t+P. In mechanism R, holding when ready fires. In
mechanism E, a fresh rising edge when ready fires. Non-ready inputs are ignored.

**Claim 1.** The output language of each mechanism is exactly all binary cast
sequences whose consecutive cast times are separated by at least P bins.

Proof: necessity follows from the cooldown. For sufficiency, take any sequence c
with that separation and set u_t=c_t. Every nonzero command has a preceding
release (or is the initially released first bin), since P >= 2. Every such edge
also occurs after the cooldown. It therefore generates exactly c under either
mechanism. No zero command produces a cast. This proves both inclusions.

**Claim 2.** Without restrictions on the unknown command policy, every probability
distribution over feasible cast sequences is realizable under either mechanism.

Proof: draw a feasible sequence with that distribution and use the construction
u=c. Equivalently, factor its finite joint distribution into causal conditional
command probabilities. Both mechanisms then have the same cast distribution.
The same conclusion holds after a shared observation channel depending only on
casts, including delays or missing reports. It need not hold if a known channel
also exposes held state, or if other pixels reveal independent control effects.

Consequently, more passive cast-only data cannot universally identify E versus R
in this model class. Different likelihoods under a fixed command prior, as in
the table, do not contradict this: Claim 2 allows the unknown policy to differ.
This is a nonidentification statement over a class, not a claim that every
particular constrained policy family is indistinguishable.

**Claim 3.** The same map u=c is a common causal right inverse. If success depends
only on producing a feasible requested cast sequence, identifying E versus R
is unnecessary: pulses have zero task loss under both.

This is the key control consequence. Calibration can matter if held actions
have other effects, onset costs differ, command latency or pulse registration
is uncertain, or the target objective includes constraints not in c. Those are
additional hypotheses to establish, not consequences of cast ambiguity alone.

The script enumerates 4,088 command words across 36 horizon/period combinations
(T=1..9, P=2..5), checking both output-language equality and the common pulse
realization. At P=1 it checks the assumption boundary: repeat can emit (1,1),
while the binary held-state rising-edge model cannot. The written proof covers
arbitrary finite horizons under its assumptions; enumeration checks its coding.
Sub-bin taps and releases require a finer command alphabet and a separate model.

## What would resolve a consequential ambiguity?

If the task actually requires knowing repeat semantics, a known held command
through the next ready time separates the two synthetic models: R casts again,
E does not. Paired demonstrations containing such a command can suffice;
new interaction is not always necessary. With incomplete observation, a missing
second report is not decisive. Reliable detection or an explicit visibility
model and repeated evidence would be needed. This note authorizes no live probe.

Current [kit documentation](../../spiderman-kit.md) still marks LT auto-repeat
unknown; the [controller lane](../../lanes/l4-controller.md) reports an 8 ms
registered press but says hold repeat was not measured. These are target-pad
facts and do not establish source keyboard/mouse semantics. Nor does the lemma
justify applying isolated pulses to continuous swing, movement or camera control.

## Novelty audit and research consequence

The probabilistic construction is a finite-state latent-variable model, not a
new inference paradigm. [PLUNDER](https://www.joydeepb.com/Publications/ral2024_plunder.pdf)
already infers latent actions through a supplied observation model. Weighted
automata distinguish string weights from path weights; [Mohri and Riley](https://cs.nyu.edu/~mohri/pub/wdis.pdf)
study disambiguation. Our Boolean matching witnesses and stochastic emission
histories have different semantics: collapsing the former must not discard the
probability of the latter. This probe supplies a small reference, not an
improvement over their general algorithms.

[Schur's 2026 demonstrator-diversity paper](https://arxiv.org/html/2603.17577v1)
provides an important positive comparison: under shared Markov dynamics,
demonstrator exclusion, sufficient policy diversity and rank assumptions,
action-free observations identify latent transitions up to permutation.
Our unrestricted hidden-control example does not refute that result. Combining
DayMR, ReqMR and James does not establish its assumptions: device/settings,
observation channels and sufficient state information need checking.

The next scientific question is narrower and stronger: **which task quantities
remain learnable under uncertain control semantics, and when does extra paired
data improve attainable behavior rather than merely select a hidden transcript?**
Study that boundary before fitting a joint latent model. Any claimed new method
must beat a common feasible controller where one exists. A new impossibility
example alone, or reimplementing latent inference, is not yet doctoral novelty.
