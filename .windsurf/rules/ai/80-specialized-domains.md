---
activation: glob
globs: ["**/robotics/**", "**/recommendation/**", "**/recommender/**", "**/synthetic-data/**", "**/threat-detection/**", "**/healthcare-ai/**", "**/bio-ai/**", "**/edge-ai/**", "**/moderation/**", "**/generative-design/**"]
description: Specialized AI domains (categories 8–15) — moderation and trust & safety, prompt-injection defence, recommendation, synthetic data, regulated health AI, on-device inference, robotics and generative design. Use the pack that owns a topic first; layer moderation with deterministic rules and never let a classifier be the only guard; beat a simple baseline before a heavy recommender; synthetic data is not a privacy guarantee; classify a health feature before building it.
trigger: glob
currency_pass: 2026-10-03
---
<!-- CONSUMER: Coding agents building moderation, recommendation, synthetic-data, health, on-device, robotics or
     generative-design features
     GOAL: Route each domain to the pack that owns it, and for the domains only this pack owns, start from the simplest
     measured option and the licence or regulation that can stop a launch.
     AGENT USAGE: Model choice across categories is ai/00-ai-model-selection.md; record a project's choice and the
     rejected alternative in project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as ai/00's selection workflow
     says. -->

# Specialized AI Domains (categories 8–15)

Last content verification: 2026-10-03

**Purpose:** Moderate content, defend agents against injected instructions, recommend items, generate synthetic data,
build health features without becoming a medical device by accident, and run models on devices, robots and design
tools.

## Fabrik defaults

- **Use the pack that owns the topic first.** Fraud and abuse are `saas/87-abuse-detection.md`; account takeover and
  credential stuffing are `core/35-security-auth.md`. On-device vision models are `ai/20-vision.md`, and a local LLM
  in a desktop app is `desktop-app/72-desktop.md`; no pack yet covers on-device models in a mobile app, so the runtime
  names below are where that starts. Forecasting and anomaly detection are `ai/70-data-predictive.md`. Prompt
  injection in code agents is `ai/60-code.md`, and in watchdog loops `core/60-watchdog.md`. This pack covers what none
  of them does, and points at them for the rest.
- **Moderation is layered, and the layers are measured.** Deterministic rules come first: block lists, rate limits,
  size and link limits. A classifier comes second, and it only flags and routes. A person or a deterministic rule
  makes any decision that cannot be undone. Before choosing a classifier, label at least 200 of the project's own
  items, in the project's own languages, and score precision and recall per harm class. A vendor's benchmark is not
  the project's content.
  - **Hosted, when the content may leave the box:** OpenAI's `omni-moderation` endpoint is free. It takes text and
    images and scores 13 harm classes, and images count for only some of them. Azure AI Content Safety has a free tier
    of 5,000 text records a month; its harm classes were trained on eight languages, and its Prompt Shields were
    tested in English only. AWS Bedrock Guardrails' Standard tier lists Turkish as supported for content filters and
    prompt attacks, meaning tested but not tuned; that tier must be selected explicitly and uses cross-Region
    inference, and the Classic tier has no Turkish at all. No hosted option documents tuning for Turkish, so a
    Turkish-language product measures on its own Turkish sample before it relies on any of them.
  - **Self-hosted, when the content must not leave the box:** IBM's Granite Guardian and Alibaba's Qwen guard models
    are Apache-licensed, but Granite Guardian is trained and tested on English only, so for Turkish the Qwen guard
    models, which cover 119 languages and dialects, are the Apache-licensed option. OpenAI's `gpt-oss-safeguard` is
    Apache-licensed and text-only, and classifies against a policy written at inference time, but it is a research
    preview. Meta's Llama Guard is gated under the Llama community licence, with its acceptable-use policy and a
    "Built with Llama" attribution; that policy withholds the multimodal models' rights from companies based in the
    EU, and its published multilingual recall is 43%. Google's ShieldGemma is English-only, under the Gemma terms.
    Read the exact licence before shipping any of them.
  - **Refused for new work:** Google's Perspective API, which is sunsetting, ends after 2026 and offers no migration
    support. Azure Content Moderator, deprecated and retiring on 2027-03-15; its replacement is Azure AI Content
    Safety. Amazon Comprehend's toxicity detection, which is English-only, and whose prompt-safety classification
    closed to new customers on 2026-04-30.

  A moderation, spam or prompt-injection check with a fixed answer (allow or flag, a short list of harm classes) on content at volume may run in ai/00's decision-model lane, through fabrik-lib's `decision-gate`: independent tests found TypeSafe's Jev about as accurate as small LLMs at spotting prompt injection, and in one fraud-classification test it recalled 93% of the fraud an LLM recalled 62% of (`/opt/fabrik/docs/reference/jev-decision-model-map.md` (hub-only)). It flags and routes. A human or a deterministic rule still owns any removal that cannot be undone, and whoever writes the content can steer the answer, so it is never the only guard.
