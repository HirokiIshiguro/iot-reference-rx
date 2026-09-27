# RX72N IDT test ports

These ports build selected native IDT groups for RX72N Envision Kit Ethernet
with the production software TLS, coreMQTT 5, corePKCS11 and OTA paths.
A selected group result does not establish complete IDT qualification or make
`202604.00-LTS` compatible with IDT 4.9.0's version checks.
Current results and host setup are maintained in [IDT validation](../../docs/idt-validation.md).

| Host scope | Builder `-TestGroup` | Device entry / source |
|---|---|---|
| `transport` | `Transport` | `rx72n_idt_transport.c`; upstream transport assertions |
| `mqtt` | `DeviceAdvisor` | `rx72n_idt_cloud.c`; production MQTT agent / SimplePubSub, evaluated by native `FullCloudIoT` |
| `pkcs11` | `PKCS11` | `rx72n_idt_pkcs11.c`; upstream `RunPkcs11Test()` and production provisioning helpers |
| `ota-pal` | `OTAPAL` | `rx72n_idt_otapal.c`; existing `Test/Custom/ota/ota_pal_test.c` assertions |
| `ota-mqtt` | `OTAE2E` | `rx72n_idt_cloud.c`; production MQTT / OTA tasks and IDT-provided application version |

`preflight` checks versions on the host and does not build firmware.
The builder requires exactly the selected test flag; other test flags stay zero.
The inactive legacy `MQTT_TEST_ENABLED` suite is not linked: its 202406 API is
not compatible with coreMQTT 5. Native `FullCloudIoT` uses Device Advisor instead.
The cloud port never generates a local PASS or changes the production MQTT protocol.

## Build and provenance

For a manual build of an already restricted source copy:

```powershell
pwsh.exe -ExecutionPolicy Bypass -File tools/build_rx72n_idt_transport.ps1 `
  -ProjectRoot <restricted-runtime-copy> -Workspace C:\ai\codex\ws\idt-private-run\build `
  -ProvenanceFile <runtime-source-provenance.json> -TestGroup Transport
```

Native runs choose the workspace automatically as
`<workspace_root>\idt-private-<run>\rx72n-idt-build-<run>`.

The wrapper links only the selected sources, applies temporary IDT defines,
and restores project metadata, demo configuration and tracked Smart Configurator
output after the build. Normal project builds retain their usual startup path.
`-ValidateOnly` checks the selected profile without compiling or touching hardware.
The build script itself does not flash a board or create AWS resources.

The provenance JSON carries the original `source_sha`, `test_library_sha`
(40 hexadecimal characters) and `source_tree_dirty` (boolean). IDT's runtime
copy may contain broken worktree/submodule `.git` pointers; provenance is
collected before copying and is never reconstructed from those pointers.
The build manifest records output/configuration hashes, selected group and,
for OTA, application version or PAL coverage.
For OTA E2E, each build gets a unique image ID in the generated signer header.
The running image emits that ID with its compiled application version before
cloud provisioning. The build ledger maps it to the MOT/payload hashes.
The host records UART before native parsing and drains it through EOF; raw
bytes remain private. The single GreaterVersion job additionally requires an
observed initial-image boot followed by the newer built image. This observation
does not replace or rewrite the native JUnit result.

## Credentials and runtime isolation

Only the restricted runtime copy may contain IDT-injected test parameters.
Transport uses the IDT-issued client certificate and a matching disposable
host-generated EC key. For native MQTT, IDT supplies endpoint/Thing but not the
client certificate: the callback reads only that exact Thing's active certificate
with the matching public key, checking account and region before accepting it.
The cloud port provisions the temporary Thing, endpoint, certificate/key and
Amazon Root CA 1 through production KVS. OTA also provisions its test signer.
Credential values are never printed.

Outputs remain under the runtime copy's `artifacts/idt/build_transport`, including
`rx72n_idt_transport.{mot,abs,x}`, the RSU, build log and manifest. The historical
output basename is shared across selected groups; the manifest identifies the
actual group. These binaries contain test credentials and must not be published
as CI artifacts or release assets. Export only the sanitized JUnit and summaries
from the host launcher. The e2 studio workspace also remains outside the checkout
under a restricted parent.

## Test boundaries

`rx72n_idt_platform.c` supplies FreeRTOS threads, time, allocation and randomness
for the local assertion suites. Workers inherit the caller's priority; a semaphore
joins completion before deletion/free. On a join timeout the port emits
`IDT_PORT_FATAL`, retains live worker/context storage and suspends the caller.
The host stops IDT, cleans resources, and resets/holds the MCU. A fatal marker
is never a PASS.

Transport gives its two TLS connections separate contexts. Its 1000 ms socket
timeout and 8192-word worker stack follow the existing integration port.
Production transport functions and upstream assertions are unchanged. Optional
`writev` tests remain unselected because the production port has no `writev`.

The PKCS11 profile is EC/import: RSA, onboard key generation, pre-provisioned
mode and JITP tests are disabled. It uses existing production provisioning helpers
rather than linking duplicate upstream implementations. Test objects are disposable;
this profile does not prove an onboard-generated-key qualification path.
The native `FullPKCS11_Core` result covers ten basic API cases. It does not cover
the separate `FullPKCS11_Import_ECC` object/sign group, which has not been run.

OTA PAL is restricted to the reviewed RX72N dual-bank layout and writes the
inactive flash region `0xFFC00000–0xFFDBFFFF`. The port performs no activation,
bank swap or reset. Of 15 nominal cases, 14 can execute assertions; the filesystem-only
`otaPal_CloseFile_NonexistingCodeSignerCertificate` is explicitly IGNORE. The host
native FRQ 2.5 maps this IGNORE to a JUnit failure. The checker preserves that
nonpassing full-group result; it does not report 15 PASS.

OTA E2E uses native IDT's OTA cases. Selecting `OTAE2EGreaterVersion` alone is
recorded as partial coverage. The AWS Signer preparation/cleanup code does not
itself prove that an OTA update succeeded. After every hardware run, retain the
bench lock through reset-hold/UART-quiet verification. Reflash and reprovision
the normal firmware before returning the board to ordinary use.
