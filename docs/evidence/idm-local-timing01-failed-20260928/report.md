# IDM local-disk timing attempt 01

EXPLORATORY; incomplete. App ap-WWbF5IrxWLLlmy3jYFwEjh made one AppCreate (RUNNING event 2026-09-28T03:37:20.030960Z). The original reviewed v1.0.5 guard proved terminal teardown with zero containers; accounting bound $0.089506.

The owner callback failed after copying the first frames.json header: it passed a metadata dictionary to scripts/job_status.write, which accepts text or integer n/total. No frame arrays were copied and no training, checkpoint or throughput result exists. Fix: serialize the progress payload as text. A regression exercises the real writer with copy, loader and trainer payloads. The original frozen runtime remains unchanged.

44 relevant tests and Ruff pass. The lead approved one fresh same-envelope timing attempt: $0.997614 hold, aggregate timing allowance $1.09 inside the $25 lane. No full run until measured throughput plus a 30% margin yields a cost sent to the lead. Retain the input volume.

Lane terminal bounds are $9.642726068670252; storage allocation is separately $1.65. This is bounded accounting, not a reconciled provider invoice.
