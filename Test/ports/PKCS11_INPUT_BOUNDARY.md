# PKCS11 native input boundary

Native FRQ edits product-owned selection configuration. Borrowed PKCS11 and
Unity bodies remain unchanged at their fixed submodule pins. The host proof
covers source selection and input binding; device results and qualification
remain unestablished for this common-core change.

| Native request / builder argument | Public original groups | Cases per execution |
|---|---|---:|
| `Full_PKCS11_StartFinish` / `-Pkcs11Group StartFinish` | StartFinish, Capabilities | 5 + 1 |
| `Full_PKCS11_NoObject` / `-Pkcs11Group NoObject` | Capabilities, NoObject | 1 + 4 |

Capabilities runs twice across these executions, so the complete Core group has
ten distinct assertion names. The group order matches the original SDK runner.
The adapter calls Unity's public `RUN_TEST_GROUP` entries rather than
`RunPkcs11Test`, which resets filters and calls all five original groups.

## Editable configuration and compiled inputs

`pkcs11_source_view.py` creates a minimal private source view with the production
manifest, two product configuration headers and a product-owned group list.
FRQ 2.5 requires that list at the fixed relative path
`Test/FreeRTOS-Libraries-Integration-Tests/src/pkcs11/core_pkcs11_test.c`.
In the view this file contains only our five public group calls, without SDK
assertion bodies. It is selection configuration and is never compiled.

`run_transport.py` passes that view as native `userdata.sourcePath`. FRQ copies
it into its own per-test source directory and edits the group list and product
headers. `build_transport.sh` parses that owned list, validates the original
captured dependency hashes, and stages a separate private build tree from the
original source. Only the edited product headers are imported into this tree.
The same relative PKCS11 path in the build tree contains the original SDK body;
the facade is never copied over it. The helper selects compiler definition
`RX_IDT_PKCS11_SELECTED_GROUP=1` or `=2` from the explicit argument.
Each native execution has its own source tree and e2 studio workspace.

The source manifest permits exact original dependency bytes only. Selector
comments, EOL changes, edited test bodies and additional dependency files all
fail verification. No native callback patches or restores borrowed input.
The private binding and build manifest record the requested native test id,
public groups, compiler definition, configuration/facade hashes and original
SDK test-body hash. Flash resolution checks that binding, effective product
headers and original test bytes before selecting the completed build outputs.
An existing private build tree is preserved and rejected rather than overwritten
or silently reused.

The native helper rejects a missing selection before accessing sources or
invoking the compiler. `FullPKCS11_Import_ECC`, RSA, onboard key generation and
pre-provisioned groups remain outside this Core profile.

## Output port and verification scope

The old copied `Test/Common/test_framework.c` has been retired. Product-owned
`rx_idt_unity_output.c` and a small `unity_config.h` implement Unity's public
output hooks. They retain native start/end markers, line buffering and the
100 ms print-task drain interval. A long line flushes in chunks without dropping
incoming characters. The original old body remains traceable through Git history
and the original Amazon FreeRTOS `tests/common/aws_test_framework.c`.

Host tests compile the adapter with the unchanged Unity fixture sources. They
check both public routes, reset stale filters, preserve a deliberately failing
host fixture result, verify output boundaries and derive the original 5/1/4
case counts. Input-binding fixtures use local Git objects and original byte
checks; they do not execute PKCS11 assertions on a microcontroller.

On 2026-10-14, the actual installed FRQ 2.5 Linux component was invoked separately
for StartFinish and NoObject against a localhost public-SDK fixture. It edited
only the owned view and reached each build callback with the expected groups.
The fixture rejected each callback before compilation. A cleanup Close request
received a fixture response; no physical device was accessed. No credentials
were supplied and no AWS operation was performed. Native results remained
nonpassing. This is a native source-selector proof, not a firmware build,
board result, complete suite result or qualification result.

Sources:

- [Pinned original integration-test runner](https://github.com/FreeRTOS/FreeRTOS-Libraries-Integration-Tests/blob/0a0a92160a81c5cba008e472203513bd0cfb4c7a/src/pkcs11/core_pkcs11_test.c)
- [Pinned public Unity fixture API](https://github.com/ThrowTheSwitch/Unity/blob/22777c4810de3e3a4cb521a05eca2752fccd00ea/extras/fixture/src/unity_fixture.h)
- [Unity output configuration API](https://github.com/ThrowTheSwitch/Unity/blob/22777c4810de3e3a4cb521a05eca2752fccd00ea/docs/UnityConfigurationGuide.md)
- [Original old output port](https://github.com/FreeRTOS/amazon-freertos/blob/a038063c3b0216e0b4d46d72425388a0c2938b13/tests/common/aws_test_framework.c)
- [AWS LTS test settings](https://docs.aws.amazon.com/freertos/latest/userguide/lts-config-settings-device.html)
- [AWS LTS build/flash variables](https://docs.aws.amazon.com/freertos/latest/userguide/lts-dt-vars.html)
