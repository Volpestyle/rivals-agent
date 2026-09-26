# Whole-session intake, 2026-09-25 recordings (VUH-1359)

Landed with this folder: the validation take **20260925T212646-322Z-49728-6** (val, 15.5846 min, reported beside the
train headline and never added), and two training takes, **20260925T203745-207Z-49728-2** (45.9781 min; a Timed Practice
round cut by the new `timed_practice` rule) and **20260926T045729-166Z-79780-1** (10.2599 min, the 23:57 take). Train
headline 150.42 of 180 over 9 sessions. Every session has its owner hand-back and an independent per-session review
(admission-review, Codex); the intake code changes (the `gate2` sealed split, the `timed_practice` cut and its
end-bracket fix, the `settings_change` cut, per-session `MOTOR_STATEMENTS`, and category-disjoint registry checks) were
reviewed in `review-intake-0926.md` and its delta re-review `review-intake-0926-2.md`. A 1 fps native banner sweep found
no Timed Practice outside the existing cut in any of the three sessions (addendum in `admission-owner-final-28.md`).
The validation take was named after recording and recorded second in its sitting (its row in the recording log). The
late 22:59 main-account take is not in this landing; it follows its own session review.

| File | sha256 |
|---|---|
| `admission-owner-decision-203745-timed.md` | `2b454e5fbec226def557f06f14ee3fc5453e05ecb7125e2f7d51c4e021f496e1` |
| `admission-owner-final-21.md` | `7a5ed05f5ef37c17f8890d57c73a1ff3e7a7e3a7f27df08b248773de3c91c0c9` |
| `admission-owner-final-22.md` | `9882c30931d8170960a4baeaf1759c62904c2e0cc285dd07d8e6619cf012a860` |
| `admission-owner-final-23.md` | `70c8334db4148da25a8c3b2452af220e2c88165157c0e4844609bb07b0d22393` |
| `admission-owner-final-24.md` | `5c64d041dd01b5a7546b8164a46e66e8263da07ad36be38bbfe6b00d6e3f030c` |
| `admission-owner-final-26.md` | `b988db1ed14648e8e62b101f448ad9a984fccb70578579bb07820937c5072660` |
| `admission-owner-final-27.md` | `9845788a9f5060c05c583ad42657541641d287c5d58fe3d8bd5b6b234cd15536` |
| `admission-owner-final-28.md` | `9207f3050c95df82d6916173223218f438301515ea96d8a12db2e948f65ddd13` |
| `arrivals-0925-late.md` | `3538713c020498feeed5ca800531c5e4c3ffd2a08fcda38f9e3db80ef3b53806` |
| `arrivals-0925.md` | `b3552d88cdc63679008a10af5e92541e7eff0fe3f2847fb16465c5739e43cb61` |
| `review-intake-0926-2-work/audit-run.txt` | `1d345429642158cc73efd4bae384864ecaf3a7df78ec98a0a2c960224f167ffb` |
| `review-intake-0926-2-work/audit.json` | `c16b1bd00ee16594e1cc7580cf4e21e3478b7d86a9a11d543562cf314c292b6d` |
| `review-intake-0926-2-work/audit.py` | `ae7d2febd49cdd85d4b2abbceca457ae6d7e8ba54f5dbff6da4e6676cab62553` |
| `review-intake-0926-2-work/cross-category.json` | `9de7eda3d6979140d8f880c4ffe0a33738571d157ab34ddb2932754a9896aa36` |
| `review-intake-0926-2-work/delta-checks.json` | `1bce44c1906755c4fad9b0502d62f85487663edbc3ef1077fea29d83ad7ca327` |
| `review-intake-0926-2-work/delta_checks.py` | `70d37ff01e6a9e6a69e08da824e1797de87a57163d917e7ce2a66caae868b9f4` |
| `review-intake-0926-2-work/finish.py` | `e25573749650abd59ae7b8eb310831bcb1565cb720bc8d0b0df3289372e1ce2f` |
| `review-intake-0926-2-work/gate2-artifact.jsonl` | `ad7109effa87eeea83463b9d55effa6cbb6c687b6100a275237a9fdb806abe39` |
| `review-intake-0926-2-work/gate2-reg.json` | `97d1a69b4019d1b88ec40ba6474f4a22433c5a253c61e8412b904780fd95260d` |
| `review-intake-0926-2-work/relocation-run.txt` | `c3149561b0207e9647916debb7298b0540562d0ea4b49a2607512c58bdc2b7da` |
| `review-intake-0926-2-work/relocation_repro.py` | `0d4b61c05db9f68397547b88cd26ddd30752c9b52ce4272ccb924fc7c885f4d7` |
| `review-intake-0926-2-work/synthetic-registry.json` | `7ea22d43ed8ec25ed65a9a7ade010bb94fad9abdf6e509bf89f4157e645a6388` |
| `review-intake-0926-2.md` | `c26426fcd75d6d2fa63ac549b13de69bacf4d16fe98a0431829d5d541f8058a3` |
| `review-intake-0926-work/audit.json` | `3c1d230c9a42d7a679257e3bf8819eb5150a6b57b070efaff83d5ae2287d7009` |
| `review-intake-0926-work/audit.py` | `ae7d2febd49cdd85d4b2abbceca457ae6d7e8ba54f5dbff6da4e6676cab62553` |
| `review-intake-0926-work/cross-category.json` | `9de7eda3d6979140d8f880c4ffe0a33738571d157ab34ddb2932754a9896aa36` |
| `review-intake-0926-work/finish.py` | `9342c1a15b7e24aa390e561d9f00003960c4b1522a31f0bf860c93a818e946e0` |
| `review-intake-0926-work/gate2-artifact.jsonl` | `be23fe3613448360ff66afad5384741d885aa8119fb85f7051abfebb58428a50` |
| `review-intake-0926-work/gate2-reg.json` | `1f3304cd7c9c062a243cb5b300b2e1468b3cc13b9b304759bc436863694b987e` |
| `review-intake-0926-work/relocation_repro.py` | `0d4b61c05db9f68397547b88cd26ddd30752c9b52ce4272ccb924fc7c885f4d7` |
| `review-intake-0926.md` | `af85359c898730380761ae960c17a2af882f68b22c460d3cdf16e0f00025b03b` |
| `review-session-045729.md` | `903bc324de163f7bdb8ec011ef5387b70576f45d69a37c8f1d96e90d7c399114` |
| `review-session-045729.verdicts.json` | `e80c10ca5bd747a6700e29e406c48ab32c5bf09d3d83e7a1e3a3509ef9d8353e` |
| `review-session-203745.md` | `a5cc09c2fc5bb52ed0eedf7ff1486aa6a208ab90be4568c73fddd1f0627f029a` |
| `review-session-203745.verdicts.json` | `916ea4bf20cba89b56c711e75b05c0d4c453e4e20c8dd9d0d8ab643146b4c74e` |
| `review-session-212646.md` | `fcc7197343571ce0a28916d26513dc6d4e5b4148860df0594496f8e0832d3012` |
| `review-session-212646.verdicts.json` | `7c47d6afac6c439298ff64ff755877ce2ebfccabef52021bdae84d12e34fb9bf` |

