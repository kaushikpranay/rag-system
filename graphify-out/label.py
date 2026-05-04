import sys, json
from graphify.build import build_from_json
from graphify.cluster import score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from pathlib import Path

extraction = json.loads(Path("graphify-out/.graphify_extract.json").read_text())
detection  = json.loads(Path("graphify-out/.graphify_detect.json").read_text(encoding="utf-8-sig"))
analysis   = json.loads(Path("graphify-out/.graphify_analysis.json").read_text())

G = build_from_json(extraction)
communities = {int(k): v for k, v in analysis["communities"].items()}
cohesion = {int(k): v for k, v in analysis["cohesion"].items()}
tokens = {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}

labels = {
    0: "Streamlit Dashboard & AWS Utilities",
    1: "LangGraph Agent Logic",
    2: "FastAPI Backend & Security",
    3: "Session Management & SQS Escalation",
    4: "Vector DB & pgvector Client",
    5: "Ingestion Pipeline",
    6: "Documentation & Setup",
    7: "Configuration Utils",
    8: "Chat UI Frontend",
    9: "Agent Package",
    10: "API Package",
    11: "Dashboard Package",
    12: "Escalation Package",
    13: "Ingestion Package",
    14: "Memory Package",
    15: "Retrieval Package",
    16: "Summarizer Logic",
    17: "Summarizer Package",
    18: "Utils Package",
    19: "Tests Package"
}

questions = suggest_questions(G, communities, labels)

report = generate(G, communities, cohesion, labels, analysis["gods"], analysis["surprises"], detection, tokens, ".", suggested_questions=questions)
Path("graphify-out/GRAPH_REPORT.md").write_text(report, encoding="utf-8")
Path("graphify-out/.graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}))
print("Report updated with community labels")
