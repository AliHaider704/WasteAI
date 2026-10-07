<!-- File: server/eval/results.md -->
Status: **NOT RUN YET.** No numbers below are measured; fill them from `runs/*.md`. Do not pick a winner from published accuracy (D-009).

## Comparison (our photos, 1 thread, CPU)
| Candidate | Photos | Top-1 | Top-3 | p50 ms | RSS MB | ONNX MB | Model license | Dataset license | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| ecovision_mobilenetv3 | - | - | - | - | - | - | verify | verify | - |
| wastewise YOLOv8n-cls | - | - | - | - | - | - | verify (Ultralytics YOLOv8 is AGPL-3.0: flag/reject) | verify | - |
| rootstrap | - | - | - | - | - | - | verify | verify | - |
| mobilenet_v2_Garbage | - | - | - | - | - | - | verify | verify | - |

## Selection rule
Highest top-1 (category and group level) on our photos, then RSS <= ~150 MB and p50 <= ~300 ms on the server, then a permissive license (Apache-2.0 / MIT / BSD). Reject AGPL and non-commercial unless the owner accepts it in DECISIONS.

## Chosen model
TBD. Reasons: TBD. Model URL: TBD. SHA256: TBD.
