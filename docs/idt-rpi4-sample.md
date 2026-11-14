# RPi #4 official IDT sample smoke

This dedicated #207 MR/API lane runs the official IDT 4.9.0 Python sample `test_log` on Runner #26 (ARM64) and publishes one JUnit result. It does not run FRQ Transport, a board, Windows builds or AWS credentialed work. It uses the stock x86-64 IDT binary through an explicitly invoked QEMU user-mode executable; the sample's Python child runs natively. This does not establish that x86-64 FRQ child executables can run without binfmt.

The sample job runs on the dedicated `207-rpi4-idt-sample` MR or API/web pipeline. After merge, an API/web pipeline on current main can select it with `RUN_RPI4_IDT_SAMPLE=true`; normal main pushes and schedules do not select it. The dedicated branch checks the reviewed CI configuration and allowed diff paths before execution, so unrelated changes fail rather than benefiting from the reduced lane. The main entry requires the fetched current default-branch HEAD. Do not combine this selector with other pipeline scope or build overrides. The job verifies the official Linux ZIP digest and immutable IDT/FRQ trees using the existing `tools/idt/idt_bundle.py`, then extracts fixed Ubuntu ARM64 QEMU and x86-64 libc packages without installation or sudo and checks their SHA-256. It runs with an empty credential home and no inherited AWS credentials. The job does not create an isolated network namespace: Runner #26's actual user could not create one. A loopback proxy is configured for external HTTP(S), but kernel-level network isolation is not claimed.

## ZIP provisioning

The job requires the non-secret absolute path `IDT_RPI4_SAMPLE_ARCHIVE`. The sample job's default on RPi #4 is `/var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip`; callers may provide another readable absolute path. Provision this only on the selected host before running the sample, using an already authorized acquisition of the official Linux IDT ZIP. The unauthenticated official `LatestIdt` endpoint returned HTTP 403 in the 2026-11-14 check; the repository's normal signed acquisition is in `tools/idt/run_idt.py`. Do not put an AWS token or private download URL in CI variables, source or logs.

For a verified local ZIP, with `IDT_SOURCE_ARCHIVE` set to its absolute path, a host operator can prepare the non-secret file without sudo:

```sh
test "$(sha256sum "$IDT_SOURCE_ARCHIVE" | cut -d ' ' -f 1)" = 59fdf0314d8196516e02806c972d13857c7d957516a22853c04f99855185cf84 &&
  install -d -m 755 /var/tmp/codex-idt-archives &&
  install -m 644 "$IDT_SOURCE_ARCHIVE" /var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip &&
  test "$(sha256sum /var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip | cut -d ' ' -f 1)" = 59fdf0314d8196516e02806c972d13857c7d957516a22853c04f99855185cf84
```

The job checks the pinned archive again; a missing or different ZIP fails the job. `/var/tmp` retention depends on host policy, so this path is a local provisioning dependency, not a durable distribution service. Remove the exact file and directory when no longer needed. No IDT or QEMU distribution is stored in Git.

## Ubuntu package pins

The smoke downloads `qemu-user-static` and `libc6-amd64-cross` at the versions and package hashes in the script. If Ubuntu no longer serves a pinned package, the job fails; do not silently select the current candidate. Review the authenticated Ubuntu package index, update the version and digest together, and rerun this lane before accepting the update. The download depends on the host's authenticated APT indexes and repository availability.

The temporary IDT tree, extracted packages and dummy key are removed on normal exit; the only published artifact is the sanitized official JUnit XML. If a runner is forcibly killed, inspect and remove only the abandoned `idt-rpi4-sample-*` temporary directory after confirming its processes have stopped.
