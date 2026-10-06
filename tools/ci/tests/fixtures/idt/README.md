# Transport coverage regression reports

These are the sanitized native CI artifacts, with native verdicts unchanged.
They contain case names, counts and timing, without diagnostic bodies or firmware.

| Report | Source job | Native result |
|---|---|---|
| `rx72n-transport-complete-pass-70574.xml` | [70574](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70574) | 14 PASS |
| `rx65n-transport-complete-fail-70856.xml` | [70856](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70856) | 13 PASS / 1 FAIL |
| `rx671-transport-truncated-70882.xml` | [70882](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/70882) | 9 PASS; 5 mandatory cases unreported |

The RX671 report had no FAIL/ERROR/SKIP but omitted the last five unconditional
cases in the pinned FRQ_2.5.0 runner. It must fail completeness validation.
