#!/usr/bin/env python3
"""
Device Configuration Loader for CI/CD Test Scripts
デバイス ID からハードウェア構成情報を取得するユーティリティ。

device_config.json にデバイスごとの COM ポート、E2 Lite シリアル番号、
AWS Thing 名等を定義し、--device-id で指定して使う。

証明書・秘密鍵は CI/CD Variables (File 型) で管理し、
環境変数名はデバイス ID から自動生成:
  rx72n-01 → AWS_CLIENT_CERT_RX72N_01 / AWS_PRIVATE_KEY_RX72N_01
"""

import json
import os


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "device_config.json")


def load_device_config(device_id, config_path=None):
    """デバイス ID から構成情報を取得する。

    Args:
        device_id: デバイス ID (例: "rx72n-01")
        config_path: device_config.json のパス (省略時は同ディレクトリ)

    Returns:
        dict: デバイス構成情報 (aws_endpoint, device_id 含む)

    Raises:
        FileNotFoundError: config ファイルが見つからない
        ValueError: 指定の device_id が config に存在しない
    """
    path = config_path or DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        config = json.load(f)

    if device_id not in config["devices"]:
        available = ", ".join(config["devices"].keys())
        raise ValueError(
            f"Unknown device ID: {device_id} (available: {available})"
        )

    device = dict(config["devices"][device_id])
    device["aws_endpoint"] = config["aws_endpoint"]
    device["aws_region"] = config.get("aws_region", "ap-northeast-1")
    device["device_id"] = device_id

    # 環境変数オーバーライド: CI/CD Variables (hardware-config) からの値を優先する。
    # USB 抜き差しで COM 番号が変わった場合、JSON を変更せずに CI/CD Variables のみで対応可能。
    env_overrides = {
        "command_port": "COMMAND_PORT",
        "log_port": "UART_PORT",
        "e2lite_serial": "E2LITE_SERIAL",
        "mac_address": "MAC_ADDR",
    }
    for key, env_var in env_overrides.items():
        val = os.environ.get(env_var)
        if val:
            device[key] = val

    return device


def device_id_to_env_suffix(device_id):
    """デバイス ID を環境変数サフィックスに変換する。

    "rx72n-01" → "RX72N_01"
    """
    return device_id.replace("-", "_").upper()


def get_cert_env_var_name(device_id):
    """デバイス ID → 証明書環境変数名"""
    return f"AWS_CLIENT_CERT_{device_id_to_env_suffix(device_id)}"


def get_key_env_var_name(device_id):
    """デバイス ID → 秘密鍵環境変数名"""
    return f"AWS_PRIVATE_KEY_{device_id_to_env_suffix(device_id)}"
