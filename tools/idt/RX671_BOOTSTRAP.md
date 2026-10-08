# RX671 initial IDT boot trust

Every RX671 native firmware scope (`transport`, `mqtt`, `ota-mqtt`, `pkcs11`,
`ota-pal`) installs a signed application through the secure dual-bank bootloader.
That first boot requires `codesignpubkey` in LittleFS. The application cannot
initialize this trust before its own first boot. Built-in public-key fallback
remains disabled, ECDSA remains required, and the bootloader never installs Data
Flash from the RSU.

The CI job builds the production credential-free provisioner and matching public
signer inputs automatically for RX671 hardware scopes. Host-only preflight does
not perform this build. Local runs or reviewed CI overrides can instead supply
the complete set of public/firmware references before native IDT starts:

| Variable | Input |
|---|---|
| `IDT_RX671_PROVISIONER_MOT_FILE` | Production linear provisioner MOT |
| `IDT_RX671_PROVISIONER_MANIFEST_FILE` | Its `provisioner-manifest.json` |
| `IDT_RX671_SIGNER_CERT_FILE` | One public P-256 signer certificate PEM |
| `IDT_RX671_SIGNER_PUBLIC_KEY_FILE` | Its matching public-key PEM |

The provisioner is built by the existing production
[`build_rx671_ota_images.py`](../build_rx671_ota_images.py) profile
`rx671-bank-single-ota-provisioner-v1`, using the same source SHA as the IDT build.
Its manifest must state `bank.single`, `credentials_embedded=false`, and the
matching MOT hash. Use the ordinary project configuration with IDT flags disabled
when building that provisioner. An IDT dual-bank application is not a provisioner.
No file reference or pre-existing provisioning summary is accepted as proof of
current Data Flash contents.

The host uses unbuffered input and reads public PEM lines only through the matching
END marker. It rejects an initial private header or any extra object after the
public PEM before reading that object's body or copying the input. A 4-KiB bound
also limits malformed input and trailing whitespace.
Public inputs are copied into the restricted run's `inputs/rx671-bootstrap`.
The intended signer must match the repository's development signing key **public
part**; the bootstrap controller does not read a private key or Wi-Fi credentials.
The callback additionally checks the actual RSU ECDSA signature, provisioner MOT
address ranges, bootloader bank0/bank1 exact shift, and the compiled boot policy
input hashes. The remote helper repeats these checks before programming.

Inside the existing bench and global RFP locks, each independent IDT image first
uses RFP chip erase to clear Code Flash, Data Flash and flash options. This
removes the startup-bank state left by a previous signed install (see
[#168](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/168)).
The real production provisioner then reconstructs public signer trust and
runs with `signer_only=True`: program the linear MOT, open SCI6, run the CLI,
format LittleFS, set `codesigncert`/`codesignpubkey`, and commit. It then erases only
`FFE00000..FFEBFFFF` and `FFF00000..FFFBFFFF`, preserving Data Flash, and programs
bootloader bank0. The callback programs bank1 and downloads the verified signed
dual-bank RSU through the existing strict UART downloader. Data Flash is
preserved after signer provisioning. Ordinary full credential provisioning
keeps its existing behavior.

The local prepared plan records `runtime_trust=not_established`. Actual LittleFS
persistence and successful secure boot require a separately authorized hardware
run; neither local checks nor a selected group establish complete IDT qualification.
Before that run, confirm the selected board and programmer, bench ownership,
ordinary CI availability, and the required physical wiring/power with the owner.
This change creates no AWS resources or credentials by itself.

End-state handling preserves the existing RX72N CI procedure: a guarded reset
command must succeed and a fresh one-second UART observation must be quiet.
RESET pin voltage measurement is not an execution prerequisite. Evidence retains
`physical_hold=unverified`; failed reset/quiet checks keep the owner record.

The shared [`cleanup_budget.py`](cleanup_budget.py) derives the RX671 transaction
bound from its operations: 60 seconds for RFP lock acquisition, three 15-second
UART control phases, one 90-second initial chip erase, four 90-second provisioner/RFP operations, a 200-second
absolute CLI bound, a 90-second bank1 write, a 540-second UART download, and two
90-second final RFP operations: 1565 seconds. The CLI bound covers the existing
45-second invitation wait, three 5-second CLI retries, 15-second commands,
30-second commit and bounded 2-ms character pacing. Other targets total 1095
seconds using their existing three erase/bootloader operations. Abort reset has
its separate 90-second bound; child termination reserves time inside each command
timeout.

Timeouts include a reserved RFP child-process termination interval. A persistent
`<rfp_lock>.unsafe.json` sentinel blocks IDT programming/reset/reuse when termination
cannot be proved. A privileged timeout or interruption requires manual recovery,
including inspection for unobserved sudo descendants. Failed SSH callbacks retain
their private remote staging rather than removing inputs that a remote process
may still be using. The shared file lock is OS-managed. The parent project's ordinary hardware CI
also checks this sentinel after taking the device lock. Other projects or manual
tools must be kept exclusive during recovery; they do not inherit this check.
