# Banking Account Anomaly Detection

An experimental machine learning project exploring anomaly detection in core banking systems using behavioral and fund-flow information.

The project investigates whether combining account activity patterns with monetary flow characteristics can improve anomaly detection compared with using either feature group separately.

The implementation uses Python, Isolation Forest, synthetic banking transactions, and several model fusion strategies.

## Approach

The experiments use synthetic transaction data representing 1,000 accounts over six months, aggregated into 6,000 account-month observations.

Five anomaly scenarios were simulated, including unusual transaction frequency, transaction amounts, inflow/outflow patterns, counterparty diversity, and combined behavioral changes.

Four Isolation Forest configurations were evaluated:

- Behavioral features
- Fund Flow Core features
- Combined Behavioral and Fund Flow features
- Fund Flow Extended features

Three additional strategies combine the outputs of separately trained detectors: Union, Mean Fusion, and Max Fusion.

The dataset was divided chronologically into training (months 1–3), validation (month 4), and testing (months 5–6).

## Key Findings

- Combining behavioral and core fund-flow features increased recall from 0.33 to 0.43, although false positives also increased.
- Max Fusion achieved an F1-score of 0.3173, with fewer false positives than the Combined Core model.
- Across five independent synthetic replications, Max Fusion consistently achieved higher F1 than Combined Core, while Combined Core achieved higher average precision.
- Descriptive evidence was generated for all 171 Max Fusion alerts, identifying the dominant detector and prominent feature deviations.

The results highlight trade-offs between detection coverage, false positives, and anomaly-ranking quality.

## Technologies

- Python
- pandas and NumPy
- scikit-learn (Isolation Forest)
- Matplotlib
- Jupyter Notebook

## Repository Structure

- `src/` — Synthetic data generation scripts
- `config/` — Experiment configurations
- `data/` — Generated account-level datasets and replication artifacts
- `notebooks/` — Data exploration, model evaluation, and robustness experiments
- `results/` — Experimental outputs
- `tests/` — Data-generation validation tests

## Getting Started

Clone the repository:

```bash
git clone https://github.com/vrafaty-coder/banking-account-anomaly-detection-v2.git
cd banking-account-anomaly-detection-v2
```

Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Activate the virtual environment before installing dependencies. The notebooks can then be explored using Jupyter.

To run the data-generation tests:

```bash
python -m unittest discover -s tests -p "test_robustness_generation.py" -v
```

## Research Paper

**Integrating Behavioral and Fund-Flow Evidence for Explainable Anomaly Detection in Core Banking**

Vahideh Rafati Porshokooh

Informatics Services Corporation, Tehran, Iran

This repository contains the experimental implementation and supporting artifacts associated with the research.

## Limitations

The experiments use synthetic banking data and predefined anomaly scenarios. The results have not been validated using production banking transactions.

The generated explanations describe unusual feature values rather than providing causal explanations of model decisions.

The framework is intended for research and experimentation, not production deployment.
