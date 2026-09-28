# V is the recorded melee binding

Frame-review pointed out, and admission-codex verified, that this session's
`motor-settings.json` binds melee to `["key:47:0", "mouse:5"]`. Its binding
note explicitly identifies these as V and Mouse 5, citing the settings look
and lead decision. Motor record SHA256:
`8c5f2318a1dd79e8dbe2257f15a2f986f7d174bdcc975fceee55f7892899ca1a`.

The owner input audit's fixed virtual-key list omitted V (VK86), and the
owner searched the later saved-settings evidence without consulting this
explicit motor binding. The resulting "unidentified" classification was
an owner audit error. This follow-up corrects that interpretation; the
already pinned owner packet and audit remain unchanged.

The press at logger 170.3793789 seconds in seg-016 is a recorded melee
binding, not a new action-vocabulary entry. Frame-review has released the
decoder slot after 2,482 native frames and is still checking that press's
native neighborhood. No final independent verdict or acceptance is implied
by this metadata correction.
