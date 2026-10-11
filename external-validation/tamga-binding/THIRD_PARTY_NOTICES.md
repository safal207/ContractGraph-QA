# Tamga source packet notices

[utf8-source-packet.json](utf8-source-packet.json) contains unchanged UTF-8 source contents from [goun7/tamga-protocol](https://github.com/goun7/tamga-protocol), encoded as JSON strings for the bounded historical verifier replay. Tamga implementation and fixture source credit remains with goun7 and the upstream contributors. The packet wrapper and this replay package were prepared by Alexey Safonov (safal207), with AI assistance.

The selected upstream revisions distribute these files under the Apache License, Version 2.0. A verbatim copy of the upstream [LICENSE at the fixed revision](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/LICENSE) is included as [TAMGA_LICENSE.txt](TAMGA_LICENSE.txt). The license has the same Git blob `d645695673349e3947e8e5ae42332d0ac3164cd7` at both selected revisions. No source text or existing notices inside the six contents strings were changed. JSON encoding is the packaging change; the decoded UTF-8 bytes retain their upstream Git blob identities.

| Packet key | Upstream revision | Source path | Git blob SHA-1 |
|---|---|---|---|
| `before_verify` | `7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b` | [`tools/verify_pairing_fixture.py`](https://github.com/goun7/tamga-protocol/blob/7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b/tools/verify_pairing_fixture.py) | `8195c659d38d7e94d71c8606a40ca54ba1f92a5e` |
| `after_verify` | `c62d4a822d7e3546931197905e137d0eb6fb490e` | [`tools/verify_pairing_fixture.py`](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/tools/verify_pairing_fixture.py) | `bd72f616b9431322534c1b803cf23c58c09aa83b` |
| `keccak` | `c62d4a822d7e3546931197905e137d0eb6fb490e` | [`tools/keccak256.py`](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/tools/keccak256.py) | `e4c6724b3df72f12b93ba756b6bf2f105d2d4a3a` |
| `fixture` | `c62d4a822d7e3546931197905e137d0eb6fb490e` | [`docs/pairing/pairing-fixture.json`](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/docs/pairing/pairing-fixture.json) | `675142be41feef6847be069b62bdf9c7174ca1e8` |
| `delivery` | `c62d4a822d7e3546931197905e137d0eb6fb490e` | [`docs/pairing/delivery.stdout`](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/docs/pairing/delivery.stdout) | `e561bdbf79a19065b7a0652fb2d67e3c5494f728` |
| `input` | `c62d4a822d7e3546931197905e137d0eb6fb490e` | [`docs/pairing/input.json`](https://github.com/goun7/tamga-protocol/blob/c62d4a822d7e3546931197905e137d0eb6fb490e/docs/pairing/input.json) | `788df9a7f66f742d3efe4ac04602c0457cee3e04` |

These are the exact historical sources used by the recorded replay. The fixture's upstream provenance labels do not independently establish execution, settlement, or authenticity; the case and EVIDENCE.md retain those boundaries. No current-release security guarantee or upstream endorsement of this replay package is implied.
