# AI TAXONOMY - Mainstream Categories (2025)

## Quick Reference (10-Line Summary)

**15 Categories → Subcategories → Tools**

1. **Speech/Audio**: Transcription (Soniox, Whisper), TTS (ElevenLabs), Voice Clone
2. **Vision**: Image Gen (Midjourney, DALL·E), Video Gen (Runway), OCR (Tesseract)
3. **Language**: LLMs (ChatGPT, Claude), Translation (DeepL), Embeddings (Cohere)
4. **Multimodal**: Vision+Language (GPT-4o, Gemini, Claude), Visual QA
5. **Agentic**: Multi-step reasoning (OpenAI o1, LangChain), Automation
6. **Code**: GitHub Copilot, Cursor IDE, Amazon CodeWhisperer
7. **Data/Predictive**: DataRobot, H2O.ai, AWS SageMaker, forecasting
8. **Robotics**: Boston Dynamics, NVIDIA Isaac, manipulation/control
9. **Synthetic Data**: NVIDIA Omniverse, Unity Perception, training data gen
10. **Recommendation**: Netflix/Spotify systems, Amazon Personalize
11. **Cybersecurity**: Darktrace, CrowdStrike, threat detection
12. **Bio/Healthcare**: AlphaFold, PathAI, drug discovery, diagnostics
13. **Edge/Embedded**: TensorFlow Lite, on-device inference
14. **Governance/Trust**: Content moderation, bias detection, LLaMA Guard
15. **Generative Design**: Autodesk, nTopology, optimization

**3 Selection Rules:**
- Match task to category first (prevents wrong tool type)
- Prefer specialized tools in category over general ones
- Document alternative considered + why not chosen

---

## 1. SPEECH & AUDIO AI

**Purpose:** Convert or interpret sound

**Subcategories:**
- **Transcription (Speech-to-Text):** Soniox, Whisper, Deepgram, AssemblyAI
- **Speech Synthesis (Text-to-Speech):** ElevenLabs, Play.ht, Amazon Polly
- **Voice Cloning:** Resemble AI, ElevenLabs VoiceLab
- **Audio Classification:** Google AudioSet, YAMNet
- **Music Generation:** Suno, Udio, Mubert, Meta MusicGen

**Use cases:** Transcription services, voice assistants, audio processing

---

## 2. VISION AI

**Purpose:** Interpret or generate images/video

**Subcategories:**
- **Image Generation:** Midjourney, DALL·E, Stable Diffusion
- **Video Generation:** Runway, Pika, Synthesia
- **Object/Scene Recognition:** YOLOv8, Detectron2, Google Vision API
- **OCR (Text from images):** Tesseract, AWS Textract
- **Face/Pose Estimation:** MediaPipe, OpenPose

**Use cases:** Content creation, surveillance, document processing

---

## 3. LANGUAGE AI

**Purpose:** Process and generate text

**Subcategories:**
- **Large Language Models:** ChatGPT, Claude, Gemini, Grok, Mistral
- **Embeddings & Search:** Cohere, OpenAI Embeddings, Pinecone
- **Translation:** DeepL, Google Translate, NLLB (Meta)
- **Summarization/Extraction:** GPT-4, Claude, Cohere Summarize

**Use cases:** Chatbots, content generation, search, translation

---

## 4. VISION-LANGUAGE & MULTIMODAL AI

**Purpose:** Combine text, image, audio, video understanding

**Examples:** GPT-4o, Gemini 1.5 Pro, Claude 3.5 Sonnet, LLaVA, Kosmos-2

**Use cases:** Image captioning, visual QA, document understanding, video analysis

---

## 5. AGENTIC / REASONING AI

**Purpose:** Multi-step reasoning or tool use

**Examples:** OpenAI o1, Claude Projects, AutoGPT, LangChain Agents

**Use cases:** Automation, code execution, planning, research

---

## 6. CODE & DEVELOPER AI

**Purpose:** Generate or explain code

**Examples:** GitHub Copilot, Amazon CodeWhisperer, Cursor IDE

**Use cases:** Code completion, refactoring, debugging assistance

---

## 7. DATA & PREDICTIVE AI

**Purpose:** Analyze structured data, forecast, detect anomalies

**Examples:** DataRobot, H2O.ai, Google Vertex AI, AWS SageMaker

**Use cases:** Business analytics, forecasting, anomaly detection

---

## 8. ROBOTICS & CONTROL AI

**Purpose:** Perceive, plan, act in physical world

**Examples:** Boston Dynamics Spot, NVIDIA Isaac, OpenAI Robotics

**Use cases:** Manipulation, drones, warehouse automation

---

## 9. SYNTHETIC DATA & SIMULATION AI

**Purpose:** Generate labeled/photorealistic data for training

**Examples:** NVIDIA Omniverse Replicator, Unity Perception, Synthesis AI

**Use cases:** Training data generation when real data limited

---

## 10. RECOMMENDATION & PERSONALIZATION AI

**Purpose:** Predict user preference or behavior

**Examples:** Netflix recommender, Spotify Discovery, Amazon Personalize

**Use cases:** Content ranking, adaptive feeds, product recommendations

---

## 11. CYBERSECURITY & THREAT DETECTION AI

**Purpose:** Detect anomalies or malicious behavior

**Examples:** Darktrace, CrowdStrike, Palo Alto Cortex

**Use cases:** Network security, fraud detection, intrusion response

---

## 12. BIO-AI / HEALTHCARE AI

**Purpose:** Model biological or medical data

**Examples:** DeepMind AlphaFold, Insilico Medicine, PathAI

**Use cases:** Protein folding, diagnostics, drug discovery

---

## 13. EDGE / EMBEDDED AI

**Purpose:** Run models on constrained hardware

**Examples:** TensorFlow Lite, Apple Neural Engine, Qualcomm AI Engine

**Use cases:** Real-time inference on devices without cloud

---

## 14. GOVERNANCE / TRUST / SAFETY AI

**Purpose:** Detect bias, hallucinations, unsafe content

**Examples:** LLaMA Guard, Perspective API, Azure Content Safety

**Use cases:** Content moderation, compliance, model interpretability

---

## 15. GENERATIVE DESIGN & SIMULATION

**Purpose:** Create optimized designs via algorithms

**Examples:** Autodesk Generative Design, nTopology, OpenAI Shap-E

**Use cases:** Architecture, manufacturing, product design

---

## TOOL SELECTION WORKFLOW

When starting AI project:
1. **Identify category** from 15 above
2. **Identify subcategory** (e.g., Speech → Transcription)
3. **Shortlist tools** from that subcategory
4. **Document in project.yaml:** ai_category, ai_subcategory, ai_tools
5. **Before-Writing-Code:** Justify chosen tool vs top alternative

**Common mistakes to avoid:**
- Using general LLM for specialized task (e.g., GPT for transcription instead of Soniox)
- Choosing tool before identifying category
- Not documenting alternative considered
