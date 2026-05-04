import json
from pathlib import Path
import sys

def run_merge():
    try:
        if Path("graphify-out/.graphify_cached.json").exists():
            content = Path("graphify-out/.graphify_cached.json").read_text(encoding="utf-8-sig")
            cached = json.loads(content)
        else:
            cached = {"nodes":[], "edges":[], "hyperedges":[]}
        
        if Path("graphify-out/.graphify_semantic_new.json").exists():
            content = Path("graphify-out/.graphify_semantic_new.json").read_text(encoding="utf-8-sig")
            new = json.loads(content)
        else:
            new = {"nodes":[], "edges":[], "hyperedges":[]}
    except Exception as e:
        print(f"Error reading semantic files: {e}")
        sys.exit(1)

    all_nodes = cached["nodes"] + new.get("nodes", [])
    all_edges = cached["edges"] + new.get("edges", [])
    all_hyperedges = cached.get("hyperedges", []) + new.get("hyperedges", [])
    seen = set()
    deduped = []
    for n in all_nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            deduped.append(n)

    merged = {
        "nodes": deduped,
        "edges": all_edges,
        "hyperedges": all_hyperedges,
        "input_tokens": new.get("input_tokens", 0),
        "output_tokens": new.get("output_tokens", 0),
    }
    Path("graphify-out/.graphify_semantic.json").write_text(json.dumps(merged, indent=2))
    print(f"Extraction complete - {len(deduped)} nodes, {len(all_edges)} edges ({len(cached['nodes'])} from cache, {len(new.get('nodes',[]))} new)")

if __name__ == "__main__":
    run_merge()
