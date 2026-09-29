# Interval freeze — before new annotation or residual calculation

Frozen 2026-09-29 by idm-owner. DEVELOPMENT ONLY, VUH-1353.
Live `2026-09-25 20-06-20.mkv`: [120.000,160.000) s.
Replay `2026-09-26 11-10-08.mkv`: [89.390,129.390) s.
Each interval is 40 s. The placement uses the predecessor's published approximate -30.61 s offset solely to include the known arrivals near live 139.7/141.0 s. No new residual was computed before this choice.

Only these two released sources are allowed. Current sealed-denylist.v2.json was read; neither is listed. V-C/V-Q, both sealed Gate 2 pairs, test takes and DayMR/ReqMR remain excluded. No camera/model outputs inform annotation. Existing criteria unchanged: 30 timer anchors/span; segment offsets agree within 1 recorded frame; |free slope-1| <= 0.001; kill-feed residuals about their own median <= 2 recorded frames. Insufficient support fails qualification.

Annotation by the agent from native video crops is owner inspection; actual human verification must be identified explicitly and cannot be claimed merely because an agent viewed images.
