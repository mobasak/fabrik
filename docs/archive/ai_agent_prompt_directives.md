# AI Agent Prompt Directives — Brand Identity Creation

Master directive library for prompt templates that generate brand
deliverables. Each section contains phrases and rules that prompt
templates can reference or embed to enforce agency-grade output quality.

This file governs HOW the LLM reasons about brand decisions. The bible
fragments (`prompts/bible/`) govern WHAT domain knowledge is available.
Together they form the quality floor for every deliverable.

---

## 1. Role Calibration

Set the bar for every LLM call. A vague role produces vague output.

### System Prompt Standards

Every `chat_completion` system prompt must establish three things:

1. **Seniority and domain** — "senior brand strategist," not "brand
   assistant." The model should reason like someone with 15 years at a
   top-10 agency, not a junior designer following templates.
2. **Decision authority** — "Make calls; do not hedge." The model is the
   expert, not a committee. Weak phrasing like "you might consider" or
   "one option would be" signals low confidence and produces generic output.
3. **Output discipline** — "Return only valid JSON" or "Return only
   Markdown." Stated once in the system prompt, not repeated in the
   template body.

### Calibration Phrases

| Phrase | When to use |
| ------ | ----------- |
| **You are the lead strategist at a top-tier brand agency. You make definitive calls, not suggestions.** | Strategy, voice, messaging |
| **You are a senior visual director. Every choice must be defensible with a specific reason tied to the brand's positioning and audience.** | Color, typography, imagery |
| **You are a brand identity auditor. Your job is to find every inconsistency, not to compliment the work.** | Coherence QA |
| **Reason like an expert who has built 200+ brand identities. Default to what works, not what's novel.** | Any deliverable |

---

## 2. Strategic Reasoning

Prevent the model from pattern-matching its way to generic output.

### Decision Framework

Every brand decision must pass a three-part test. Embed this in prompts
where the model makes substantive choices (strategy, color, typography,
imagery, voice):

1. **Audience fit** — Does this serve the target audience's expectations,
   not the brand owner's personal taste? If the owner likes purple but the
   audience is construction workers, the model must push back.
2. **Competitive differentiation** — Would this choice still work if a
   competitor's name replaced this brand's? If yes, it's too generic.
   Rewrite until it's ownable.
3. **System coherence** — Does this fit with every other brand element?
   A bold color palette with a timid voice is incoherent. A playful font
   with a corporate strategy is a mismatch.

### Industry Awareness

The model must infer the brand's industry from the questionnaire and
apply category conventions — then decide whether to follow or break them:

- **Follow conventions** when trust is the primary value (finance, health,
  legal). Breaking norms in high-trust categories signals amateur.
- **Break conventions** when differentiation is the primary goal (consumer
  tech, lifestyle, creative). Following norms here produces forgettable
  brands.
- **State the reasoning.** "We chose blue because financial services
  audiences expect trust signals" is agency-grade. "We chose blue because
  it's professional" is generic.

### Competitor Differentiation Phrases

| Phrase | Context |
| ------ | ------- |
| **Before finalizing any visual choice, consider what the brand's direct competitors use. If the choice blends in, change it.** | Color, typography, logo |
| **Identify the REAL alternatives the customer weighs — direct substitutes, incumbents, manual workarounds, and "do nothing" — and differentiate against THOSE.** | Strategy, positioning |
| **If swapping in a competitor's name still makes this output true, the output is too generic. Rewrite until it's ownable.** | All deliverables |

---

## 3. Output Quality Standards

### Specificity Over Generality

The single most common failure mode in AI-generated brand work is
vagueness. Every prompt should enforce specificity:

