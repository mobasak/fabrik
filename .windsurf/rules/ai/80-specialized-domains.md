---
activation: glob
globs: ["**/robotics/**", "**/recommendation/**", "**/recommender/**", "**/synthetic-data/**", "**/threat-detection/**", "**/healthcare-ai/**", "**/bio-ai/**", "**/edge-ai/**", "**/moderation/**", "**/generative-design/**"]
description: Specialized AI domains (categories 8–15) — Robotics, Synthetic Data, Recommendation, Cybersecurity, Bio/Healthcare, Edge/Embedded, Governance/Trust/Safety, Generative Design. NOT covered by Kilo — use domain-specific tools.
trigger: glob
---
<!-- CONSUMER: Coding agents building specialized-domain AI + Traycer (tech-plan)
     GOAL: For these domains use the established domain tool, not a general LLM and not Kilo.
     TRAYCER USAGE: Context File for robotics / recommendation / security-ML / healthcare / edge / moderation / generative-design tickets.
     AGENT USAGE: Identify the exact domain below and reach for its named tool. None of these are Kilo categories. -->

# Specialized AI Domains (categories 8–15)

These are domain-specialized — **not** Kilo categories. Use the named domain tools; don't substitute a general LLM.

## 8. Robotics & Control
Perceive, plan, act in the physical world. **Examples:** Boston Dynamics Spot, NVIDIA Isaac, OpenAI Robotics. **Use cases:** manipulation, drones, warehouse automation.

## 9. Synthetic Data & Simulation
Generate labeled/photorealistic training data. **Examples:** NVIDIA Omniverse Replicator, Unity Perception, Synthesis AI. **Use cases:** training-data generation when real data is limited.

## 10. Recommendation & Personalization
Predict user preference/behavior. **Examples:** Netflix recommender, Spotify Discovery, Amazon Personalize. **Use cases:** content ranking, adaptive feeds, product recommendations.

## 11. Cybersecurity & Threat Detection
Detect anomalies/malicious behavior. **Examples:** Darktrace, CrowdStrike, Palo Alto Cortex. **Use cases:** network security, fraud detection, intrusion response.

## 12. Bio-AI / Healthcare
Model biological/medical data. **Examples:** DeepMind AlphaFold, Insilico Medicine, PathAI. **Use cases:** protein folding, diagnostics, drug discovery.

## 13. Edge / Embedded
Run models on constrained hardware. **Examples:** TensorFlow Lite, Apple Neural Engine, Qualcomm AI Engine. **Use cases:** real-time on-device inference without cloud.

## 14. Governance / Trust / Safety
Detect bias, hallucinations, unsafe content. **Examples:** LLaMA Guard, Perspective API, Azure Content Safety. **Use cases:** content moderation, compliance, model interpretability.

A moderation, spam or prompt-injection check with a fixed answer (allow or flag, a short list of harm classes) on content at volume may run in ai/00's decision-model lane, through fabrik-lib's `decision-gate`: independent tests found TypeSafe's Jev about as accurate as small LLMs at spotting prompt injection, and in one fraud-classification test it recalled 93% of the fraud an LLM recalled 62% of (`/opt/fabrik/docs/reference/jev-decision-model-map.md` (hub-only)). It flags and routes. A human or a deterministic rule still owns any removal that cannot be undone, and whoever writes the content can steer the answer, so it is never the only guard.

## 15. Generative Design & Simulation
Create optimized designs via algorithms. **Examples:** Autodesk Generative Design, nTopology, OpenAI Shap-E. **Use cases:** architecture, manufacturing, product design.
