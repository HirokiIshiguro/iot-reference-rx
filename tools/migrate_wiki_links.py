#!/usr/bin/env python3
"""Migrate GitHub wiki links to local docs/ relative paths."""

import re
import os
import urllib.parse

# Wiki page name -> (language, local filename)
WIKI_MAP = {
    # Japanese pages
    "Home": ("ja", "Home.md"),
    "デバイスをAWS-IoTに登録する": ("ja", "デバイスをAWS-IoTに登録する.md"),
    "FreeRTOSプロジェクトの新規作成・インポート": ("ja", "FreeRTOSプロジェクトの新規作成・インポート.md"),
    "FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定": ("ja", "FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定.md"),
    "FreeRTOSプログラムを実行し、AWS-IoTに接続する": ("ja", "FreeRTOSプログラムを実行し、AWS-IoTに接続する.md"),
    "CK\u2010RX65N_Specification": ("ja", "CK-RX65N_Specification.md"),  # unicode hyphen
    "トラブルシューティング": ("ja", "トラブルシューティング.md"),
    "RXクラウドソリューション一覧": ("ja", "RXクラウドソリューション一覧.md"),
    "RX65N-Cloud-Kitでセンサデータを可視化する": ("ja", "RX65N-Cloud-Kitでセンサデータを可視化する.md"),
    # English pages
    "Home_Eng": ("en", "Home.md"),
    "Register-device-to-AWS-IoT": ("en", "Register-device-to-AWS-IoT.md"),
    "Creating-and-importing-a-FreeRTOS-project": ("en", "Creating-and-importing-a-FreeRTOS-project.md"),
    "Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core": ("en", "Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core.md"),
    "Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT": ("en", "Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT.md"),
    "FreeRTOS\u2010Plus\u2010TCP-Porting-Guide": ("en", "FreeRTOS-Plus-TCP-Porting-Guide.md"),  # unicode hyphen
    "RX-Cloud-Solutions": ("en", "RX-Cloud-Solutions.md"),
}

WIKI_BASE = "https://github.com/renesas/iot-reference-rx/wiki/"


def compute_relative_path(from_file, target_lang, target_file):
    """Compute relative path from from_file to target in docs/<lang>/."""
    from_dir = os.path.dirname(from_file)
    target_path = os.path.join("docs", target_lang, target_file)
    return os.path.relpath(target_path, from_dir).replace("\\", "/")


def replace_wiki_links(content, from_file):
    """Replace GitHub wiki URLs with relative paths."""
    def replacer(match):
        url = match.group(0)
        # Remove base URL
        path_part = url[len(WIKI_BASE):]
        # URL-decode
        decoded = urllib.parse.unquote(path_part)
        # Split anchor
        anchor = ""
        if "#" in decoded:
            decoded, anchor = decoded.split("#", 1)
            anchor = "#" + anchor

        # Look up in map
        if decoded in WIKI_MAP:
            lang, filename = WIKI_MAP[decoded]
            rel = compute_relative_path(from_file, lang, filename)
            return rel + anchor
        else:
            # Try URL-encoded variants
            for key in WIKI_MAP:
                if urllib.parse.quote(key, safe="-_") == path_part.split("#")[0]:
                    lang, filename = WIKI_MAP[key]
                    rel = compute_relative_path(from_file, lang, filename)
                    return rel + anchor
            # Not found, leave as-is
            print(f"  WARNING: No mapping for wiki page: {decoded}")
            return url

    # Match wiki URLs (with optional anchor)
    pattern = re.escape(WIKI_BASE) + r'[^\s\)"]+'
    return re.sub(pattern, replacer, content)


def process_directory(docs_dir):
    """Process all markdown files in docs/."""
    count = 0
    for root, dirs, files in os.walk(docs_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            filepath = os.path.join(root, f)
            with open(filepath, "r", encoding="utf-8") as fh:
                original = fh.read()

            updated = replace_wiki_links(original, filepath)
            if updated != original:
                with open(filepath, "w", encoding="utf-8") as fh:
                    fh.write(updated)
                count += 1
                print(f"Updated: {filepath}")

    print(f"\nTotal files updated: {count}")


if __name__ == "__main__":
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    process_directory(docs_dir)
