# Step 7-4 OTA Attempt

Date: 2026-03-07 JST

## Scope

Issue #6 asks for one OTA happy-path run on the runner-connected CK-RX65N board.
This attempt did not reach OTA execution. Early manual trials mixed in the wrong
E2 Lite serial (`OBE110008`), but later validation with the correct CK-RX65N tool
(`OBE110020`) proved that the boot loader and UART path are alive. The remaining
work is to bring the app path back up on the same correct target and continue with
provisioning and OTA execution.

## Baseline

- Repository state: `main` merge commit `ddac254`
- Board target: CK-RX65N (V1)
- UART probe targets: `COM6` (expected J20), `COM7` (alternate probe)
- E2 Lite selection rule: use the device currently returned by
  `rfp-cli -d RX65x -t e2l -if fine -list-tools`
- Post-check correction: with only CK-RX65N connected, current `rfp-cli -list-tools`
  returns `OBE110020`

## AWS Preflight

The AWS side was not the blocker in this attempt.

- `C:\Program Files\Amazon\AWSCLIV2\aws.exe` default identity worked
- Existing OTA-related resources were visible:
  - S3 bucket: `rx65n-ota`
  - signer profiles: `ota_cert`, `rx65n_ota`, `rx65n_ota_profile20` and others
  - IoT OTA service role: `rx72n-ota-service-role`

Because UART recovery failed earlier, no new Thing/certificate provisioning and no
OTA Job creation were executed in this attempt.

## Commands Run

### 1. Headless build

```bat
tools\build_headless.bat C:\codex\tmp_iot_reference_rx_step7_4
```

Observed result:

- `BUILD SUCCESS`

### 2. Generate baseline initial image

```powershell
python tools/generate_signer_cert.py `
  --key tools/test_keys/secp256r1.privatekey `
  --out C:\codex\step7_4_run\baseline\userprog_codesign_cert.pem

python Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/src/smc_gen/r_fwup/tool/image-gen.py `
  -iup Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/HardwareDebug/aws_ether_ck_rx65n_v2.mot `
  -ip Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/src/smc_gen/r_fwup/tool/RX65N_DualBank_ImageGenerator_PRM.csv `
  -o C:\codex\step7_4_run\baseline\userprog `
  -ibp Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/HardwareDebug/boot_loader_ck_rx65n_v2.mot `
  -key tools/test_keys/secp256r1.privatekey `
  -vt ecdsa -ff RTOS
```

Observed result:

- `Generated OTA signer certificate`
- `Successfully generated ... userprog.mot file.`

### 3. Flash attempt A: combined `userprog.mot`

```powershell
rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery

rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF `
  -p C:\codex\step7_4_run\baseline\userprog.mot -run -noquery
```

Observed result:

- both commands ended with `Operation successful`

### 4. Flash attempt B: separate boot_loader + app

```powershell
rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery

rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF `
  -p Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/HardwareDebug/boot_loader_ck_rx65n_v2.mot `
  -run -noquery

rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF `
  -file Projects/aws_ether_ck_rx65n_v2/e2studio_ccrx/HardwareDebug/aws_ether_ck_rx65n_v2.mot `
  -auto -noerase -run -noquery
```

Observed result:

- all three commands ended with `Operation successful`

### 5. UART probe after flash

```powershell
python tools/test_mqtt.py --port COM6 --baud 115200 --timeout 45
python tools/test_mqtt.py --port COM7 --baud 115200 --timeout 30
```

Observed result:

- `CLI did not respond after all retries`
- `Total UART bytes received: 0`
- COM6 and COM7 both stayed at `0 byte`

Representative excerpt:

```text
WARNING: CLI did not respond after all retries
Sending 'reset' anyway as last resort...
Monitoring completed in 45.1s
Total UART bytes received: 0
```

### 6. `boot_loader` only + direct terminal observation

To remove the app/OTA layer from the equation, only the boot loader was flashed and
the serial console was kept open with `miniterm`.

```powershell
python -m serial.tools.miniterm COM6 115200

rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF -erase-chip -noquery

