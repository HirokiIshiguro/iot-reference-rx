# RX72N IDT transport port

`rx72n_idt_transport.c` runs the pinned upstream `Full_TransportInterfaceTest`
suite on RX72N Envision Kit Ethernet with the production software TLS transport.
This is an individual `FullTransportInterfaceTLS` validation build. It does not
establish full IDT qualification or make the current `202604.00-LTS` manifest
compatible with IDT's version checks.

IDT populates `Test/include/test_param_config.h` with the echo endpoint, CA,
and client certificate. The development build callback verifies the certificate
against its disposable host-generated EC key, then injects that matching private
key into the runtime source copy. FRQ 2.5 does not inject the private key itself.
Select only
`TRANSPORT_INTERFACE_TEST_ENABLED=1` in `test_execution_config.h`. All other
test flags must be zero. Then run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File tools/build_rx72n_idt_transport.ps1 `
  -ProjectRoot <runtime-copy> -Workspace C:\ai\codex\ws\rx72n-idt-build `
  -ProvenanceFile <runtime-source-provenance.json>
```

The wrapper temporarily links six test sources and defines
`ENABLE_IDT_TRANSPORT_TEST=1` and `UNITY_INCLUDE_CONFIG_H`. It restores project
metadata and tracked Smart Configurator output after the build. The default
project still starts its usual MQTT/OTA demos. The script builds only; it does
not flash a board, reset hardware, or create AWS resources.

The provenance JSON records `source_sha`, `test_library_sha` (40 hex characters)
and `source_tree_dirty` (boolean), collected from the original checkout before
IDT copies it. Git submodule pointers in that copy may no longer resolve.

Build the IDT-injected configuration only in the restricted runtime copy.
Outputs there are `artifacts/idt/build_transport/rx72n_idt_transport.{mot,abs,x}`
plus the build log and hash manifest. Test binaries contain the disposable IDT
credentials and must stay in that runtime copy. Do not include them in CI
artifacts or release assets, despite the local output directory's name.
Only credential-free logs and metadata may be exported from the runtime copy.
At runtime the test writes those credentials through the normal KVS/PKCS11
provisioning path. Restore the board's normal credentials after testing.

Each of the two TLS connections owns a separate transport context. Test workers
inherit the calling test task's priority. Completion is joined through a
semaphore, and only a completed worker is deleted and freed. On a join timeout,
the port emits `IDT_PORT_FATAL: thread join timeout` and suspends the calling
test task indefinitely. It preserves the worker, descriptor and context because
the worker may hold TLS/PKCS11 locks. No subsequent test or teardown runs; the
host must stop IDT, clean up its test resources, and reset/hold the MCU before
reuse. The fatal marker is a failed run, never a PASS.

Socket timeout (1000 ms) and worker stack depth (8192 words) follow the existing
`Test/integration_test.c` port. The transport functions and upstream assertions
are not altered. Optional
`writev` tests are not selected because the production port has no `writev`.

MQTT, PKCS11, Device Advisor, OTA PAL and OTA E2E tests are excluded from this
build. In particular, the pinned 202406 MQTT test calls the old coreMQTT API;
coreMQTT 5 requires different callback signatures and API parameters, as well
as an explicit review of persistent-session and retransmission semantics.
