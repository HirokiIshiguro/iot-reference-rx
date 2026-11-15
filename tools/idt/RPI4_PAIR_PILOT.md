# RPi4 / Windows RX72N Transport pilot

The normal CI includes `tools/ci/rpi4_transport_pilot.yml`, whose jobs are
selected only by the protected Transport profiles. The controller and its AWS
preflight require explicit manual starts; the paired Windows worker is selected
only in the associated downstream pipeline. Host configuration, permissions,
cost and recovery must be reviewed separately. No hardware success follows from
the mock tests or from the existence of this entry point.

The native controller creates the parent socket and takes a source snapshot
before native IDT starts. Each callback request starts a separate downstream
Windows job for that request. The job receives the parent pipeline ID, a new
private session ID and the expected source SHA; the job token stays on RPi #4.
The public-only standalone CI file tests a placeholder compile and response
without IDT, AWS or hardware. Both runners and Windows-to-RPi SSH are required.
The callback uses the parent socket under the dedicated user's private home.

The Windows worker uses `ssh -T` with `BatchMode=yes` and
`StrictHostKeyChecking=yes`, the dedicated Windows private key and a temporary
known-hosts file containing the previously verified RPi #4 host key. It does
not depend on the account's global SSH configuration. The private key and RPi
forced-command policy must be installed and verified separately. The requested command is exactly
`python3 -u "$HOME/.cache/idt-rx72n-pair/<session>/rpi4_pair_agent.py" attach <session>`,
where both session fields are the same decimal identifier. The forced-command
policy must accept this form without allowing an arbitrary shell.
`rpi4_ssh_gate.py` is a proposed forced-command entry that accepts only this
form, checks the session owner and permissions, and executes the session agent.
It is not installed or authorized by this repository change; the host owner
must review and place a root-managed copy before configuring the key.

The public smoke covers job dispatch, authenticated socket exchange, a real
placeholder-only compile and worker shutdown. The protected pipeline separately
compares the complete Windows/RPi source snapshot and validates the same-SHA
normal bundle. Neither check proves a hardware/AWS Transport run.

FRQ calls `rpi4_build_callback.py <source-path>` with exactly one argument,
`IDT_TARGET=rx72n-ethernet` and `IDT_SCOPE=transport`. Only changes to the two
test headers are accepted; the entire original file-hash snapshot is included
as provenance. Other modifications, SHA/target differences, malformed frames
and output hash mismatches stop the build. Windows gets only those headers and
provenance over the private SSH stream; no AWS/OIDC credential is transferred.
The returned application MOT, bootloader MOT and build manifest stay private.
The RPi uses the existing package and manifest helpers before the existing
flash verifier consumes the output. Other targets and IDT scopes are excluded.

The broker shuts down each Windows worker after its response, waits until the
per-request socket is gone and then removes that session. Failure or uncertain
process state retains the session for controlled recovery. The CI template
briefly takes the shared CC-RX lease while exporting its existing function;
each build then takes the same lease for its helper. The native worker job also
uses the existing GitLab resource group.

Open integration gates include the real Transport result, independent recovery,
the normal firmware end state and a fresh check of dedicated runner/bench
availability. A failed Windows build intentionally retains its workspace when
child process termination is not proven.

The Windows worker now starts its build helper in a Windows Job Object with
`KILL_ON_JOB_CLOSE` and without breakaway flags. The helper blocks on stdin
until the worker assigns it to the Job and sends `go`; it cannot take the lease
or invoke the compiler first. A controlled timeout or exception terminates the
Job and checks its active-process count. An unconfirmed stop fails closed and
retains the private workspace. Abrupt worker death closes the Job handle, but
cannot run Python cleanup: private files must be recovered separately. Local
dummy parent/child/grandchild tests cover normal execution, failed assignment,
timeout, and forced worker death on the dedicated runner; a separate public
build exercised the real compiler's successful path. Forced cancellation of a
real compiler was not tested. The reviewed worker SID and the accepted
containment evidence are fixed in source; an unconfirmed stop retains files for
independent recovery.

Local nonsecret tests:

```sh
python -B -m unittest tools.ci.tests.test_idt_rpi4_pair -v
python -B -m unittest tools.ci.tests.test_windows_build_job -v
```
