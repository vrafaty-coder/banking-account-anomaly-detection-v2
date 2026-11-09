# Banking Account Anomaly Detection — V2

## Overview

This repository contains the experimental implementation of a research framework for explainable account-level anomaly detection in core banking systems.

The framework integrates behavioral account features and fund-flow evidence to investigate their contributions to anomaly detection.

The experiments use synthetic banking data, Isolation Forest models, score-fusion strategies, and repeated robustness evaluations.

All generated banking data is synthetic. No real customer or production banking data is included.

## Research Objectives

The project investigates:

- The effectiveness of behavioral account features for anomaly detection.
- The contribution of fund-flow features.
- The performance of combined behavioral and fund-flow models.
- The effectiveness of alternative anomaly-score fusion strategies.
- The stability of detection performance across independently generated synthetic datasets.
- The interpretation of anomaly alerts using account-level evidence.

## Synthetic Dataset

The primary V2 dataset contains:

| Property | Value |
|---|---|
| Accounts | 1,000 |
| Observation period | 6 months |
| Evaluation unit | Account-month |
| Account-month observations | 6,000 |
| Training period | Months 1–3 |
| Validation period | Month 4 |
| Test period | Months 5–6 |
| Injected validation anomalies | 50 |
| Injected test anomalies | 100 |

Five controlled anomaly scenarios are implemented:

1. S1 — Transaction count spike
2. S2 — Transaction amount shift
3. S3 — Inflow/outflow shift
4. S4 — Counterparty diversity spike
5. S5 — Combined moderate shift

Anomalies are injected into selected account-month observations while preserving the defined experimental allocation constraints.

## Detection Methods

Four Isolation Forest configurations are evaluated:

- Behavioral
- Fund Flow Core
- Combined Core
- Fund Flow Extended

Three fusion strategies are also evaluated:

- Union
- Mean Fusion
- Max Fusion

Performance is assessed using precision, recall, F1-score, average precision, and alert counts.

## Robustness Evaluation

Five independently seeded synthetic datasets, R1–R5, are used to examine the stability of the experimental results.

Each replication follows the same generation and evaluation framework while varying the configured random seeds.

The robustness experiments assess the consistency of individual detection models and fusion strategies.

## Repository Structure

```text
banking-account-anomaly-detection-v2/
├── config/
├── data/
│   ├── generated_v2/
│   │   └── releases/
│   │       └── v2_20261028/
│   └── robustness/
│       └── releases/
│           ├── R1/
│           ├── R2/
│           ├── R3/
│           ├── R4/
│           └── R5/
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_model_preparation.ipynb
│   ├── 02_model_preparation_threshold_comparison_reviewed.ipynb
│   ├── 03_robustness_evaluation.ipynb
│   └── 04_replication_evaluation.ipynb
├── results/
├── src/
│   ├── generate_data_v2.py
│   └── generate_robustness_data.py
├── tests/
│   └── test_robustness_generation.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Installation

Clone the repository and create a Python virtual environment.

```bash
python -m venv .venv
```

Activate the environment and install dependencies.

```bash
python -m pip install -r requirements.txt
```

The environment requires NumPy, pandas, Matplotlib, and scikit-learn.

To execute the notebooks interactively, a compatible Jupyter environment is also required.

## Data Availability

The repository includes account-level metadata, account-month features, evaluation labels, and experimental results.

Large transaction-level CSV files are excluded from Git tracking to keep the repository manageable.

The included account-month datasets support model-level evaluation without requiring the complete transaction files.

Full synthetic data regeneration is supported by the generation scripts and their associated configurations, subject to the documented release-generation procedures.

## Validation

Robustness-generation unit tests can be executed using:

```bash
python -m unittest discover -s tests -p "test_robustness_generation.py" -v
```

These tests verify generation-related invariants and reproducibility safeguards. They do not independently reproduce all published model metrics.

## Limitations

The experiments use synthetic rather than production banking data. Consequently, measured performance should not be interpreted as validated effectiveness in a live banking environment.

The injected scenarios represent controlled behavioral and fund-flow changes and do not establish that detected anomalies correspond to actual financial crime or fraud.

## Research Status

This repository preserves the V2 experimental implementation, evaluation artifacts, and R1–R5 robustness analysis associated with the research study.