**Second landing (2026-09-26): the late 22:59 take, 20260926T035932-508Z-63684-14 (train, 30.1522 min), on James's main
account.** Admitted under the lead's option B: effective bindings equal on every pressed key, Shift and Caps Lock shown
swinging on native frames, normal regime, the settings menu at its start and a ~9 s Timed Practice round cut, and the
main account's yaw gain measured on its own turn take (calibration 20260926T060921-977Z-60612-1: mean +0.064 %; the slow
turn +0.159 % missed the scripted +-0.08 % check, and "equal" is the lead's decision using 030045's +-0.25 % slow-class
tolerance). Its independent review matches all 35 owner decisions. Train headline 180.57 of 180 over 10 sessions; val
15.58 beside it. A 1 fps banner sweep of all ten admitted sessions found Timed Practice only inside the two cuts.

| File | sha256 |
|---|---|
| `review-session-035932.md` | `78b22e91b932116bd2f79e3419f560d217b7a5c88aa08386087197f86b9f69b7` |
| `review-session-035932.verdicts.json` | `88afc54b6534bf3a37d3ad570c42acd6616f083aac388b276878e2ca9b05a03e` |
| `admission-owner-final-25.md` | `431b95ead635525ca9318410faabaecd9be87ca744aa8ce66df6e8273faa3c10` |
| `admission-owner-final-25.held.md` | `e8e6c448ef09fc0bbf67428287f226c43e9860ec6851c7f8dce911985a89adde` |
| `admission-owner-final-29.md` | `98668c820a2ee3a230db4964a46af1eadb55a56919f7043ada03311eda6b535f` |
| `admission-owner-decision-late-account.md` | `9009449bc1504fd24a1dcf4b8b1e373507054c86cb34d0512bc96f4327f5f336` |
| `admission-owner-decision-late-gain.md` | `45b3d19bbc9ce2501a452f7ff4c05cfaa81cafa6c9a59eff2d0fcbf0236365d0` |
