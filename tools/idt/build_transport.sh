#!/bin/bash
# Sensitive injected source and images stay in the private IDT runtime tree.
set -euo pipefail
test "$#" -eq 1 || { echo 'One IDT source path is required' >&2; exit 2; }
src="$(realpath "$1")"
here="$(cd -- "$(dirname -- "$0")" && pwd)"
linux_py="${IDT_LINUX_PYTHON:-python3}"
target="$("$linux_py" "$here/targets.py" --field id)"
export IDT_TARGET="$target"
target_field() { "$linux_py" "$here/targets.py" --target "$target" --field "$1"; }
artifact="$(target_field artifact_basename)"
packager="$(target_field packager)"
prm="$(target_field prm)"
signing_key="$(target_field signing_key)"
bank_range_start="$(target_field bank_range_start)"
bank_range_end="$(target_field bank_range_end)"
bank_shift="$(target_field bank_shift)"
if [[ "${IDT_SCOPE:-transport}" != pkcs11 && "${IDT_SCOPE:-transport}" != ota-pal ]]; then
  "$linux_py" "$here/prepare_transport_key.py" "$src"
fi
if [[ "$target" != rx72n-ethernet && "${IDT_SCOPE:-transport}" != pkcs11 && "${IDT_SCOPE:-transport}" != ota-pal ]]; then
  "$linux_py" "$here/prepare_target_network.py" "$src"
fi
win="$(wslpath -w "$src")"
pwsh="${IDT_WINDOWS_PWSH:?Windows PowerShell executable is required}"
py="${IDT_WINDOWS_PYTHON:?Windows Python executable is required}"
runtime="${IDT_RUNTIME_DIR:?Private runtime directory is required}"
run_name="$(basename -- "$(dirname -- "$runtime")")"
[[ "$run_name" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Invalid runtime directory name' >&2; exit 2; }
workspace="${IDT_WORKSPACE_ROOT:?Windows workspace root is required}\\${target}-idt-build-${run_name}"
case "${IDT_SCOPE:-transport}" in
  transport) test_group=Transport ;;
  mqtt) test_group=DeviceAdvisor ;;
  ota-mqtt) test_group=OTAE2E ;;
  pkcs11) test_group=PKCS11 ;;
  ota-pal) test_group=OTAPAL ;;
  *) echo 'Unsupported IDT build scope' >&2; exit 2 ;;
esac
if [[ "$test_group" == OTAE2E ]]; then
  "$linux_py" "$here/ota_support.py" prepare "$src" --target "$target"
fi
"$pwsh" -NoProfile -ExecutionPolicy Bypass -File "$win\tools\build_rx72n_idt_transport.ps1" \
  -ProjectRoot "$win" -Workspace "$workspace" -TestGroup "$test_group" -Target "$target" \
  -E2Studio "${IDT_E2STUDIO_CLI:?e2 studio executable is required}" \
  -ProvenanceFile "${IDT_PROVENANCE_FILE:?Source provenance is required}"
out="$win\artifacts\idt\build_transport"
"$linux_py" "$here/ota_support.py" validate-packaging "$src" --target "$target"
package_args=("$(wslpath -w "$src/$packager")" --mot "$out\${artifact}.mot"
  --key "$(wslpath -w "$src/$signing_key")" --output "$out\${artifact}.rsu")
if [[ "$prm" != None ]]; then
  package_args+=(--prm "$(wslpath -w "$src/$prm")")
fi
"$py" "${package_args[@]}"
"$py" "$win\tools\shift_srec_addresses.py" \
  --input "$out\bootloader.mot" \
  --output "$out\bootloader_bank1.mot" --range-start "$bank_range_start" --range-end "$bank_range_end" \
  --shift="$bank_shift" --drop-out-of-range
"$linux_py" "$here/ota_support.py" record-packaging "$src" --target "$target"
if [[ "$test_group" == OTAE2E ]]; then
  "$linux_py" "$here/ota_support.py" payload "$src" --target "$target"
fi
