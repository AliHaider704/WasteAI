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


## A2 run 2026-10-07 (96 photos, 12 categories, 8 per category; photo source UNVERIFIED)

## emily_imagenet

| photos | top-1 | top-3 | top-1 group | p50 ms | p95 ms | RSS MB | ONNX MB | load s |
|---|---|---|---|---|---|---|---|---|
| 96 | 39.6% | 61.5% | 50.0% | 10 | 11 | 89 (peak 110) | 8.5 | 0.1 |

| category | n | top-1 | top-3 |
|---|---|---|---|
| battery | 8 | 88% | 100% |
| cardboard | 8 | 100% | 100% |
| carton_beverage | 8 | 0% | 0% |
| ewaste_small | 8 | 0% | 0% |
| general_residual | 8 | 12% | 25% |
| glass | 8 | 75% | 100% |
| metal_aluminum | 8 | 38% | 88% |
| metal_steel | 8 | 25% | 62% |
| organic_food | 8 | 12% | 25% |
| paper | 8 | 12% | 50% |
| plastic_unknown | 8 | 50% | 100% |
| textile | 8 | 62% | 88% |

## emily_unit

| photos | top-1 | top-3 | top-1 group | p50 ms | p95 ms | RSS MB | ONNX MB | load s |
|---|---|---|---|---|---|---|---|---|
| 96 | 25.0% | 51.0% | 37.5% | 10 | 10 | 90 (peak 110) | 8.5 | 0.0 |

| category | n | top-1 | top-3 |
|---|---|---|---|
| battery | 8 | 25% | 62% |
| cardboard | 8 | 62% | 100% |
| carton_beverage | 8 | 0% | 0% |
| ewaste_small | 8 | 0% | 0% |
| general_residual | 8 | 0% | 12% |
| glass | 8 | 38% | 88% |
| metal_aluminum | 8 | 0% | 62% |
| metal_steel | 8 | 12% | 25% |
| organic_food | 8 | 0% | 0% |
| paper | 8 | 62% | 100% |
| plastic_unknown | 8 | 50% | 100% |
| textile | 8 | 50% | 62% |

## wastewise

| photos | top-1 | top-3 | top-1 group | p50 ms | p95 ms | RSS MB | ONNX MB | load s |
|---|---|---|---|---|---|---|---|---|
| 96 | 32.3% | 47.9% | 40.6% | 5 | 5 | 78 (peak 96) | 5.5 | 0.0 |

| category | n | top-1 | top-3 |
|---|---|---|---|
| battery | 8 | 50% | 88% |
| cardboard | 8 | 88% | 100% |
| carton_beverage | 8 | 0% | 0% |
| ewaste_small | 8 | 0% | 0% |
| general_residual | 8 | 0% | 0% |
| glass | 8 | 75% | 100% |
| metal_aluminum | 8 | 62% | 88% |
| metal_steel | 8 | 12% | 38% |
| organic_food | 8 | 0% | 0% |
| paper | 8 | 38% | 88% |
| plastic_unknown | 8 | 62% | 75% |
| textile | 8 | 0% | 0% |

| model | licence | verdict |
|---|---|---|
| emilyyy04/trash_classifier (MobileNetV2, tv10, imagenet norm) | MIT per HF card; base google/mobilenet_v2_1.0_224; training data undocumented | ACCEPTED with caveat |
| SriramRokkam/wastewise-garbage-cls (YOLOv8n-cls) | README Apache-2.0, file metadata AGPL-3.0 (conflict) | REJECTED |

Active model sha256: f0f86dde57c548c5741ac9a69b486ed04256f0a5df02e8d3244f88db7564dbf4
