# Documentation / ドキュメント

This directory contains documentation migrated from the [GitHub Wiki](https://github.com/renesas/iot-reference-rx/wiki).

## Structure / 構造

```
docs/
├── en/          # English documentation
├── ja/          # 日本語ドキュメント
├── images/      # Images (shared between languages)
├── _Sidebar.md  # Navigation (from Wiki sidebar)
├── _Footer.md   # Footer (from Wiki footer)
└── README.md    # This file
```

## English / 英語

| Page | Description |
|------|-------------|
| [Home](en/Home.md) | Getting Started Guide overview |
| [Register device to AWS IoT](en/Register-device-to-AWS-IoT.md) | AWS IoT Thing/Certificate setup |
| [Creating and importing a FreeRTOS project](en/Creating-and-importing-a-FreeRTOS-project.md) | e2 studio project import / PG |
| [Configure AWS IoT Core connection](en/Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core.md) | AWS endpoint / credential config |
| [Execute and connect to AWS IoT](en/Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT.md) | Run demo and verify connection |
| [FreeRTOS-Plus-TCP Porting Guide](en/FreeRTOS-Plus-TCP-Porting-Guide.md) | Porting to other RX MCUs |
| [RX Cloud Solutions](en/RX-Cloud-Solutions.md) | Overview of RX cloud solutions |

## 日本語 / Japanese

| ページ | 説明 |
|--------|------|
| [Home](ja/Home.md) | Getting Start Guide 概要 |
| [デバイスをAWS-IoTに登録する](ja/デバイスをAWS-IoTに登録する.md) | AWS IoT Thing/証明書のセットアップ |
| [FreeRTOSプロジェクトの新規作成・インポート](ja/FreeRTOSプロジェクトの新規作成・インポート.md) | e2 studio プロジェクトのインポート / PG |
| [AWS IoT Core接続設定](ja/FreeRTOSプロジェクトでAWS-IoT-Coreへの接続に必要な設定.md) | AWS エンドポイント / クレデンシャル設定 |
| [FreeRTOSプログラム実行・AWS IoT接続](ja/FreeRTOSプログラムを実行し、AWS-IoTに接続する.md) | デモ実行と接続確認 |
| [CK-RX65N Specification](ja/CK-RX65N_Specification.md) | CK-RX65N V1/V2 仕様比較 |
| [RXクラウドソリューション一覧](ja/RXクラウドソリューション一覧.md) | RX クラウドソリューション概要 |
| [RX65N-Cloud-Kitでセンサデータを可視化する](ja/RX65N-Cloud-Kitでセンサデータを可視化する.md) | センサデータ可視化 |
| [トラブルシューティング](ja/トラブルシューティング.md) | よくある問題と解決方法 |

## Migration Notes / 移行メモ

- Migrated on 2026-03-03 from GitHub Wiki
- Images use GitHub CDN URLs (original hosting); local copies in `images/`
- Cross-links updated from Wiki URLs to relative paths
- Source: `tools/migrate_wiki_links.py`