rfp-cli -d RX65x -t "e2l:<detected-e2l-serial>" -if fine -s 500K `
  -auth id FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF `
  -p Projects/boot_loader_ck_rx65n_v2/e2studio_ccrx/HardwareDebug/boot_loader_ck_rx65n_v2.mot `
  -run -noquery
```

Additional manual checks:

- board power cycle (USB disconnect/reconnect)
- board reset button
- J16 changed to `RUN`

Observed result:

- no `BootLoader` banner
- no `send image(*.rsu) via UART.`
- no text output at all on `COM6`

This made the blocker look stronger than an MQTT or OTA application-level failure,
but the conclusion is only valid if the flash commands targeted the CK-RX65N board.

### 7. Post-attempt correction: E2 Lite mapping

Additional hardware mapping checks after the initial attempt showed:

- with only CK-RX65N connected, unplugging `J20` removes `COM6`
- with only CK-RX65N connected, `rfp-cli -d RX65x -t e2l -if fine -list-tools`
  returns `OBE110020`
- `rfp-cli ... -t "e2l:OBE110008"` now fails with
  `E3000201: Cannot find the specified tool`
- runner hardware inventory also maps `OBE110020 = CK-RX65N V1` and
  `OBE110008 = RX72N Envision Kit`

Therefore, any Step 7-4 flash/UART observation taken with `OBE110008` is not a
valid CK-RX65N result. The previous UART-silent observations need one clean rerun
with `OBE110020` before issue #8-style board/UART recovery is treated as the
confirmed blocker.

### 8. Validation with the correct CK-RX65N E2 Lite

With only CK-RX65N connected and `OBE110020` selected, the boot loader was flashed
again and `COM6` was observed with `miniterm`.

Observed result:

- `rfp-cli -d RX65x -t e2l -if fine -list-tools` returned only `OBE110020`
- `boot_loader_ck_rx65n_v2.mot` flash succeeded with `e2l:OBE110020`
- `miniterm COM6 115200` showed the expected banner:

```text
==== RX65N : BootLoader [dual bank] ====
send image(*.rsu) via UART.
```

This clears the earlier suspicion that the CK board's UART path was dead. At
least the following path is now confirmed on the real target:

- `J14 / OBE110020 -> RX65N flash/write -> boot_loader execution -> J20 / COM6 UART output`

## Result

This Step 7-4 attempt failed before provisioning or OTA execution.

The first blocker was:

- correct target selection (`OBE110020` for CK-RX65N V1)

Rationale:

- build succeeded
- image generation succeeded
- AWS preflight resources existed
- later hardware checks established `OBE110020 = CK-RX65N V1`
- `OBE110008` is not the CK target and should not be used for retry
- `OBE110020` + `boot_loader_ck_rx65n_v2.mot` + `miniterm COM6` produced the
  expected boot loader banner

The earlier UART-silent observations remain valid as history of a mis-targeted
trial, but they no longer justify treating `board/UART dead` as the active
Step 7-4 blocker. The active next step is to rerun the app path on `OBE110020`.

## Next Step

Retry order should be:

1. keep only CK-RX65N connected
2. confirm `rfp-cli -d RX65x -t e2l -if fine -list-tools` returns `OBE110020`
3. rerun separate flash on `e2l:OBE110020`
   - `boot_loader_ck_rx65n_v2.mot`
   - `aws_ether_ck_rx65n_v2.mot`
4. verify app-side UART/CLI with `python tools/test_mqtt.py --port COM6 --baud 115200 --timeout 45`
5. reprovision credentials if app flash used `-erase-chip`
6. then continue with OTA Job creation and `tools/test_ota.py`-based observation

## Notes

- `tools/flash.bat` had a batch parsing bug caused by an unused quoted variable.
  That was fixed during this branch so the manual flash helper itself no longer
  aborts before invoking `rfp-cli`.
- A second batch parsing bug was found later in the prerequisite check for
  `rfp-cli`: `Program Files (x86)` in `%RFP_CLI%` broke `if (...)` parsing.
  This was fixed by removing the grouped block from that check.
