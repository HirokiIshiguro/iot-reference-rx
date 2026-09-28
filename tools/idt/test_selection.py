"""Explicit case selection for the pinned FRQ_2.5.0 OTA MQTT group."""

OTA_TEST_IDS = (
    "OTAE2EGreaterVersion", "OTAE2ESameVersion", "OTAE2EPreviousVersion",
    "OTAE2EIncorrectSigningAlgorithm", "OTAE2EUntrustedCertificate",
    "OTAE2EUnsignedImage", "OTAE2EBackToBackDownload", "OTAE2ECancelThenUpdate",
    "OTAE2EDisconnectAndResume", "OTAE2EDisconnectCancelUpdate",
    "OTAE2ETwoUpdatesCancelFirst", "OTAE2EImageCrashed",
    "OTAE2ERollbackIfUnableToConnectAfterUpdate",
)


def parse_test_ids(value):
    if value is None:
        return ()
    selected = tuple(item.strip() for item in value.split(","))
    if not selected or any(item not in OTA_TEST_IDS for item in selected):
        raise ValueError("Select explicit FRQ_2.5.0 OTA MQTT test IDs; empty/unknown IDs are invalid")
    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate OTA test IDs are invalid")
    return selected
