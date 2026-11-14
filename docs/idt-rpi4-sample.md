# RPi #4 official IDT sample: dedicated-ref operation

This is a device-free CI experiment, not an MR-ready replacement for the repository's normal root CI. Project 38's `207-idt-rpi4-sample-stage1` ref deliberately uses a dedicated root configuration that includes `.gitlab/ci/rpi4-official-idt-sample.yml`. Do not merge that root configuration into main. GitLab project 38 uses the normal project CI config path; the pipeline creation API does not select an alternate config file per request. Trigger this ref through `POST /projects/38/pipeline` with `ref=207-idt-rpi4-sample-stage1`; no pipeline variables are needed. Inspect the returned SHA and job list before relying on the result. An alternate non-secret absolute ZIP path may be supplied as `IDT_RPI4_SAMPLE_ARCHIVE`.

The only job targets Runner #26 and checks the pinned official Linux IDT 4.9.0 / FRQ 2.5.0 ZIP and immutable files, then downloads and verifies pinned Ubuntu ARM64 QEMU and x86-64 libc packages. It explicitly runs the official device-free `test_log` sample under QEMU, with a dummy local pool and no AWS credentials, and publishes the single JUnit XML. QEMU/IDT are not stored in Git, installed on the host, or registered in host binfmt. The Runner user cannot create a network namespace; a loopback proxy is configured, but kernel-level egress isolation is not established. This smoke is not FRQ Transport, hardware verification, an AWS qualification result or proof of x86-64 child auto-execution.

## ZIP provisioning

Set the non-secret absolute `IDT_RPI4_SAMPLE_ARCHIVE` path at job invocation, or use the default `/var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip` on the selected RPi host. Obtain the official Linux ZIP through an already authorized acquisition. The unauthenticated official `LatestIdt` endpoint returned HTTP 403 on 2026-11-14; the repository's signed acquisition is in `tools/idt/run_idt.py`. Do not store a token or private download URL in CI variables, source or logs.

On RPi #4, with `IDT_SOURCE_ARCHIVE` set to an existing official ZIP, the host operator can provision the non-secret file without sudo:

```sh
test "$(sha256sum "$IDT_SOURCE_ARCHIVE" | cut -d ' ' -f 1)" = 59fdf0314d8196516e02806c972d13857c7d957516a22853c04f99855185cf84 &&
  install -d -m 755 /var/tmp/codex-idt-archives &&
  install -m 644 "$IDT_SOURCE_ARCHIVE" /var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip &&
  test "$(sha256sum /var/tmp/codex-idt-archives/idt-freertos-4.9.0-linux.zip | cut -d ' ' -f 1)" = 59fdf0314d8196516e02806c972d13857c7d957516a22853c04f99855185cf84
```

The job rechecks the digest and fails if the file is absent or changed. `/var/tmp` retention depends on host policy and is not a durable distribution service. Remove the exact file and directory when they are no longer needed.

## Package and cleanup policy

The script pins Ubuntu `qemu-user-static` and `libc6-amd64-cross` versions and package hashes. If the repository no longer serves them, the job fails. Review the authenticated Ubuntu index, update version and digest together, and rerun the lane; do not silently use a new candidate. An accessible authenticated APT index and package repository are prerequisites.

The job removes its temporary IDT tree, extracted packages and dummy key on normal exit; only sanitized JUnit is uploaded. If a runner is forcibly killed, inspect and remove only its abandoned `idt-rpi4-sample-*` temporary directory after confirming its processes have stopped.

## Future Transport execution

The official Transport `test.json` selects FRQ via `execution.linux.cmd` and arguments. A local, no-AWS/no-device experiment could first verify the unmodified archive and its original test definition, then make a separate temporary run copy, change only that copy's Linux command to the absolute pinned QEMU executable and arguments `-L`, the private x86-64 sysroot, the unchanged FRQ path, followed by the original FRQ arguments. Record and compare the exact before/after JSON and FRQ hash; never claim that the modified copy passes the original manifest. First substitute `--help` in a synthetic test to establish vendor IDT -> QEMU -> unchanged FRQ without running Transport. It remains unverified whether the IDT accepts the adjusted Transport definition, whether every required child is covered, or whether vendor integrity/qualification rules permit this overlay. If not, use a separately reviewed private or host binfmt configuration with explicit ownership and teardown; do not add sudo to shared Runner jobs. Windows build callbacks and AWS/HIL permissions remain separate work.