- **Prompt injection is answered by design, not by a detector.** No detector is a security boundary. A USENIX Security
  study bypassed twelve published defences with adaptive attacks, above 90% success against most of them, detectors
  included. OWASP's entry on prompt injection says it is unclear whether fool-proof prevention exists, and the UK NCSC
  says models do not enforce a boundary between instructions and data. So: frame every piece of external content as
  data, never as instructions (tojlo-mail's email triage already does). Give the model's tools the least privilege the
  task needs. Require a person's approval before any action that cannot be undone. Validate the output format before
  acting on it. A detector — Llama Prompt Guard, Azure Prompt Shields, Bedrock's prompt-attack filter — is a signal to
  log and route on, never the gate.
- **Recommendation starts with a baseline you can query.** First popularity, then item-to-item co-occurrence ("bought
  together", "viewed after"), both as SQL over the project's own Postgres tables. Next comes `implicit` (ALS or BPR;
  MIT licence, maintained) once there are enough interactions per item. A heavier model ships only when it beats that
  baseline on recall or NDCG measured on a held-out window after the training window, and then in an online A/B test.
  The evidence is consistent: of the seven neural recommenders a RecSys study could reproduce, simple
  nearest-neighbour heuristics often beat six, and the seventh did not consistently beat a tuned linear method; a 2025
  study found well-tuned simple baselines beating published diffusion recommenders. LightFM is refused for new work;
  it has had no release since 2023-03. A hosted service — Google's AI Commerce Search (formerly Vertex AI Search for
  commerce), Amazon Personalize, Recombee — only when the SQL baseline has plateaued and the interaction data may
  leave the box.
- **Synthetic data is neither a privacy guarantee nor a replacement for real data.** A USENIX Security study found
  synthetic data gives no better privacy-utility trade-off than traditional anonymisation, with highly variable
  privacy gain. Personal data stays under the project's data rules even after it is synthesised. Use synthetic records
  for tests, fixtures and demos (Faker), and for augmentation only with the real data kept in the mix: training on
  each generation's synthetic output instead of real data degrades a model and loses the tails of the distribution,
  while accumulating synthetic data beside the real data avoids it. Licence trap: SDV is under the Business Source
  License, which forbids using it for a synthetic-data service and changes to MIT only four years after each release.
  synthcity and MOSTLY AI's synthetic-data SDK are Apache-licensed.
- **Classify a health feature before you build it.** In the US, a low-risk general-wellness product is not regulated
  as a device under FDA policy, and that now includes noninvasive trackers of physiological values such as blood
  pressure that make no disease claim; the policy does not cover dietary supplements themselves. Clinical decision
  support stays outside device rules only when it meets all four non-device criteria: it does not process medical
  images or signals, it shows medical information, it supports a clinician's decision, and the clinician can
  independently review the basis; FDA now uses enforcement discretion when only one recommendation is clinically
  appropriate. An app where a consumer enters their own data is not a HIPAA business associate. But the FTC's Health
  Breach Notification Rule covers health apps outside HIPAA, with civil penalties per violation. In the EU, the
  medical-device regulation's software rule (Rule 11) makes software that informs diagnostic or therapeutic decisions
  class IIa or higher. Such software is then high-risk under the AI Act, whose obligations for AI in regulated
  products now apply from 2028-08-02. A feature that diagnoses, treats, or recommends a treatment is spec-chain work,
  with its regulatory classification in the decision row; it never goes through `/task`.
