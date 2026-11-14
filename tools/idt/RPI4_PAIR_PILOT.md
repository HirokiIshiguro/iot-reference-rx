# RPi4 / Windows RX72N Transport pilot

This is an integration draft. `tools/ci/rpi4_transport_pilot.yml` is not
included by the normal pipeline and its workflow rejects every pipeline.
Windows execution remains disabled in source until a reviewed dedicated
execution SID and verified compiler cancellation are configured. No IDT,
AWS, compiler or hardware success follows from the mock tests.

The intended Linux launcher creates the pair session before starting Windows,
then takes a source snapshot before native IDT starts:

```sh
python3 tools/idt/rpi4_pair_agent.py prepare "$CI_PIPELINE_ID"
# Save rpi4_pair.snapshot(Path(CI_PROJECT_DIR)) as private JSON before IDT.
python3 tools/idt/rpi4_pair_agent.py wait-ready "$CI_PIPELINE_ID" --seconds "$PAIR_READY_SECONDS"
export IDT_PAIR_SOCKET="$HOME/.cache/idt-rx72n-pair/$CI_PIPELINE_ID/build.sock"
export IDT_PAIR_BASELINE=/path/to/private/baseline.json
export IDT_PAIR_BUILD_SECONDS="$PAIR_BUILD_SECONDS"
# Existing IDT_PROVENANCE_FILE and private IDT_RUNTIME_DIR must be set too.
```

FRQ calls `rpi4_build_callback.py <source-path>` with exactly one argument,
`IDT_TARGET=rx72n-ethernet` and `IDT_SCOPE=transport`. Only changes to the two
test headers are accepted; the entire original file-hash snapshot is included
as provenance. Other modifications, SHA/target differences, malformed frames
and output hash mismatches stop the build. Windows gets only those headers and
provenance over the private SSH stream; no AWS/OIDC credential is transferred.
The returned application MOT, bootloader MOT and build manifest stay private.
The RPi uses the existing package and manifest helpers before the existing
flash verifier consumes the output. Other targets and IDT scopes are excluded.

After the native controller and its build callback have stopped, call
`rpi4_pair_agent.py shutdown "$CI_PIPELINE_ID" --seconds <budget>`, wait for
the Windows worker to finish, and then call `rpi4_pair_agent.py cleanup
"$CI_PIPELINE_ID"`. Failure or uncertain process state retains private files
for controlled recovery. The Windows worker blocks in stream reads while idle;
it does not hold the CC-RX file lease then. The initial CI template briefly
takes that lease while exporting its existing function; each build then takes
the same lease for its helper. GitLab resource_group does not cover the idle
worker in this draft.

Open integration gates: actual native source diff and complete dependency bytes;
RPi Linux/OIDC launcher and native x86-64 child execution under ARM64; dedicated
Windows service identity, credential and RPi SSH permissions; compiler licence
under that identity; cancellation/descendant-stop and private workspace cleanup;
fixed deadline and recovery ownership. A failed Windows build intentionally
retains its workspace because child process termination is not yet proven.

The Windows worker now starts its build helper in a Windows Job Object with
`KILL_ON_JOB_CLOSE` and without breakaway flags. The helper blocks on stdin
until the worker assigns it to the Job and sends `go`; it cannot take the lease
or invoke the compiler first. A controlled timeout or exception terminates the
Job and checks its active-process count. An unconfirmed stop fails closed and
retains the private workspace. Abrupt worker death closes the Job handle, but
cannot run Python cleanup: private files must be recovered separately. Local
dummy parent/child/grandchild tests cover normal execution, failed assignment,
timeout, and forced worker death. They do **not** prove e2 studio, nested
Runner-service Job behavior, the lease-release race, or workspace cleanup on a
real cancellation. `COMPILER_CANCELLATION_VERIFIED` therefore remains false.

Local nonsecret tests:

```sh
python -B -m unittest tools.ci.tests.test_idt_rpi4_pair -v
python -B -m unittest tools.ci.tests.test_windows_build_job -v
```
