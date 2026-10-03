# Renesas RX IDT test ports

These ports build selected native IDT groups for RX72N Envision Kit Ethernet,
CK-RX65N V1 + BG96 cellular and EK-RX671 + Type 1YN Wi-Fi with each target's
existing production software TLS, MQTT, corePKCS11 and OTA paths.
The historical `rx72n_idt_*` filenames and entry points remain shared.
RX72N/RX671 use the shared coreMQTT 5 tree; BG96 uses its maintained local
coreMQTT 2.3.1 tree. The ports do not alter either protocol/version.
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

## Target startup

| Builder `-Target` | Selector | Network startup | OTA PAL inactive region |
|---|---|---|---|
| `rx72n-ethernet` (default) | `IDT_TARGET_RX72N_ETHERNET=1` | production FreeRTOS+TCP Ethernet | `0xFFC00000..0xFFDBFFFF` |
| `rx65n-bg96` | `IDT_TARGET_RX65N_BG96=1` | production `Connect2AP()` and BG96 cellular sockets | `0xFFE00000..0xFFEEFFFF` |
| `rx671-wifi` | `IDT_TARGET_RX671_WIFI=1` | production WHD AP JOIN and verified DHCP lease | `0xFFE00000..0xFFEBFFFF` |

`rx_idt_config.h` checks a single startup profile and that its selected target
matches the BSP MCU. The old RX72N builder may omit the selector on RX72N only.
No IDT startup/header is required by ordinary project builds. BG96 initializes
its existing SCI0 UART and queue directly at 921600 bps; RX671 retains `debug_uart` SCI6 at
921600 bps. Both bypass their interactive CLI and other smoke/benchmark tasks.
PKCS11 and OTA PAL start after LittleFS/KVS initialization without a network
or MQTT task competing with the tested lifecycle.

For BG96/Wi-Fi network scopes, the host generates the private runtime-only
`Test/include/idt_network_config.h`. `rx_idt_network.c` writes those parameters
to production KVS before connecting, including explicit empty cellular user /
password strings to clear stale values. Wi-Fi requires SSID 1..32 bytes and
WPA2 passphrase 8..63 bytes, `WHD_JOIN_ENABLE=1`, `WHD_JOIN_USE_KVS=1` and
`RX671_WIFI_CREDENTIAL_KVS_ENABLE=1`. Cellular requires a nonempty APN and
authentication `0`, `1` or `2`. These values are never printed. Local PKCS11 /
PAL tests neither require this header nor start networking.

RX671 IDT images use the existing temporary 768-KiB dual-bank OTA layout;
the checked-in normal linear-bank profile remains unchanged. The compile-time
PAL guard rejects a linear build or any unreviewed address/size combination.
An RX671 bootloader-backed native launch also requires a matched signer in
LittleFS before the first application boot. The secure bootloader refuses an
empty trust store with built-in fallback disabled. The established production
credential provisioner prepares `codesignpubkey` and `codesigncert` while
preserving Data Flash; application-side IDT provisioning alone cannot initialize
trust before that first boot. The guarded callback runs that production linear
signer-only provisioner before writing both bootloader banks and downloading the
signed dual-bank application. Its required public bootstrap inputs are
`IDT_RX671_PROVISIONER_MOT_FILE`, `IDT_RX671_PROVISIONER_MANIFEST_FILE`,
`IDT_RX671_SIGNER_CERT_FILE`, and `IDT_RX671_SIGNER_PUBLIC_KEY_FILE`.
The host copies verified inputs into private runtime, and the remote callback
revalidates the source/hash/layout, public signer, bootloader policy, and actual
initial RSU signature before hardware mutation. This check proves prepared
materials; LittleFS runtime trust is established by the real provisioning
transaction. Missing or mismatched inputs are blocked for every RX671 scope.
This callback has only been validated locally with mocks during this work.

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
IDT profiles initialize the UART port synchronously without creating an
interactive CLI task. This avoids deleting that task while it holds the TX
mutex during its welcome message, which previously hid post-OTA boot output.
`-ValidateOnly` checks the selected profile without compiling or touching hardware.
The build script itself does not flash a board or create AWS resources.

The provenance JSON carries the original `source_sha`, `test_library_sha`
(40 hexadecimal characters), `source_tree_dirty` (boolean), selected target and
fingerprint, dependency gitlink pins, and exact dependency file hashes. IDT's
runtime copy may contain broken worktree/submodule `.git` pointers; provenance is
captured from initialized dependencies matching source gitlinks before copying.
Every builder verifies the copied dependency file set and bytes before applying
temporary profiles. RX671 helpers consume that verified provenance without Git
initialization or network access, retaining the WHD forward/reverse patch gate.
The build manifest records output/configuration hashes, selected group and,
for OTA, application version or PAL coverage.
For OTA E2E, each build gets a unique image ID in the generated signer header.
The running image emits that ID with its compiled application version before
cloud provisioning. The build ledger maps it to the MOT/payload hashes.
The host records UART before native parsing and drains it through EOF; raw
bytes remain private. Every OTA ledger entry must match the selected target and
its fingerprint. The single GreaterVersion job additionally requires an
observed initial-image boot followed by the newer built image. This observation
does not replace or rewrite the native JUnit result.
Flash callback failures remain latched in the private runtime. The supervisor
checks that latch during execution and after native exit, so a native zero exit
cannot turn a failed initial flash into a passing run.

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

OTA PAL is restricted to the reviewed target-specific dual-bank layouts and writes the
configured inactive install region. The port performs no activation,
bank swap or reset. Of 15 nominal cases, 14 can execute assertions; the filesystem-only
`otaPal_CloseFile_NonexistingCodeSignerCertificate` is explicitly IGNORE. The host
native FRQ 2.5 maps this IGNORE to a JUnit failure. The checker preserves that
nonpassing full-group result; it does not report 15 PASS.

OTA E2E uses native IDT's OTA cases. Selecting `OTAE2EGreaterVersion` alone is
recorded as partial coverage. The AWS Signer preparation/cleanup code does not
itself prove that an OTA update succeeded. Keep the bench lock until the guarded
reset command succeeds and a fresh one-second UART observation is quiet.
RESET pin voltage measurement is not a prerequisite; record physical hold as
unverified. Failed reset/quiet checks retain ownership. Reflash and reprovision
the normal firmware before returning the board to ordinary use.
