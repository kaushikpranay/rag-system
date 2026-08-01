import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ["RDS_HOST"] = "127.0.0.1"
os.environ["RDS_PORT"] = "5432"

from app.retrieval.pgvector_client import retrieve_similar, get_connection

query = "How do you calculate and print the response time for a vector database query in seconds?"
expected = 'time() - start_time\nprint(f"Querying response time: {response_time:.2f} seconds")  \nThe output contai'

# Search with top_k=30 to see where the correct chunk actually lands
results = retrieve_similar(query, top_k=30, min_similarity=0.0)

print(f"Total results returned: {len(results)}")
for i, r in enumerate(results, 1):
    content = r["content"]
    sim = float(r["similarity"])
    is_match = expected in content
    tag = " <<<< EXPECTED CHUNK" if is_match else ""
    preview = content[:90].replace("\n", " ")
    print(f"  [{i:2d}] sim={sim:.4f} | {preview}...{tag}")

# Also check if the expected substring exists in DB at all
conn = get_connection()
cur = conn.cursor()
search_term = expected[:40]
cur.execute("SELECT id, content FROM documents WHERE content ILIKE %s", (f"%{search_term}%",))
rows = cur.fetchall()
print(f"\nDirect DB search for expected substring (first 40 chars): found {len(rows)} rows")
for row_id, content in rows:
    preview = content[:100].replace("\n", " ")
    print(f"  row id={row_id}: {preview}...")
cur.close()
conn.close()