- **On-device runtimes are named by the packs that own them.** For reading a dependency list: TensorFlow Lite is now
  called LiteRT (Apache licence). ONNX Runtime is MIT-licensed; iterative_image_editor already runs it. Core ML models
  come through Apple's `coremltools` (BSD licence). PyTorch's ExecuTorch (BSD licence) is production-stable.
  `transformers.js` (Apache licence) runs ONNX models in the browser, on the GPU through WebGPU, and falls back to
  WebAssembly where WebGPU is missing.
- **Robotics and generative design have no fleet user; start from the open, current line.** ROS: use its current
  long-term-support distribution. Even-year releases are supported for five years. NVIDIA's Isaac Sim and Isaac Lab
  code is open, but a full workflow needs NVIDIA's proprietary Omniverse components. For text- or image-to-3D,
  Microsoft's TRELLIS has MIT-licensed code and weights. OpenAI's Shap-E has had no commit since 2023-11. Tencent's
  Hunyuan3D community licence does not apply in the EU, the UK or South Korea, so it cannot serve users there.

**Anti-pattern:** a classifier as the only thing between user content and an irreversible removal; a prompt-injection
detector treated as the security boundary; a neural recommender shipped without beating a co-occurrence baseline;
"synthetic, so it's anonymous"; a symptom checker or treatment suggestion built as an ordinary feature.

## The fleet today

No fleet repository has a directory matching this pack's globs, and none depends on a moderation, recommendation,
synthetic-data, robotics or generative-design library (43 repositories, 304 dependency files read on 2026-10-03). The
domains appear inside other work. tojlo-mail's LLM email triage frames each email body as untrusted data before the
model reads it, which is this pack's prompt-injection rule. iterative_image_editor runs ONNX Runtime on-device.
fabrik-citation-verifier queries PubMed for citations, which is a lookup, not a health feature. A future store
recommender in web-ecommerce-factory starts at the SQL baseline above.

## Subcategories

- **8. Robotics & control:** ROS, NVIDIA Isaac Sim and Isaac Lab, MuJoCo, Gazebo.
- **9. Synthetic data & simulation:** Faker for fixtures, synthcity and MOSTLY AI's SDK for tabular synthesis, SDV
  (Business Source License), NVIDIA's NeMo Data Designer (Apache-licensed, from the Gretel acquisition), NVIDIA
  Omniverse Replicator for images.
- **10. Recommendation & personalization:** SQL popularity and co-occurrence, `implicit`, Surprise (explicit ratings
  only), RecBole (research-oriented), Recommenders (now under LF AI & Data), Gorse (an Apache-licensed recommender
  server), Google's AI Commerce Search, Amazon Personalize, Recombee.
- **11. Cybersecurity & threat detection:** `saas/87-abuse-detection.md` owns it; the classifiers are statistical
  first, as in `ai/70-data-predictive.md`.
- **12. Bio-AI & healthcare:** the regulatory rule above; scientific models such as protein-structure predictors are
  research tools, not product features.
- **13. Edge & embedded:** LiteRT, ONNX Runtime, Core ML, ExecuTorch, `transformers.js`.
- **14. Governance, trust & safety:** the moderation and prompt-injection rules above; OpenAI's `omni-moderation`,
  Azure AI Content Safety, AWS Bedrock Guardrails, Granite Guardian, the Qwen guard models, Llama Guard, ShieldGemma.
- **15. Generative design & simulation:** TRELLIS for 3D assets; CAD-as-code (CadQuery, build123d) where dimensions
  must be exact; Autodesk's and nTop's generative design as hosted tools.

**Use cases:** comment and upload moderation, agent hardening, "you may also like", test fixtures, wellness tracking,
on-device inference, 3D product assets.
