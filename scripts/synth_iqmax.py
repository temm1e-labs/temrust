#!/usr/bin/env python3
"""IQ-max synthesis: ~170 high-density CS/math/PLT topics → rigorous Q&A
pairs via Qwen3-Coder-Next-FP8 teacher. Tests the hypothesis that exposing
a 1.5B Coder to dense academic-reasoning content (out of distribution from
the eval) lifts general reasoning capacity that transfers to Rust borrow/
type/test tasks.

Output rows use the same chat-template SFT format as v5:
  {"messages": [
      {"role": "system", "content": <Tem-Rust system prompt>},
      {"role": "user", "content": "<deep technical question>"},
      {"role": "assistant", "content": "<rigorous step-by-step explanation>"}
  ]}

We use the SAME Tem-Rust system prompt for IQ examples so the model learns
"Tem-Rust answers Rust questions AND deep CS/math reasoning under the same
persona" — maximizing the chance reasoning capacity transfers to the eval.
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

from together import Together

TEACHER = "Qwen/Qwen3-Coder-Next-FP8"

SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. Return the complete fixed Rust "
    "file in a single ```rust code block. Do not include any other code blocks "
    "or explanations outside the block."
)

# A separate, instructional system prompt for the IQ slice. We can't reuse the
# Rust-fix-only system prompt — the model would learn to wrap explanations in
# ```rust blocks, which would break the eval. Keep this conceptually compatible
# (still "Tem-Rust") but task-appropriate.
SYSTEM_IQ = (
    "You are Tem-Rust, a careful, technically rigorous coding and reasoning "
    "assistant. When asked an in-depth conceptual question about computer "
    "science, programming language theory, mathematics, or systems, give a "
    "precise step-by-step explanation. Use definitions, derivations, and "
    "examples where useful. Be concise but do not hand-wave."
)


# 170 topics across 7 domains. Each is a *concept prompt* — we ask the teacher
# to write a rigorous expository answer.
TOPICS: list[tuple[str, str]] = [
    # ====================  Type theory (32)  ====================
    ("type-theory", "Define System F<: and explain how it differs from System F. Give an example of a term well-typed in F<: but not in F."),
    ("type-theory", "Explain Hindley-Milner type inference. What is principal type, and why does let-polymorphism preserve it but lambda-bound polymorphism does not?"),
    ("type-theory", "Define dependent types. Explain Π-types and Σ-types and how they generalize → and ×."),
    ("type-theory", "Explain occurs-check in unification. Why is it required for soundness, and what type-system feature breaks if you omit it?"),
    ("type-theory", "Define refinement types and contrast them with full dependent types. What expressiveness do you trade for decidable type-checking?"),
    ("type-theory", "Define linear types. Explain the structural rules (exchange, weakening, contraction) that linear logic forbids. How does this relate to Rust's affine types?"),
    ("type-theory", "Explain region inference for memory-safe languages without GC. Give the inference rule for a region-annotated function type."),
    ("type-theory", "Define higher-rank polymorphism (rank-N types). Why is type inference undecidable for rank-2 and above?"),
    ("type-theory", "Explain GADTs (generalized algebraic data types). Show a GADT-using term whose well-typedness depends on a refined index."),
    ("type-theory", "Define existential types and explain their use for module signatures and abstract data types. Show the pack/unpack rules."),
    ("type-theory", "Explain iso-recursive vs equi-recursive types. Why does Rust use iso-recursive (with explicit roll/unroll via Box)?"),
    ("type-theory", "Define subtyping S <: T as a relation. Explain the difference between subtyping and bounded polymorphism."),
    ("type-theory", "Explain variance: covariance, contravariance, and invariance. Give the rule for function-type variance and Rust's lifetime variance for &'a T."),
    ("type-theory", "Define F-bounded polymorphism. Why is it needed for binary methods like equals?"),
    ("type-theory", "Explain trait coherence in Rust. Why does the orphan rule exist, and what soundness property would break without it?"),
    ("type-theory", "Define normalization for a typed lambda calculus. State the strong normalization theorem for simply-typed lambda calculus."),
    ("type-theory", "Explain the Curry-Howard correspondence. Match: type → proposition, term → proof, normalization → proof simplification."),
    ("type-theory", "Define intersection types. Why are they undecidable in the general case but useful for principal-type analysis?"),
    ("type-theory", "Explain type classes (Haskell) vs traits (Rust). What is the dictionary-passing translation?"),
    ("type-theory", "Define the lifetime calculus underlying Rust's borrow checker. Show the inference rule for assigning a lifetime to a borrowed expression."),
    ("type-theory", "Explain the difference between lifetime parameters as type-level parameters and as term-level inferred entities. Show why Rust can elide some."),
    ("type-theory", "Define the W-type (well-founded trees). How does it generalize inductive datatypes in dependent type theory?"),
    ("type-theory", "Explain coinductive types. Give an example (e.g., Stream) and the bisimulation principle for proving equality of coinductive values."),
    ("type-theory", "Define occurrence checks needed for guarded coinductive definitions. Why do they ensure productivity?"),
    ("type-theory", "Explain the difference between subtyping (Liskov) and parametric polymorphism. Why doesn't 'every Cat is an Animal' imply 'List<Cat> is a List<Animal>' without variance annotations?"),
    ("type-theory", "Define and motivate effect types. Show the rule for typing a let-bound expression in an effect calculus."),
    ("type-theory", "Explain algebraic effects and effect handlers. Contrast with monad transformers."),
    ("type-theory", "Define normalization-by-evaluation (NbE). Why does it avoid reduction strategies and give canonical forms directly?"),
    ("type-theory", "Define dependent pattern matching. Why is it more powerful than projection (J-rule) alone, and what's the relation to inductive elimination principles?"),
    ("type-theory", "Explain the consistency of intuitionistic type theory. Why does adding excluded middle as an axiom not break it but limit the constructive content of proofs?"),
    ("type-theory", "Define Hoare logic. State the rules for sequencing, while loops, and assignment. How does separation logic extend it for heap-allocated state?"),
    ("type-theory", "Explain Rust's `for<'a>` higher-rank trait bounds. When are they needed and what's the underlying System F<: encoding?"),

    # ====================  Category theory (20)  ====================
    ("cat-theory", "Define a category. Give the four data and three laws. Show that the category Set with functions satisfies them."),
    ("cat-theory", "Define a functor F: C → D. State the two functor laws and verify them for the List functor."),
    ("cat-theory", "Define a natural transformation η: F ⇒ G between functors F, G: C → D. State the naturality square."),
    ("cat-theory", "State the Yoneda lemma. Explain what 'representable functor' means and why Yoneda formalizes 'an object is determined by its hom-functor'."),
    ("cat-theory", "Define a monad as a triple (T, η, μ). State the three monad laws and verify them for the Maybe (Option) monad."),
    ("cat-theory", "Define applicative functors. Show why every monad is applicative but not vice versa, with a concrete example (e.g., ZipList)."),
    ("cat-theory", "Define adjunction F ⊣ G. State the unit and counit triangle identities. Give an example (Free ⊣ Forgetful for monoids)."),
    ("cat-theory", "Define a limit in a category. Specialize to product, equalizer, pullback. State universal property."),
    ("cat-theory", "Define a colimit. Specialize to coproduct, coequalizer, pushout."),
    ("cat-theory", "Explain initial and terminal objects. Why does the function type A → B with B terminal collapse to a point in Set?"),
    ("cat-theory", "Define monomorphism and epimorphism category-theoretically. Show that in Set they coincide with injective and surjective functions."),
    ("cat-theory", "Define a slice category C/A. Why is it useful for talking about A-indexed objects in C?"),
    ("cat-theory", "Define a presheaf as a functor C^op → Set. Show the Yoneda embedding C → [C^op, Set]."),
    ("cat-theory", "Define a profunctor C ⇸ D as a functor C^op × D → Set. Give an example arising in programming (e.g., a relation between input and output types)."),
    ("cat-theory", "Define a Kleisli category for a monad T. Show that morphisms are functions A → T B."),
    ("cat-theory", "Define a Cartesian closed category (CCC). Why is the simply-typed lambda calculus the internal language of any CCC?"),
    ("cat-theory", "Explain Kan extensions (left and right). Give the universal property of LeftKan_K F."),
    ("cat-theory", "Define a 2-category and a strict vs weak monad on a 2-category. Why does this matter for higher-order languages?"),
    ("cat-theory", "Define an enriched category. Why does a Lawvere metric space arise as a category enriched over [0, ∞]?"),
    ("cat-theory", "Define a fibration between categories. Why are dependent types modeled by a fibration rather than an arrow in a 1-category?"),

    # ====================  PL semantics (25)  ====================
    ("pl-semantics", "Define small-step operational semantics for the call-by-value lambda calculus. Show the reduction rule for application."),
    ("pl-semantics", "Define big-step operational semantics for the same. Show evaluation rule for a let expression."),
    ("pl-semantics", "Define denotational semantics. Show the meaning function ⟦ · ⟧ for the simply-typed lambda calculus into a Cartesian-closed domain."),
    ("pl-semantics", "Define axiomatic semantics via Hoare logic. Give partial-correctness rules for if and while."),
    ("pl-semantics", "Explain the difference between call-by-value, call-by-name, and call-by-need (lazy). Give a term that distinguishes them."),
    ("pl-semantics", "Define the CEK abstract machine. Show how function application is implemented as continuation-passing."),
    ("pl-semantics", "Define continuation-passing style (CPS) transformation. Show ⟦ λx.e ⟧_cps."),
    ("pl-semantics", "Define A-normal form (ANF). Why is ANF easier to compile than direct-style, and what's the relation to SSA?"),
    ("pl-semantics", "Define static single assignment (SSA). Show how to convert a loop with mutable counter into SSA with phi-nodes."),
    ("pl-semantics", "Define dominator trees in a CFG. Why are they fundamental to many SSA-based optimizations?"),
    ("pl-semantics", "Explain abstract interpretation as a Galois connection between concrete and abstract semantics. Give an example (sign analysis)."),
    ("pl-semantics", "Define the polyhedral model for loop optimization. Why does it enable tiling and loop fusion to be expressed as integer-linear constraints?"),
    ("pl-semantics", "Explain region-based memory management as in MLKit. How are region annotations inferred?"),
    ("pl-semantics", "Define separation logic. Give the frame rule and explain why it enables local reasoning about heap-mutating programs."),
    ("pl-semantics", "Define Iris as a higher-order separation logic. Why does it scale to fine-grained concurrency where vanilla separation logic does not?"),
    ("pl-semantics", "Explain the difference between operational and axiomatic memory models. State a rule that holds in TSO but not sequential consistency."),
    ("pl-semantics", "Define release/acquire memory ordering. Show why it is sufficient for a producer/consumer pattern but insufficient for Dekker's algorithm."),
    ("pl-semantics", "Define data race vs memory race. Why does Rust's type system prevent data races but not all memory races?"),
    ("pl-semantics", "Explain async/await as a syntactic sugar for state-machine generators. Show how the compiler lowers an async block."),
    ("pl-semantics", "Define algebraic effects with handlers. Show the operational rule for resuming a continuation."),
    ("pl-semantics", "Define monad transformers and their stacking issue. Why do algebraic effects avoid the n^2 lifting boilerplate?"),
    ("pl-semantics", "Explain the difference between dynamic dispatch (vtables) and static dispatch (monomorphization) in Rust. Why does Rust default to monomorphization?"),
    ("pl-semantics", "Explain trait object safety. State the conditions and explain why methods returning Self are not object-safe."),
    ("pl-semantics", "Explain the Rust drop check (`#[may_dangle]`). What soundness property would fail if drop check were disabled?"),
    ("pl-semantics", "Define the Pin and Unpin types in Rust. What invariant do they encode and why is it needed for self-referential structs in async?"),

    # ====================  Algorithms / complexity (25)  ====================
    ("algo-complexity", "State the Master theorem. Apply it to T(n) = 2T(n/2) + n and to T(n) = 2T(n/2) + n log n."),
    ("algo-complexity", "Explain amortized analysis via the potential method. Apply it to dynamic-array doubling, deriving O(1) amortized push."),
    ("algo-complexity", "State the Akra-Bazzi theorem. Apply it to a recurrence with unequal sub-problem sizes."),
    ("algo-complexity", "Define NP-completeness. State the Cook-Levin theorem and outline the reduction from any NP language to SAT."),
    ("algo-complexity", "Define polynomial-time many-one reduction. Show that 3-SAT ≤_p Vertex-Cover."),
    ("algo-complexity", "Explain the P vs NP problem. Why does P = NP (if true) imply efficient algorithms for ALL NP-complete problems via reduction?"),
    ("algo-complexity", "Define randomized algorithms. Distinguish Las Vegas (always correct, randomized runtime) from Monte Carlo (bounded error, deterministic runtime)."),
    ("algo-complexity", "Define a PTAS and an FPTAS. Give an example problem with a PTAS but no known FPTAS unless P=NP."),
    ("algo-complexity", "Explain online algorithms and competitive analysis. Define the c-competitive ratio and apply to the marker algorithm for paging."),
    ("algo-complexity", "Define parameterized complexity (FPT). Show that Vertex-Cover is FPT in the size of the cover via a bounded search tree."),
    ("algo-complexity", "State the Exponential Time Hypothesis (ETH). What conditional lower bounds does ETH imply for 3-SAT?"),
    ("algo-complexity", "Explain fine-grained complexity. State the SETH-based lower bound for edit distance."),
    ("algo-complexity", "State the comparison-based sorting lower bound Ω(n log n). Sketch the decision-tree argument."),
    ("algo-complexity", "Explain integer sorting in o(n log n) (radix sort). What model assumptions are required for the bound to hold?"),
    ("algo-complexity", "Define union-find with union-by-rank and path compression. State the inverse-Ackermann amortized bound and outline the analysis."),
    ("algo-complexity", "Explain Fibonacci heaps. Why does decrease-key run in O(1) amortized despite worst-case O(log n)?"),
    ("algo-complexity", "Define link-cut trees and explain their use for dynamic-tree operations in O(log n) amortized."),
    ("algo-complexity", "Define persistent data structures. Show how a persistent linked list achieves O(1) cons and O(n) snapshots without copy."),
    ("algo-complexity", "Define cache-oblivious algorithms. Explain the tall-cache assumption and how cache-oblivious mergesort achieves O((n/B) log_{M/B} (n/M)) cache misses."),
    ("algo-complexity", "Explain approximate counting via HyperLogLog. Why does it use O(log log n) memory for n distinct elements?"),
    ("algo-complexity", "Define the multiplicative weights algorithm. Apply it to learning from expert advice with regret O(√(T log n))."),
    ("algo-complexity", "Define reservoir sampling. Show the algorithm for sampling 1 element uniformly from a stream of unknown length."),
    ("algo-complexity", "Define Bloom filters. State the false-positive rate as a function of number of hash functions, table size, and inserted elements."),
    ("algo-complexity", "Define the FFT (Cooley-Tukey). Why does it run in O(n log n) and not O(n log^2 n) like naive divide-and-conquer multiplication?"),
    ("algo-complexity", "Explain the Karatsuba multiplication algorithm. Derive its O(n^log_2 3) running time from the recurrence."),

    # ====================  Math reasoning (24)  ====================
    ("math-reasoning", "State and prove the pigeonhole principle. Apply it to show that any 5 points in a unit square have two within distance √2/2."),
    ("math-reasoning", "Explain the difference between weak induction, strong induction, structural induction, and well-founded induction."),
    ("math-reasoning", "Prove that the harmonic series ∑ 1/n diverges via comparison with a geometric grouping."),
    ("math-reasoning", "Prove the Cauchy-Schwarz inequality |⟨a,b⟩| ≤ |a||b|. Give the equality condition."),
    ("math-reasoning", "Prove the AM-GM inequality (a₁ + … + aₙ)/n ≥ (a₁ · … · aₙ)^(1/n) by Cauchy induction."),
    ("math-reasoning", "Define linearity of expectation. Use it to compute the expected number of fixed points of a random permutation of [n]."),
    ("math-reasoning", "State Markov's inequality and Chebyshev's inequality. Show how Chebyshev follows from Markov applied to (X-EX)²."),
    ("math-reasoning", "State the Chernoff bound for sums of independent Bernoulli random variables. Compare its sharpness to Chebyshev."),
    ("math-reasoning", "Define and apply the union bound. When is it tight, and when does the Lovász Local Lemma improve on it?"),
    ("math-reasoning", "State the central limit theorem. What conditions on the random variables are required?"),
    ("math-reasoning", "State the law of large numbers, both weak and strong forms. Where does each fail?"),
    ("math-reasoning", "Prove Borel-Cantelli (first lemma): if ∑ P(A_n) < ∞ then P(A_n i.o.) = 0."),
    ("math-reasoning", "Define a martingale. State the optional stopping theorem with its hypotheses."),
    ("math-reasoning", "Define the probabilistic method. Use it to prove that there exists a 2-coloring of a complete graph K_n with no monochromatic K_{2 log n} clique."),
    ("math-reasoning", "Define generating functions. Use the closed form of ∑ x^n / n! to derive the moment-generating function of a Poisson(λ) random variable."),
    ("math-reasoning", "Define recurrence relations and characteristic equations. Solve a_n = a_{n-1} + 6 a_{n-2}."),
    ("math-reasoning", "State and prove the binomial theorem. Use it to prove ∑ C(n,k) = 2^n."),
    ("math-reasoning", "Define a group, ring, and field. Show that ℤ/pℤ is a field iff p is prime."),
    ("math-reasoning", "Define a vector space and a basis. State the rank-nullity theorem for a linear map T: V → W."),
    ("math-reasoning", "State the spectral theorem for symmetric matrices. Why does it imply orthogonal diagonalizability?"),
    ("math-reasoning", "Define an inner product space. Prove the Cauchy-Schwarz inequality from the inner product axioms."),
    ("math-reasoning", "Define a metric space and a topology. Show that every metric space is also a topological space."),
    ("math-reasoning", "Define compactness in a topological space. State the Heine-Borel theorem characterizing compact subsets of ℝ^n."),
    ("math-reasoning", "Define continuity in topological terms (preimage of open is open). Prove that continuous functions preserve compactness."),

    # ====================  Rust-adjacent systems CS (28)  ====================
    ("rust-systems", "Explain LLVM IR. Why is it the natural target for Rust's mid-end optimization passes, and how does it represent SSA?"),
    ("rust-systems", "Define dominator trees. Why is computing them a prerequisite for many SSA optimizations like global value numbering?"),
    ("rust-systems", "Explain register allocation. Contrast linear-scan (used in some JITs) with graph-coloring approaches."),
    ("rust-systems", "Define escape analysis. How does it enable stack-allocating values that would otherwise be heap-allocated?"),
    ("rust-systems", "Explain reference counting (Rc<T> in Rust). Why doesn't naive reference counting reclaim cyclic data?"),
    ("rust-systems", "Define weak references (Weak<T>). How do they break reference cycles, and what's the runtime cost?"),
    ("rust-systems", "Explain mark-sweep garbage collection. Why is it not used in Rust by default?"),
    ("rust-systems", "Explain copying (semi-space) garbage collection. Why does it improve cache locality despite using more memory?"),
    ("rust-systems", "Explain generational garbage collection. State the weak generational hypothesis."),
    ("rust-systems", "Define lock-free data structures. Explain the ABA problem and how hazard pointers solve it."),
    ("rust-systems", "Define RCU (read-copy-update). Why is it more efficient than reader-writer locks for read-heavy workloads?"),
    ("rust-systems", "Define memory models: sequential consistency, total store order (TSO), release/acquire. Show a program that distinguishes TSO from SC."),
    ("rust-systems", "Define data races vs memory races. Why does Rust's type system prevent the former but not all of the latter?"),
    ("rust-systems", "Explain false sharing. How does cache-line alignment of struct fields prevent it?"),
    ("rust-systems", "Define MESI cache coherence. Walk through a state transition for a write to a shared line."),
    ("rust-systems", "Define NUMA. Why does first-touch placement matter for memory-bound parallel programs?"),
    ("rust-systems", "Explain TLB shootdowns. Why are they expensive on multi-socket systems?"),
    ("rust-systems", "Define work-stealing schedulers. State the classic 'work O(T₁) + span O(T_∞)' bound for fully strict computations."),
    ("rust-systems", "Explain the difference between coroutines and threads. Why are async/await stackless coroutines in Rust?"),
    ("rust-systems", "Define lock contention. How does adaptive backoff reduce it?"),
    ("rust-systems", "Define and explain epoch-based memory reclamation. How does it solve the use-after-free problem in lock-free structures?"),
    ("rust-systems", "Explain branch prediction. Why are unpredictable branches expensive on modern superscalar CPUs, and how does branchless coding (cmov) help?"),
    ("rust-systems", "Define out-of-order execution. Why does it require a reorder buffer to maintain in-order retirement?"),
    ("rust-systems", "Explain SIMD vectorization. Why does Rust expose `std::simd` rather than auto-vectorizing aggressively?"),
    ("rust-systems", "Define cache lines and false sharing. Why is `#[repr(align(64))]` a common Rust idiom for hot atomic fields?"),
    ("rust-systems", "Explain the Rust borrow checker as an alias-analysis pass. What invariants does it establish that LLVM relies on for optimization?"),
    ("rust-systems", "Define the Rust trait object layout. Why is the vtable kept separate from the data pointer in `&dyn Trait`?"),
    ("rust-systems", "Explain Rust's `unsafe` block as a delineator of the safe/unsafe boundary. What does soundness mean for an unsafe abstraction?"),

    # ====================  Foundations of CS (16)  ====================
    ("foundations", "State Gödel's first incompleteness theorem. Sketch the construction of a self-referential sentence."),
    ("foundations", "State Gödel's second incompleteness theorem. Why does it imply Peano arithmetic cannot prove its own consistency?"),
    ("foundations", "State the Church-Turing thesis. Distinguish it from a mathematical theorem."),
    ("foundations", "Prove the halting problem is undecidable via diagonalization."),
    ("foundations", "State Rice's theorem. Apply it to prove that 'does this program halt on all inputs' is undecidable."),
    ("foundations", "Define the recursion theorem (Kleene). Sketch its application to fixed-point combinators in lambda calculus."),
    ("foundations", "State the Curry-Howard correspondence. Match: implication = function type, conjunction = pair, disjunction = sum."),
    ("foundations", "Define intuitionistic logic. Why does it reject the law of excluded middle, and how does it relate to constructive proofs?"),
    ("foundations", "Define sequent calculus. State the cut rule and explain why cut elimination implies consistency."),
    ("foundations", "Define natural deduction. Show the introduction and elimination rules for implication."),
    ("foundations", "Prove Church-Rosser (confluence) for the untyped lambda calculus. Sketch the parallel reduction technique."),
    ("foundations", "State the strong normalization theorem for simply-typed lambda calculus. Outline Tait's reducibility argument."),
    ("foundations", "Define Knuth-Bendix completion for term rewriting systems. Why does it sometimes fail to terminate?"),
    ("foundations", "Define the lambda cube (Barendregt). Place System F, λΠ, λω, and the Calculus of Constructions on its vertices."),
    ("foundations", "Define realizability semantics for intuitionistic logic. Explain how it gives constructive content to proofs."),
    ("foundations", "Explain the BHK (Brouwer-Heyting-Kolmogorov) interpretation of intuitionistic connectives."),
]


def teacher_chat(client: Together, system: str, user: str, max_tokens: int = 2048) -> str:
    last_err = ""
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=TEACHER,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            return r.choices[0].message.content or ""
        except Exception as e:
            last_err = str(e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"teacher failed after retries: {last_err}")


def process_one(client_args: tuple, item: tuple[int, tuple[str, str]]) -> tuple[int, str, str, str | None]:
    """Worker: returns (idx, domain, prompt, response_or_None)."""
    api_key, = client_args
    client = Together(api_key=api_key)
    idx, (domain, prompt) = item
    try:
        response = teacher_chat(client, SYSTEM_IQ, prompt)
        if len(response.strip()) < 200:
            return idx, domain, prompt, None
        return idx, domain, prompt, response
    except Exception:
        return idx, domain, prompt, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/clean/sft_iqmax.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=6, help="parallel teacher requests")
    args = ap.parse_args()

    random.seed(args.seed)
    topics = list(TOPICS)
    random.shuffle(topics)
    if args.limit:
        topics = topics[: args.limit]

    api_key = os.environ["TOGETHER_API_KEY"]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sink = open(args.out, "w")
    n_kept = 0
    n_err = 0
    by_domain: dict[str, int] = {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    items = list(enumerate(topics))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(process_one, (api_key,), it) for it in items]
        n_done = 0
        for fut in as_completed(futures):
            idx, domain, prompt, response = fut.result()
            n_done += 1
            if response is None:
                n_err += 1
            else:
                sink.write(json.dumps({
                    "messages": [
                        {"role": "system", "content": SYSTEM_IQ},
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response},
                    ]
                }) + "\n")
                sink.flush()
                n_kept += 1
                by_domain[domain] = by_domain.get(domain, 0) + 1
            if n_done % 10 == 0:
                el = time.time() - t0
                print(f"  [{n_done}/{len(items)}] kept={n_kept} err={n_err} ({el:.0f}s; {el/(n_kept or 1):.1f}s/row)  per-domain={by_domain}", flush=True)

    sink.close()
    el = time.time() - t0
    print(f"\nFINAL: kept={n_kept}/{len(items)} err={n_err} ({el:.0f}s)", flush=True)
    print(f"  per-domain: {by_domain}", flush=True)
    print(f"  wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
