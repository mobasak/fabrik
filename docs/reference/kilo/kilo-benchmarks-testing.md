# Agent Testing Log

Testing agents assigned in role mappings to determine if they should be blocked.

## Blocking Criteria

| Criterion | Threshold | Action |
|-----------|-----------|--------|
| Response time | >60s | Block (too slow) |
| Error rate | API errors | Block |
| Quality | Unusable output | Block |
| Cost efficiency | Extreme outlier | Review |

## How to Block/Unblock

```bash
# Block an agent
python manage_blocked.py block "agent/id" "reason"

# Unblock an agent
python manage_blocked.py unblock "agent/id"

# List blocked agents
python manage_blocked.py list
```

---

## Model Availability Test (2026-03-23 19:00)

Quick health check of all 5 reviewing models:

| Pri | Model | Status | Response |
|-----|-------|--------|----------|
| 1 | Claude Opus 4.6 | ✓ PASS | OK |
| 2 | Gemini 3.1 Pro Preview | ✓ PASS | OK |
| 3 | GPT-5.4 | ✓ PASS | OK |
| 4 | Grok 4 | ✓ PASS | OK |
| 5 | Qwen3 VL 235B Thinking | ✓ PASS | OK |

**All 5 reviewing models available and responding.**

---

## Comparison Test (2026-03-23 18:30)

Testing review quality with staged diff:

| Model | Duration | Issues Found | Quality |
|-------|----------|--------------|---------|
| **qwen3-vl-235b-a22b-thinking** | 2m3s | 6 (4 MAJOR, 2 MINOR) | ✓ Clean, focused on 3 staged files |
| glm-4.7 | 8m32s | 5+ MAJOR | ⚠️ Timeout + retry, scope creep (15 files) |

**Winner:** `qwen3-vl-235b-a22b-thinking` — 4x faster, better focus.

---

## Test Results (2026-03-23)

### Summary

| Model | Role | Time | Quality | Decision |
|-------|------|------|---------|----------|
| MiniMax M2.5 | coding #4 | 5.3s | ✓ Good | **ACCEPT** |
| DeepSeek V3.2 Exp | coding #5 | 8.9s | ✓ Good | **ACCEPT** |
| Grok 4 | reviewing #4 | 20.7s | ✓ Good review | **ACCEPT** |
| Qwen3 VL 235B Thinking | reviewing #5 | 16.3s | ✓ Good | **ACCEPT** |
| GPT-5.4 | coding #1 | 4.0s | ✓ Excellent | **ACCEPT** |
| GLM 4.7 | fixing #4 | 18.9s | ✓ Good | **ACCEPT** |
| Kimi K2 Thinking | fixing #5 | 16.2s | ✓ Good | **ACCEPT** |
| Qwen3 235B Instruct | documentation #1 | 11.6s | ✓ Good | **ACCEPT** |
| gpt-oss-20b | documentation #2 | 7.5s | ✓ Good | **ACCEPT** |
| MiMo-V2-Flash | documentation #3 | 45.0s | ✓ Good | **ACCEPT** (borderline) |
| Grok 4 Fast | documentation #5 | 11.3s | ✓ Good | **ACCEPT** |

**All models passed.** No new blocks required.

---

## Individual Test Results

### 1. MiniMax M2.5 (`minimax/minimax-m2.5`)
- **Role:** coding #4
- **Test:** Write email validator function
- **Time:** 5.3s
- **Quality:** Clean code, correct regex
- **Decision:** ✓ ACCEPT

### 2. DeepSeek V3.2 Exp (`deepseek/deepseek-v3.2-exp`)
- **Role:** coding #5
- **Test:** Write email validator function
- **Time:** 8.9s
- **Quality:** Good code with docstring
- **Decision:** ✓ ACCEPT

### 3. Grok 4 (`x-ai/grok-4`)
- **Role:** reviewing #4
- **Test:** Review SQL injection vulnerable code
- **Time:** 20.7s
- **Quality:** Correctly identified SQL injection (BLOCKER), plaintext passwords (MAJOR), no input validation (MINOR)
- **Decision:** ✓ ACCEPT

### 4. Qwen3 VL 235B Thinking (`qwen/qwen3-vl-235b-a22b-thinking`)
- **Role:** reviewing #5
- **Test:** Review division function
- **Time:** 16.3s
- **Quality:** Correctly identified ZeroDivisionError and type validation issues
- **Decision:** ✓ ACCEPT

### 5. GPT-5.4 (`openai/gpt-5.4`)
- **Role:** coding #1
- **Test:** Write email validator function
- **Time:** 4.0s
- **Quality:** Excellent, clean code using re.fullmatch
- **Decision:** ✓ ACCEPT

### 6. GLM 4.7 (`z-ai/glm-4.7`)
- **Role:** fixing #4
- **Test:** Fix syntax error in function
- **Time:** 18.9s
- **Quality:** Correct fix with explanation
- **Decision:** ✓ ACCEPT

### 7. Kimi K2 Thinking (`moonshotai/kimi-k2-thinking`)
- **Role:** fixing #5
- **Test:** Fix syntax error in function
- **Time:** 16.2s
- **Quality:** Correct fix, concise
- **Decision:** ✓ ACCEPT

### 8. Qwen3 235B Instruct (`qwen/qwen3-235b-a22b-2507`)
- **Role:** documentation #1
- **Test:** Write README section
- **Time:** 11.6s
- **Quality:** Well-formatted with features table, installation, usage examples
- **Decision:** ✓ ACCEPT

### 9. gpt-oss-20b (`openai/gpt-oss-20b`)
- **Role:** documentation #2
- **Test:** Write README section
- **Time:** 7.5s
- **Quality:** Comprehensive README with batch examples, development section
- **Decision:** ✓ ACCEPT

### 10. MiMo-V2-Flash (`xiaomi/mimo-v2-flash`)
- **Role:** documentation #3
- **Test:** Write README section
- **Time:** 45.0s
- **Quality:** Good output but slow
- **Decision:** ✓ ACCEPT (borderline - monitor for degradation)

### 11. Grok 4 Fast (`x-ai/grok-4-fast`)
- **Role:** documentation #5
- **Test:** Write README section
- **Time:** 11.3s
- **Quality:** Good README with features, installation, configuration
- **Decision:** ✓ ACCEPT

---

## Previous Benchmark Data (2026-03-19)

Source: `docs/reference/kilo/REVIEWER_BENCHMARK_RESULTS.md`

| Model | Time | Accuracy | Cost | Decision |
|-------|------|----------|------|----------|
| gemini-3.1-flash-lite | 16s | 95%+ | $0.02 | ✓ ACCEPT |
| glm-4.7 | 25s | 90%+ | $0.008 | ✓ ACCEPT |
| glm-5 | 21s | 100% | $0.05 | ✓ ACCEPT |
| claude-sonnet-4.6 | 20s | 100% | $0.04 | ✓ ACCEPT |
| claude-opus-4.6 | 45s | 100% | $0.50 | ✓ ACCEPT |
| **deepseek-v3.2** | **109s** | 100% | $0.05 | ❌ **BLOCKED** (too slow) |

---

## Blocked Agents History

| Date | Agent ID | Reason | Blocked By |
|------|----------|--------|------------|
| 2026-03-19 | `deepseek/deepseek-v3.2` | Too slow (109s per review) | Benchmark test |

