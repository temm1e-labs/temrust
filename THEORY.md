# THEORY — The Thesis As Stated

Captured verbatim from the originator (Quan Duong, 2026-05-05), then unpacked. **No editorial spin in this document.** The challenges live in `CHALLENGE.md`.

---

## The thesis (originator's words)

> Current LLM models are being trained wrong. They are trained on all available materials known to mankind on the internet like Common Crawl. Yes, they're impressive — a living wikipedia that seems to know it all. But this causes 2 major problems: **bloated param size AND lower model IQ**.
>
> I imagine when a model is trained specifically on **math, science, philosophy, engineering and top 1% smartest literature throughout history** it would on average be smarter (neuron-weighted for intelligence materials). Yes it doesn't know EVERYTHING like common LLMs but it will be super smart — a 4B model could potentially beat ×20 its size model in intelligence / reasoning capability, like an 80B model.

## Unpacking the claim

The thesis bundles five distinct sub-claims. Each must be evaluated separately because some are clearly true and some are clearly false:

### Claim 1 — "Frontier LLMs are trained on raw Common Crawl"
**Status:** outdated. Frontier labs already filter aggressively (FineWeb-Edu, RefinedWeb, Dolma, classifiers trained by Llama-3-70B). Nobody serious dumps raw CC. The interesting question is the *degree* of curation, not whether it happens.

### Claim 2 — "Broad training causes bloated param size"
**Status:** mechanistically wrong as stated. Parameters encode distributed statistical patterns, not 1:1 facts. Removing junk data does not "free" parameters; it changes which patterns are learned. The defensible version: **at fixed parameter count, training tokens spent on low-information data are training tokens that did not buy reasoning capability.** That is true, and it is the Phi insight.

### Claim 3 — "Broad training lowers model IQ"
**Status:** unproven in strong form, defensible in weak form. There is no good operational definition of "IQ" for LLMs. On reasoning benchmarks (MATH, GPQA, AIME), curated small models genuinely beat much larger generalists. On open-ended tasks (Arena, SWE-bench, factual recall), they do not.

### Claim 4 — "Train only on math/science/philosophy/engineering/top 1% literature"
**Status:** untested in the strict form, partially tested in soft form. Phi uses heavily curated web + synthetic textbooks but does not exclude general English, code, conversation. DeepSeek-Math is closer to the strict form but only for math. Whose canon counts as "top 1%" is itself a research question (see `CHALLENGE.md` §6).

### Claim 5 — "A 4B beats an 80B in reasoning capability"
**Status:** true on narrow benchmarks, false on broad utility. Examples that *do* validate the claim:
- **DeepSeek-R1-Distill-Qwen-1.5B** beats GPT-4o on AIME (28.9 vs ~9) and MATH-500 (83.9 vs ~74).
- **Qwen2.5-Math-7B** beats Llama-3.1-**405B** on MATH (55.4 vs 53.8) and GSM8K (91.6 vs 89.0).
- **Phi-4 (14B)** beats GPT-4o on GPQA Diamond (56.1 vs 50.6).
- **rStar-Math** lifts Phi-3-mini-3.8B to 86.4 MATH and AIME 53.3% — top 20% of high-school math olympiad performers.

Examples that *invalidate* the strong claim:
- Phi-4 SimpleQA score: **3**, vs Llama-3-70B at **~20**. World knowledge collapses.
- Phi-1.5 perplexity on the Pile: **2.1× worse** than OPT-1.3B, **3.5× worse** than Llama-2-7B. Language modelling itself is degraded.
- LMSys Arena rankings: Phi family consistently underperforms its benchmark scores.

---

## What the originator actually wants (best reading)

Stripping the loose phrasing, the productive form of the thesis is:

> **Hypothesis (TemLLM-strict):** A 4–14B model pretrained on a corpus where the *median* document is high-information-density (textbook, paper, derivation, top-shelf literature) — supplemented by synthetic curriculum-style data and distilled reasoning traces from a frontier teacher — will, **on verifiable-reasoning tasks**, match or exceed open generalist models 10–20× larger.

This is the form that has been validated. The next docs evaluate it.

## What the originator should *not* expect

- A 4B model that wins LMSys Arena.
- A 4B model that codes large agentic projects (SWE-bench).
- A 4B model with broad world knowledge (SimpleQA, TriviaQA).
- A 4B model that handles dialect, low-resource languages, niche domains.

This is the **utility tax** on narrow curation, and it is steep.
