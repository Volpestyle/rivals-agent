# Watchdog F1 delta re-review: 8593ef5 — LAND

Independent fit-review (Codex), 2026-09-27. **F1 is closed; no remaining findings in this reviewed delta.** This accepts the Job Object correction to the bd95447/b28d2e4 plumbing review. Earlier passing evidence stands for unchanged boundaries. Native video parity and measured intake peaks remain separate operational evidence.

The private unnamed job has KILL_ON_JOB_CLOSE and a non-inheritable job handle. Start creates the root suspended, assigns it to the job, retains its Process.Handle, and only then resumes it. Descendants inherit job ownership rather than relying on a surviving ancestry walk for cleanup. The committed wrapper checks ActiveCount after root exit and refuses success if descendants remain. Its finally block closes the job on failure and normal completion. Failure before successful start terminates the suspended root and closes the job; no user session/process or name-based process group is targeted.

## Independent verification

- Ran the actual `tests/test_admission_job.ps1` against the committed C# helper. Both real parent exit 0 and exit 1 cases passed: an owned sleeper descendant remained visible to the job after parent exit, then terminated on job close; an unrelated sleeper stayed alive during both checks. Test evidence: `C:/Users/volpe/AppData/Local/Temp/admission-job-test-36feea7f126b47689c339ffa50651d9e/`. Only processes created by these tests were cleaned up. A test-created unrelated venv-launcher descendant was also explicitly cleaned up afterwards.
- Ran 12 additional live-root close probes using the helper and a reviewer-created sleeping Python process. Every root exited after Dispose, and all 12 immediate exit-code reads were available. Evidence directory: `C:/Users/volpe/AppData/Local/Temp/fit-review-job-active-f0c480afb7044c28bec90ee06788a91f/`.
- Executed the committed wrapper's actual monitor/catch/finally block with an owned live sleeper and a synthetic resource refusal. The job closed, the root exited, and the captured receipt preserved `failure=synthetic resource refusal` with a non-null exit code. The termination exit code was 0, but the retained failure prevents the wrapper's final status path from claiming success. Evidence directory: `C:/Users/volpe/AppData/Local/Temp/fit-review-job-monitor-b759a6ab08e941b2ae3e6e75dae05947/`. Receipt output was intercepted in memory; no admission records were written.

## Exact scope

Committed SHA256 pins:

- run_intake.ps1: `85bdf75b760ce3bd165b54f88ad4d633fb8e261b1303da4c99b028cad3519874`
- OwnedProcessJob.cs: `fb192f46791a4ba1d9a952be30ce13d73774baea4742bba90b8100cd16a2074a`
- test_admission_job.ps1: `e79eb37a4ef81561917f789462cb7fdcdff97784c15eb61b36706cf8816210b2`

Helper and test working bytes match the commit. During review the owner added uncommitted wrapper scope for session -4 and an assemble command; these concurrent edits were not touched and are outside this verdict. The monitor probe used the committed 8593ef5 block loaded with git show, so its result does not depend on those edits.

No intake/decode/assembly, training, sealed payload reads, existing-process termination, owner-path edits or commits. The reported -6 evidence completion under the old wrapper and its null-exit failure receipt are **not reconciled or accepted here**; this review makes no retrospective exit-0 claim.