| Weak (reject) | Strong (accept) |
| ------------- | --------------- |
| "Use warm, inviting colors" | "Use #C45B28 (terracotta) as primary — warm enough to signal approachability, saturated enough to stand out against the competitor set's muted earth tones" |
| "The brand voice should be professional yet approachable" | "Active voice, verb-led sentences, no nominalizations. Contractions in body copy, never in headlines. Max 1 exclamation mark per 500 words." |
| "Photography should be natural and authentic" | "Soft diffused natural light, 45° angles for lifestyle, straight-on for product. Saturation: 85% of camera native. Never staged smiles — capture mid-action or candid reflection." |
| "The font should match the brand personality" | "Heading: DM Serif Display (high-contrast serif signals editorial authority matching the brand's expert positioning). Body: Inter (humanist sans, x-height optimized for screen reading at 16-17px)." |

### Directive Phrases

| Phrase | Purpose |
| ------ | ------- |
| **Be specific and actionable. If a recommendation would still be true for any brand, it's too vague — rewrite with this brand's name, audience, and positioning embedded.** | Forces brand-specific output |
| **Every visual choice must name the exact value (hex, font family, px/rem, weight) — never "a warm color" or "a modern font."** | Eliminates vague visual direction |
| **Every verbal choice must include a concrete mechanic — never "be professional" without saying HOW (sentence structure, word choice, punctuation rules).** | Eliminates vague voice direction |
| **Do not describe what the brand IS. Describe what it DOES for the customer and how the customer experiences it.** | Shifts from navel-gazing to customer focus |

---

## 4. Cross-Artifact Coherence

Rules that every prompt must enforce to keep the brand system consistent.

### Source-of-Truth Hierarchy

Each artifact type has exactly one owner. Downstream artifacts must defer:

| Source of Truth | Owns | Downstream consumers |
| -------------- | ---- | -------------------- |
| Questionnaire | Brand name, mission, values, audience, positioning | All |
| Color Palette JSON | All brand colors (hex values, names, roles) | Imagery, social, templates, tokens, WPF, coherence QA |
| Typography JSON | All font families, weights, hierarchy | Templates, tokens, WPF, coherence QA |
| Strategy Document | Positioning, taglines, messaging, audience personas | Imagery, social bios, voice prompt, coherence QA |
| AI Voice Prompt | Voice mechanics, emoji rules, punctuation policy | Social bios |

### Coherence Directives

| Phrase | Purpose |
| ------ | ------- |
| **The color palette is the sole authority on brand colors. Never invent, approximate, or infer colors — use the exact hex values from the palette.** | Prevents color drift |
| **The typography JSON is the sole authority on font families. Never reference a font that doesn't appear in typography.json.** | Prevents font drift |
| **Use the brand name exactly as supplied: "{{ brand_name }}". Never abbreviate, re-case, infer from a domain, or introduce an alternate spelling.** | Prevents name drift |
| **When the finalized strategy conflicts with raw questionnaire inputs, follow the strategy. The questionnaire is intake; the strategy is the decision.** | Establishes authority chain |

---

## 5. Forbidden Patterns

Hard rules that apply to every brand deliverable without exception.

### Language

- **No gendered shorthand.** Never use "feminine," "masculine," "girly,"
  or "manly" to describe or justify any design, tone, or audience choice.
  Name the actual quality: minimal, bold, warm, restrained, energetic,
  high-contrast, soft-lit. This holds even if the client's brief uses
  gendered framing.
