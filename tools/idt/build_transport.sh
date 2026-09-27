#!/bin/bash
# Sensitive injected source and images stay in the private IDT runtime tree.
set -euo pipefail
test "$#" -eq 1 || { echo 'One IDT source path is required' >&2; exit 2; }
src="$(realpath "$1")"
here="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ "${IDT_SCOPE:-transport}" != pkcs11 && "${IDT_SCOPE:-transport}" != ota-pal ]]; then
  "${IDT_LINUX_PYTHON:-python3}" "$here/prepare_transport_key.py" "$src"
fi
win="$(wslpath -w "$src")"
pwsh="${IDT_WINDOWS_PWSH:?Windows PowerShell executable is required}"
py="${IDT_WINDOWS_PYTHON:?Windows Python executable is required}"
runtime="${IDT_RUNTIME_DIR:?Private runtime directory is required}"
run_name="$(basename -- "$(dirname -- "$runtime")")"
[[ "$run_name" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Invalid runtime directory name' >&2; exit 2; }
workspace="${IDT_WORKSPACE_ROOT:?Windows workspace root is required}\\rx72n-idt-build-${run_name}"
case "${IDT_SCOPE:-transport}" in
  transport) test_group=Transport ;;
  mqtt) test_group=DeviceAdvisor ;;
  ota-mqtt) test_group=OTAE2E ;;
  pkcs11) test_group=PKCS11 ;;
  ota-pal) test_group=OTAPAL ;;
  *) echo 'Unsupported IDT build scope' >&2; exit 2 ;;
esac
if [[ "$test_group" == OTAE2E ]]; then
  "${IDT_LINUX_PYTHON:-python3}" "$here/ota_support.py" prepare "$src"
fi
"$pwsh" -NoProfile -ExecutionPolicy Bypass -File "$win\tools\build_rx72n_idt_transport.ps1" \
  -ProjectRoot "$win" -Workspace "$workspace" -TestGroup "$test_group" \
  -E2Studio "${IDT_E2STUDIO_CLI:?e2 studio executable is required}" \
  -ProvenanceFile "${IDT_PROVENANCE_FILE:?Source provenance is required}"
out="$win\artifacts\idt\build_transport"
"$py" "$win\tools\build_fwup_v2_rsu.py" --mot "$out\rx72n_idt_transport.mot" \
  --prm "$win\tools\fwup\rx72n_envision_kit_dual_bank.prm.csv" \
  --key "$win\sample_keys\secp256r1.privatekey" --output "$out\rx72n_idt_transport.rsu"
"$py" "$win\tools\shift_srec_addresses.py" \
  --input "$win\Projects\boot_loader_rx72n_envision_kit\e2studio_ccrx\HardwareDebug\boot_loader_rx72n_envision_kit.mot" \
  --output "$out\bootloader_bank1.mot" --range-start 0xFFE00000 --range-end 0xFFFFFFFF \
  --shift=-0x200000 --drop-out-of-range
if [[ "$test_group" == OTAE2E ]]; then
  "${IDT_LINUX_PYTHON:-python3}" "$here/ota_support.py" payload "$src"
fi
