# First real batch failed before AppCreate

The native source-mount proof remains valid. The first real six-process batch exposed two v1.0.2 host-runner defects: concurrent billing queries exceeded the report rate limit; one admitted child passed fractional started=time.time() to the dashboard writer whose default updated time is rounded to seconds. That exception occurred before the runner try/finally and watchdog.

Owner reports five children refused before reservation. yaw-probe-20260927-02 remained RESERVED with rpc_count=0, app_id=null and allowance $0.480734. All six children exited 1; the 21:56:35.674Z authenticated inventory found every owned name absent and zero containers. No AppCreate occurred. Explore-policy owns unchanged accepted-library reconciliation and immutable failure evidence under probe-launch-01; modal-port owns the new source fixes/tests/review. Do not relaunch this frozen packet or treat the mount proof as a successful cloud execution.
