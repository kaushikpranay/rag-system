# Vector Database & pgvector Benchmark Report

**Generated:** 2026-07-28 16:56:19 UTC  
**Database System:** PostgreSQL (pgvector v0.8.2)  
**Dataset Size:** 821 vectors (13 MB)  
**Connection Status:** Active (Pool Health: HEALTHY)

---

## Executive Summary & SLA Metrics

| Metric Category | Metric | Measured Value | SLA Target | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ANN Accuracy** | Recall@1 | **100.00%** | &ge; 70.0% | PASSED |
| **ANN Accuracy** | Recall@3 | **100.00%** | &ge; 75.0% | PASSED |
| **ANN Accuracy** | Recall@5 | **100.00%** | &ge; 80.0% | PASSED |
| **Ranking Quality** | MRR | **1.0000** | &ge; 0.70 | PASSED |
| **Ranking Quality** | NDCG@5 | **1.0000** | &ge; 0.75 | PASSED |
| **Latency** | Average Latency | **10.68 ms** | &lt; 50 ms | PASSED |
| **Latency** | P50 Latency | **10.39 ms** | &lt; 30 ms | PASSED |
| **Latency** | P95 Latency | **12.75 ms** | &lt; 250 ms | PASSED |
| **Latency** | P99 Latency | **12.86 ms** | &lt; 500 ms | PASSED |
| **Index Status** | HNSW Index Usage | **PASSED (HNSW Index Scan Active)** | HNSW Index Scan | PASSED |
| **Infra Health** | Active Connections | **2** | &le; 20 | PASSED |
| **Infra Health** | Pool Status | **HEALTHY** | HEALTHY | PASSED |

---

## Similarity Threshold Calibration

- **Recommended Threshold:** `0.3`
- **Peak F1 Score:** `0.6726`

### Precision-Recall-F1 Grid
| Similarity Threshold | Precision | Recall | F1 Score |
| :---: | :---: | :---: | :---: |
| `0.2` | 0.4000 | 1.0000 | 0.5714 |
| `0.3` | 0.5205 | 0.9500 | 0.6726 |
| `0.35` | 0.5370 | 0.7250 | 0.6170 |
| `0.4` | 0.5610 | 0.5750 | 0.5679 |
| `0.45` | 0.5385 | 0.5250 | 0.5316 |
| `0.5` | 0.5135 | 0.4750 | 0.4935 |
| `0.55` | 0.5135 | 0.4750 | 0.4935 |
| `0.6` | 0.6000 | 0.4500 | 0.5143 |
| `0.7` | 0.8947 | 0.4250 | 0.5763 |

---

## Regression Analysis

> [!NOTE]
> **Detected Regressions:** None Detected

All 15 vector database verification checks passed.
