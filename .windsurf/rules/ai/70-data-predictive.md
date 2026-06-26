---
activation: glob
globs: ["**/forecasting/**", "**/predictive/**", "**/anomaly/**", "**/timeseries/**", "**/time-series/**", "**/analytics-ml/**"]
description: Data & Predictive AI (category 7) — analyze structured data, forecast, detect anomalies (DataRobot, H2O.ai, Vertex AI, SageMaker). Not covered by Kilo — use specialized domain tools.
trigger: glob
---
<!-- CONSUMER: Coding agents building forecasting/anomaly/analytics features + Traycer (tech-plan)
     GOAL: Use a real ML/forecasting platform, not a general LLM, for structured-data prediction.
     TRAYCER USAGE: Context File for forecasting / anomaly-detection / predictive-analytics tickets.
     AGENT USAGE: Reach for a dedicated predictive platform. Kilo doesn't cover this — don't substitute a chat LLM for time-series forecasting. -->

# 7. Data & Predictive AI

**Purpose:** Analyze structured data, forecast, detect anomalies.

## Examples
DataRobot, H2O.ai, Google Vertex AI, AWS SageMaker.

## Kilo coverage
❌ Specialized — not a Kilo category. Use a dedicated predictive/ML platform.

**Use cases:** business analytics, forecasting, anomaly detection.

**Anti-pattern:** using a general chat LLM for structured-data forecasting instead of a proper predictive model.
