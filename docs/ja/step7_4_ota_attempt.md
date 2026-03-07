# Step 7-4 OTA Attempt

Date: 2026-03-07 JST

## Scope

Issue #6 asks for one OTA happy-path run on the runner-connected CK-RX65N board.
This attempt did not reach OTA execution. The failure was narrowed to one blocker:
the UART console stayed at `0 byte` after flash, so provisioning and OTA logs could
not be captured.

## Baseline

- Repository state: `main` merge commit `ddac254`
- Board target: CK-RX65N (V1)
- UART probe targets: `COM6` (expected J20), `COM7` (alternate probe)
- E2 Lite selection rule: use the device currently returned by
  `rfp-cli -d RX65x -t e2l -if fine -list-tools`

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

This makes the blocker stronger than an MQTT or OTA application-level failure.

## Result

This Step 7-4 attempt failed before provisioning or OTA execution.

The single blocker is:

- `flash -> UART recovery` boundary

Rationale:

- build succeeded
- image generation succeeded
- both flash strategies succeeded according to `rfp-cli`
- AWS preflight resources existed
- UART stayed at `0 byte`, so the board could not be provisioned or observed
- even `boot_loader`-only flash plus direct terminal observation produced no UART text
- J16=`RUN` and hardware reset also did not restore output

This matches the symptom family already tracked in issue #8 more closely than an
AWS-side configuration failure, and it weakens the hypothesis that only the
application/OTA layer is at fault.

## Next Step

Do not spend the next retry on AWS setup first.

Retry order should be:

1. verify board-to-host mapping explicitly
   - unplug J20 and confirm `COM6` disappears
   - unplug J14 and confirm `rfp-cli -list-tools` loses the current E2 Lite serial
2. if mapping is correct, treat the next investigation as J20/SCI5 path or board-side
   UART hardware rather than OTA logic
3. only after UART visibility is back, rerun `test_mqtt.py`
4. then continue with provisioning and OTA Job creation

## Notes

- `tools/flash.bat` had a batch parsing bug caused by an unused quoted variable.
  That was fixed during this branch so the manual flash helper itself no longer
  aborts before invoking `rfp-cli`.
