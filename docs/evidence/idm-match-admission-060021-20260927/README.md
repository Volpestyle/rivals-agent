# Match -10 owner packet: pending independent review

Session `20260927T060021-195Z-150600-10` is registered `idm_train`.
The owner inspected all 175 supplied JPEGs in 22 labeled contact sheets;
all JPEG and evidence-input hashes match. Nine spans totaling 418.791649924
seconds are provisionally accepted; 51 remain rejected. This packet is not
an admission or permission to train.

Two unresolved machine proposals were rejected on visual evidence:

- **seg-021, 174.404454738–178.696121234 logger seconds:** every supplied
  sample shows the Past Lives / Defeated By replay UI. The replay shows his
  own Spider-Man HUD after an apparent fall/death, so an own-HUD positive
  does not establish live control. Reject the full span.
- **seg-057, 511.604441250–539.254440145 seconds:** final frame 64699 already
  dissolves into the round-transition screen while the HUD remains drawn.
  Reject the full span conservatively; earlier samples are own live play.

Independent review should check both findings and the adjacent accepted
boundaries (especially seg-017 before the self-replay). Other accepts show
own setup movement, traversal and combat. Setup countdowns and objective
banners over live play are retained. Several own-HUD reader misses in combat
appear to be effects or bonus-HP interference, not another camera.

Input replay across the nine accepts found no UI-key make, held-button3
plus settle overlap, unbound key/button or focus change. Mouse 1/2/4/5 are
bound gameplay controls (5 is melee). One scroll-up event at logger
348.5132994 seconds in seg-040 needs native event-neighborhood review.
No keyboard `4` thank-you press occurs in these accepted spans; the comms
clarification does not expand the gameplay vocabulary.

| Artifact | SHA256 |
|---|---|
| Evidence | `a9d97ffd85d06f6394024a74654179468a0af6cda231c19887aa26625b154673` |
| Owner verdicts | `c6b4906864328bcf4d1e7c2494e90e76ad5d1fd9274f6e2ee27b42f800a8c0f8` |
| Exact segment list | `139e2499a8ff1340398227b37665b962ef7ffaf87c3e0e6ba28a5b303d36d806` |
| Input replay audit | `75201c0cc8c4aaa44111045e9061bf7bb63ee66acfc37a91cfe8e2170a1a491a` |
| Media (provenance pin) | `0771473550e9752bd58c3505c16a8d44d1b31fcfc5dfd7553e1039a598c2471b` |

Evidence/owner files are in `data/human/sessions/20260927T060021-195Z-150600-10/`.
The exact segment list, input audit and local contact sheets are under
`data/admission-codex/review-10/`. All six guarded stages passed with exit 0
and no failure; evidence peaked at 429,498,368 bytes. Fresh proposal/evidence
use the reviewed held-button3 snapshot `4fe07b4b...`.