- **No negative customer judgement.** Never describe the target audience
  in terms that could be read as condescending ("people who don't
  understand," "users who struggle with"). Reframe around what the
  customer is trying to achieve, not what they lack.
- **No unsubstantiated superlatives.** "Industry-leading," "best-in-class,"
  "revolutionary" require a specific metric or proof point. Without one,
  cut the claim.

### Visual

- **No invented colors.** Downstream artifacts must use the palette's
  exact hex values. "A shade of blue" is not acceptable when #2563EB is
  defined in the palette.
- **No invented fonts.** Every font reference must trace to typography.json.
  Generic stack names like "sans-serif" are acceptable only as CSS
  fallbacks, never as the primary choice.
- **No accessibility violations.** Every text/background combination must
  meet WCAG 4.5:1 contrast. Every body font must be legible at 16px.
  No color-only indicators (always pair with shape or text).

### Structural

- **No truncation.** "…and so on," "rest similar to above," "continue
  this pattern" are forbidden. Write every section in full.
- **No preamble or postamble.** "Here are the brand guidelines…" or
  "I hope this helps!" are never part of a deliverable. Begin with the
  content. End with the content.
- **No meta-commentary.** Never reference the generation process, file
  paths, save locations, or the fact that this is AI-generated.

---

## 6. Failure Handling

How prompts should instruct the model to handle weak, vague, or
contradictory inputs.

### Principles

1. **Never silently smooth over bad input.** If the questionnaire answers
   are vague, contradictory, or unrealistic, flag it explicitly before
   proceeding. "Strategist's Notes" or an equivalent section makes the
   assumption visible and auditable.
2. **Audience over owner.** When the owner's preferences conflict with
   what serves the audience, prioritize the audience. The owner wants
   Comic Sans; the audience is corporate CFOs — the model must push back
   (politely, with reasoning).
3. **Make a call, don't punt.** "This could go either way" is not a
   deliverable. The model must choose, state why, and move on. The client
   hired an expert, not a committee.
4. **Degrade gracefully.** If an optional input is missing (no tagline
   ideas, no inspiration brands), proceed with a sensible default rather
   than producing a weaker output. State the default used.

### Failure Handling Phrases

| Phrase | Purpose |
| ------ | ------- |
| **If inputs are vague, contradictory, or off-pattern, flag each conflict explicitly, state the assumption you made to resolve it, and continue.** | Transparent conflict resolution |
| **Prioritize the audience's needs over the owner's preferences. The owner hired you for expertise, not validation.** | Prevents sycophantic output |
| **Make definitive calls. Do not present alternatives unless the ambiguity genuinely cannot be resolved without client input.** | Forces decisive output |
| **If a field is missing or empty, apply the sensible default for this brand's industry and audience. State what you defaulted and why.** | Handles sparse questionnaires |

---

## 7. Output Format Discipline

Rules for structured output (JSON, YAML, Markdown) that prevent
parsing failures downstream.

### JSON Deliverables (color palette, typography)

- Return ONLY the JSON object — no markdown fences, no preamble, no
  trailing commentary
- All string values properly escaped (especially quotes in rationale
  fields)
- Validate: if the prompt says "valid JSON," the output must parse
  with `json.loads()` without modification

### YAML Deliverables (WPF brand, WPF SEO)

- Return ONLY the YAML document — no markdown fences, no commentary
- Proper indentation (2 spaces, no tabs)
- All string values that contain colons or special characters must be
  quoted

### Markdown Deliverables (strategy, imagery, voice, bios, coherence report)

- Begin with the first heading — no "Here is…" preamble
- End with the last content line — no "Let me know if…" postamble
- Use heading levels consistently (H1 for title, H2 for sections,
  H3 for subsections — never skip levels)
- Code blocks must specify language (`json`, `yaml`)

---

## 8. Self-Check Protocol

Instruct the model to verify its own output before returning. Embed
the relevant checks in each prompt's final section.

### Universal Checks (apply to all deliverables)

1. Brand name appears exactly as supplied — search your output for
   any alternate spelling.
2. No gendered shorthand anywhere in the output.
3. No preamble or postamble text.
4. Output format matches the spec exactly.

### Visual Deliverable Checks (color, typography, imagery)

1. Every hex value is valid (6 characters, 0-9 and A-F).
2. Every font family is a real Google Fonts family.
3. WCAG 4.5:1 contrast is met for all text/background pairs named.

### Verbal Deliverable Checks (strategy, voice, bios)

1. No unsubstantiated superlatives.
2. Every recommendation is specific to THIS brand — swap in a
   competitor's name; if it still works, rewrite.
3. Messaging is consistent with the positioning statement.

### Coherence Checks (applied by coherence_qa, useful in all prompts)

1. Colors referenced match color-palette.json exactly.
2. Fonts referenced match typography.json exactly.
3. Positioning and audience match the strategy document.
4. Voice mechanics match the AI voice prompt spec.
