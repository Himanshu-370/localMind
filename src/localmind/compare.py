"""Record GraphRAG vs vector-only on fixed questions -> results.md (spec 16.8)."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .rag import Engine

# (question, expected evidence files; empty = unanswerable)
QUESTIONS = [
    ("What authentication-related issues could affect Project Atlas?", {"project.md", "architecture.md", "security.md", "incidents.md"}),
    ("What caused the Kafka connection failure?", {"incidents.md"}),
    ("Where is Atlas Kafka hosted?", {"architecture.md"}),
    ("What does AWS MSK require for authentication?", {"security.md"}),
    ("Which infrastructure does Project Atlas depend on?", {"project.md", "architecture.md"}),
    ("Who is the CEO of Project Atlas?", set()),
]


def main():
    eng = Engine(Config.load())
    rows = ["| Question | Mode | Recall | Cited files | Latency | Answer (first 160 chars) |", "|---|---|---|---|---|---|"]
    for q, expected in QUESTIONS:
        for mode in ("GraphRAG", "Vector only"):
            a = eng.ask(q, mode)
            got = {Path(c.path).name for c in a.citations}
            recall = f"{len(got & expected)}/{len(expected)}" if expected else ("abstained" if a.warnings else "ANSWERED")
            ans = " ".join(a.text.split())[:160].replace("|", "/")
            rows.append(f"| {q} | {mode} | {recall} | {', '.join(sorted(got)) or '-'} | {a.elapsed:.0f}s | {ans} |")
            print(rows[-1], flush=True)
    man = eng.manifest()
    head = (f"# Comparison results\n\nModel `{man['llm_model']}`, embeddings `{man['embed_model']}`, "
            f"{len(man['docs'])} docs, same budget both modes (top_k=10, chunk_top_k=5). "
            "Recall = expected source files among cited files. Tiny corpus, single run: indicative only, "
            "not evidence that either mode is better.\n\n")
    Path("results.md").write_text(head + "\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
