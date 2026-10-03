---
activation: glob
globs: ["**/forecasting/**", "**/predictive/**", "**/anomaly/**", "**/timeseries/**", "**/time-series/**", "**/analytics-ml/**"]
description: Data & Predictive AI (category 7) — forecast time series, detect anomalies, predict from tabular data. Beat a naive baseline first, never take numbers from a chat LLM, and check the licence of the exact model weights before production.
trigger: glob
currency_pass: 2026-10-03
---
<!-- CONSUMER: Coding agents building forecasting, anomaly-detection or tabular-prediction features
     GOAL: Use the simplest model that beats a naive baseline, run it in the project's own worker, and keep chat LLMs out
     of the numbers.
     AGENT USAGE: Model choice across categories is ai/00-ai-model-selection.md; record a project's choice and the
     rejected alternative in project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as ai/00's selection workflow
     says. -->

# 7. Data & Predictive AI

Last content verification: 2026-10-03

**Purpose:** Forecast time series, detect anomalies, predict from structured data.

## Fabrik defaults

- **Beat a naive baseline first.** Every forecast is scored against seasonal naive and every anomaly detector against
  a robust z-score rule (median and MAD) on a held-out window that comes after the training window, never a random
  split. A heavier model ships only when it beats that baseline on the project's own data, and the margin goes in the
  project's decision ledger. The public leaderboards score every model relative to seasonal naive, and several
  classical methods land below it; on time-series anomaly benchmarks, simple statistical methods often win.
- **Never take numbers from a chat LLM.** A forecast or a tabular prediction comes from a model built for it, never from
  prompting a general LLM with the numbers: removing the LLM from LLM-based forecasters did not hurt accuracy and
  usually improved it, and on a context-aware benchmark most LLM forecasters were dominated by pretrained time-series
  models. An LLM may describe or explain a forecast, or turn text into a covariate; a qualitative judgement over numbers
  is ai/00's lane, and it is not a forecast.
- **Forecasting, in order.** Classical models first, through Nixtla's `statsforecast` (AutoARIMA, AutoETS, AutoTheta
  and seasonal naive). Then gradient-boosted trees on lag features, through `mlforecast` with LightGBM. A pretrained
  time-series foundation model only when there are many series, little history per series, or a zero-shot need:
  Amazon's Chronos first, because its current generation has open weights under an Apache licence, runs on CPU or
  GPU, and led the pretrained models on fev-bench in its paper. Prophet is in maintenance mode, so start nothing new on
  it.
- **Tabular prediction:** gradient-boosted trees (LightGBM, XGBoost, CatBoost) by default. A tabular foundation model
  is worth trying on small datasets, where it leads, but only one whose weights allow commercial use: TabICL (BSD
  licence) and Amazon's Mitra (Apache licence) do. AutoGluon (Apache licence) ensembles both families when a project
  wants AutoML.
- **Anomaly detection:** statistical first — a robust z-score, seasonal decomposition, or scikit-learn's
  `IsolationForest`; PyOD (BSD licence) when more detectors are needed, and River for streaming data. Salesforce's
  Merlion was archived on 2026-03-11 and ADTK has had no release since 2020, so adopt neither.
- **Run it in the project's own worker.** These libraries and the smaller foundation models run on CPU inside a
  core/75-workers-jobs worker that reads from and writes back to Postgres. A GPU model goes through
  core/76-gpu-workers. PostgresML, which ran models inside Postgres, went bust in 2025, and TimescaleDB's toolkit has
  no forecasting or anomaly functions, so neither is a home for this work.
- **Managed platforms only on a recorded need.** Amazon Forecast closed to new customers on 2024-07-29 and AWS points
  them to SageMaker Canvas, which also took over Autopilot's interface on 2023-11-30. Google's AutoML forecasting and
  BigQuery's `AI.FORECAST` (which hosts TimesFM, without covariates) and Azure ML's AutoML forecasting are live.
  DataRobot, H2O's Driverless AI and Nixtla's hosted TimeGPT publish no list prices.

**Anti-pattern:** a forecast whose only evaluation is a random train/test split, or a number produced by prompting a
chat LLM. The first leaks the future into training; the second is beaten by the baseline it never ran.

**Licence trap — open code, closed weights.** Several leading models ship permissively licensed code with
non-commercial weights: TimesFM's newest pretrained weights, while its earlier weights stay under an Apache licence;
every TabPFN generation after its second, which needs a commercial licence from Prior Labs for production, client work
or business decisions; and Salesforce's Moirai, released for research only. Read the licence of the exact weights you
download, not the repository's.

## The fleet today

No fleet repository uses a machine-learning or forecasting library, and no directory matches this pack's globs; it is
read by citation from ai/00. Every prediction in the fleet is hand-written: linear burn-rate projections, trailing-mean
spike rules, standard-deviation bands and one least-squares fit. That is the right start, and this pack's first rule
applies to it: each rule should be scored against the naive baseline before a library replaces it.

## Subcategories

- **Forecasting libraries:** Nixtla's `statsforecast`, `mlforecast` and `neuralforecast` (Apache licence), Darts
  (Apache licence; forecasting and anomaly detection), sktime (BSD licence), AutoGluon's time-series module.
- **Time-series foundation models:** Chronos (Apache-licensed open weights; Amazon also deploys it through SageMaker),
  TimesFM (Google; licence varies by weights generation), Datadog's Toto (Apache-licensed weights; GPU), IBM's Granite
  TinyTimeMixers (Apache licence; small enough for CPU), Moirai (research-only weights), Nixtla's TimeGPT (hosted,
  enterprise plans).
- **Tabular models:** gradient-boosted trees; TabICL, Mitra and TabDPT (commercial-safe); TabPFN (non-commercial
  weights for its newer generations); AutoGluon's tabular ensembles.
- **Anomaly detection:** scikit-learn, PyOD, River, Darts.
- **Managed:** SageMaker Canvas, Google's AutoML forecasting and BigQuery ML, Azure ML AutoML, DataRobot, H2O.
- **Compare on:** GIFT-Eval and fev-bench for forecasting (read the leakage and zero-shot columns), TabArena for
  tabular models, TSB-AD and ADBench for anomaly detection. A vendor's own "first place" claim is not a leaderboard
  reading.

**Use cases:** demand and capacity forecasting, usage and cost projection, metric anomaly alerts, lead or churn scoring.
