# Vector Database & pgvector Benchmark Report

**Generated:** 2026-07-29 17:08:14 UTC  
**Target Endpoint:** `127.0.0.1:5432`  
**Database System:** PostgreSQL (pgvector v0.8.2)  
**Dataset Size:** 11,421 active vectors (155 MB)  
**Connection Status:** Active (Pool Health: HEALTHY)

---

## Executive Summary & SLA Metrics

| Metric Category | Metric | Measured Value | SLA Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ANN Accuracy** | Recall@1 | **86.67%** | &ge; 70.0% | PASSED |
| **ANN Accuracy** | Recall@3 | **84.44%** | &ge; 75.0% | PASSED |
| **ANN Accuracy** | Recall@5 | **80.00%** | &ge; 80.0% | PASSED |
| **Ranking Quality** | MRR | **0.8667** | &ge; 0.70 | PASSED |
| **Ranking Quality** | NDCG@5 | **0.8219** | &ge; 0.75 | PASSED |
| **Latency Distribution** | Min Latency | **0.00 ms** | N/A | INFORMATIONAL |
| **Latency Distribution** | P50 Latency | **6.97 ms** | &lt; 30 ms | PASSED |
| **Latency Distribution** | P90 Latency | **11.39 ms** | &lt; 150 ms | PASSED |
| **Latency Distribution** | P95 Latency | **11.70 ms** | &lt; 250 ms | PASSED |
| **Latency Distribution** | P99 Latency | **13.72 ms** | &lt; 500 ms | PASSED |
| **Latency Distribution** | Max Latency | **14.34 ms** | N/A | INFORMATIONAL |
| **Latency Distribution** | Average Latency | **6.78 ms** | &lt; 50 ms | PASSED |
| **Index Status** | HNSW Index Usage | **PASSED (HNSW Index Scan Active)** | HNSW Index Scan | PASSED |
| **Infra Health** | Active Connections | **3** | &le; 20 | PASSED |
| **Infra Health** | Pool Status | **HEALTHY** | HEALTHY | PASSED |

---

## Similarity Threshold Calibration

- **Recommended Threshold:** `0.3`
- **Peak F1 Score:** `0.4810`

### Precision-Recall-F1 Grid
| Similarity Threshold | Precision | Recall | F1 Score |
| :---: | :---: | :---: | :---: |
| `0.2` | 0.1558 | 1.0000 | 0.2697 |
| `0.3` | 0.3455 | 0.7917 | 0.4810 |
| `0.35` | 0.3556 | 0.6667 | 0.4638 |
| `0.4` | 0.3448 | 0.4167 | 0.3774 |
| `0.45` | 0.5000 | 0.4167 | 0.4545 |
| `0.5` | 0.8571 | 0.2500 | 0.3871 |
| `0.55` | 1.0000 | 0.1667 | 0.2857 |
| `0.6` | 1.0000 | 0.1250 | 0.2222 |
| `0.7` | 0.0000 | 0.0000 | 0.0000 |

---

## Regression Analysis

> [!NOTE]
> **Detected Regressions:** None Detected

All 15 vector database verification checks passed.
