"""
Phase 7 — Streamlit Human Agent Dashboard
RAG Query Resolution System
File: app/dashboard/streamlit_app.py
"""
import hashlib
import streamlit as st
import boto3
import json
import psycopg2
import os
import time
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()
def check_password():
    ssm = boto3.client("ssm", region_name="us-east-1")
    stored_hash = ssm.get_parameter(
        Name="DASHBOARD_PASSWORD_HASH", 
        WithDecryption=True
    )["Parameter"]["Value"]

    def password_entered():
        entered = hashlib.sha256(
            st.session_state["password"].encode()
        ).hexdigest()
        if entered == stored_hash:
            st.session_state["authenticated"] = True
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False

    if "authenticated" not in st.session_state:
        st.text_input("Dashboard Password", 
            type="password", 
            on_change=password_entered, 
            key="password")
        return False

    if not st.session_state["authenticated"]:
        st.text_input("Dashboard Password", 
            type="password", 
            on_change=password_entered, 
            key="password")
        st.error("Incorrect password")
        return False

    return True

if not check_password():
    st.stop()

# YOUR EXISTING DASHBOARD CODE BELOW THIS LINE
# ─── Config ─────────────────────────────────────────────────────────────────
AWS_REGION        = os.getenv("AWS_REGION", "us-east-1")
SQS_QUEUE_URL     = os.getenv("SQS_QUEUE_URL")
S3_BUCKET         = os.getenv("S3_BUCKET_NAME")
DYNAMODB_TABLE    = os.getenv("DYNAMODB_TABLE", "rag-session-memory")

RDS_HOST          = os.getenv("RDS_HOST")
RDS_PORT          = int(os.getenv("RDS_PORT", 5432))
RDS_DB            = os.getenv("RDS_DB", "ragdb")
RDS_USER          = os.getenv("RDS_USER")
RDS_PASSWORD      = os.getenv("RDS_PASSWORD")

# ─── AWS Clients ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_aws_clients():
    session = boto3.Session(region_name=AWS_REGION)
    return {
        "sqs":      session.client("sqs"),
        "s3":       session.client("s3"),
        "dynamodb": session.resource("dynamodb"),
        "bedrock":  session.client("bedrock-runtime"),
    }

# ─── SQS Helpers ─────────────────────────────────────────────────────────────
def receive_from_sqs(max_messages: int = 10) -> list:
    clients = get_aws_clients()
    all_messages = []
    attempts = 3  # poll multiple times
    try:
        for _ in range(attempts):
            resp = clients["sqs"].receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=2,
                AttributeNames=["All"],
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                break
            all_messages.extend(msgs)
            if len(all_messages) >= max_messages:
                break
        return all_messages
    except Exception as e:
        st.error(f"SQS receive error: {e}")
        return []


def delete_from_sqs(receipt_handle: str) -> bool:
    """Delete a resolved message from SQS."""
    clients = get_aws_clients()
    try:
        clients["sqs"].delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle,
        )
        return True
    except Exception as e:
        st.error(f"SQS delete error: {e}")
        return False


def get_queue_depth() -> int:
    """Return approximate number of messages in queue."""
    clients = get_aws_clients()
    try:
        resp = clients["sqs"].get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))
    except Exception:
        return -1

# ─── RDS Helpers ─────────────────────────────────────────────────────────────
def get_rds_connection():
    """Get psycopg2 connection with pgvector registered."""
    conn = psycopg2.connect(
        host=RDS_HOST, port=RDS_PORT,
        dbname=RDS_DB, user=RDS_USER, password=RDS_PASSWORD
    )
    register_vector(conn)  # CRITICAL — do not remove
    return conn


def get_bedrock_embedding(text: str) -> list:
    """Generate 1024-dim embedding via Bedrock Titan V2."""
    clients = get_aws_clients()
    try:
        body = json.dumps({"inputText": text})
        resp = clients["bedrock"].invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(resp["body"].read())
        return result["embedding"]
    except Exception as e:
        st.error(f"Bedrock embedding error: {e}")
        return None


def store_verified_answer_rds(query: str, answer: str) -> bool:
    """Store verified Q&A as new embedding in RDS pgvector."""
    text_to_embed = f"Q: {query}\nA: {answer}"
    embedding = get_bedrock_embedding(text_to_embed)
    if embedding is None:
        return False
    conn = None
    try:
        conn = get_rds_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (content, metadata, embedding)
            VALUES (%s, %s, %s)
            """,
            (
                text_to_embed,
                json.dumps({
                    "source": "human_verified",
                    "query": query,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }),
                embedding,
            ),
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        st.error(f"RDS insert error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def store_verified_answer_s3(session_id: str, query: str, answer: str) -> bool:
    """Archive verified answer to S3 verified-answers/ folder."""
    clients = get_aws_clients()
    key = f"verified-answers/{session_id}_{int(time.time())}.json"
    payload = {
        "session_id": session_id,
        "query": query,
        "verified_answer": answer,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        clients["s3"].put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(payload),
            ContentType="application/json",
        )
        return True
    except Exception as e:
        st.error(f"S3 store error: {e}")
        return False

# ─── DynamoDB — update session with verified answer ──────────────────────────
def update_session_with_verified(session_id: str, query: str, answer: str):
    """Append verified answer back into DynamoDB session history."""
    clients = get_aws_clients()
    table = clients["dynamodb"].Table(DYNAMODB_TABLE)
    try:
        resp = table.get_item(Key={"session_id": session_id})
        history = resp.get("Item", {}).get("history", [])
        history.append({
            "query": query,
            "answer": f"[VERIFIED BY AGENT] {answer}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET history = :h",
            ExpressionAttributeValues={":h": history},
        )
    except Exception as e:
        st.warning(f"DynamoDB update skipped: {e}")

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Agent Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; color: #e0e0e0; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #161b27;
        border-right: 1px solid #2a2f3e;
    }

    /* Cards */
    .query-card {
        background: #1a1f2e;
        border: 1px solid #2a2f3e;
        border-left: 4px solid #f5a623;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .query-card.resolved {
        border-left-color: #27c93f;
        opacity: 0.6;
    }

    /* Labels */
    .label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #888;
        margin-bottom: 4px;
    }
    .value { font-size: 14px; color: #e0e0e0; margin-bottom: 12px; }

    /* Badge */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background: #f5a623;
        color: #0f1117;
    }
    .badge.resolved { background: #27c93f; }

    /* Metric boxes */
    .metric-box {
        background: #1a1f2e;
        border: 1px solid #2a2f3e;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-box .num { font-size: 32px; font-weight: 700; color: #f5a623; }
    .metric-box .lbl { font-size: 12px; color: #888; margin-top: 4px; }

    /* Buttons */
    .stButton > button {
        background: #f5a623;
        color: #0f1117;
        border: none;
        font-weight: 600;
        border-radius: 6px;
    }
    .stButton > button:hover { background: #e09415; }

    /* Text areas */
    .stTextArea > div > textarea {
        background: #0f1117;
        border: 1px solid #2a2f3e;
        color: #e0e0e0;
        border-radius: 6px;
    }

    /* Divider */
    hr { border-color: #2a2f3e; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 RAG System")
    st.markdown("**Human Agent Dashboard**")
    st.markdown("---")

    queue_depth = get_queue_depth()
    depth_color = "#f5a623" if queue_depth > 0 else "#27c93f"
    depth_label = "Pending" if queue_depth != 1 else "Pending"

    st.markdown(f"""
    <div class="metric-box">
        <div class="num" style="color:{depth_color};">{queue_depth if queue_depth >= 0 else "?"}</div>
        <div class="lbl">{depth_label} in Queue</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
    max_fetch = st.slider("Max messages to fetch", 1, 10, 5)
    st.markdown("---")
    st.markdown("**Workflow**")
    st.markdown("1. Fetch escalated queries\n2. Review LLM answer\n3. Write correct answer\n4. Submit → stores to RDS + S3")
    st.markdown("---")
    st.markdown("<div style='font-size:11px;color:#555;'>Phase 7 — RAG System v1.0</div>", unsafe_allow_html=True)
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
        

# ─── Main Header ─────────────────────────────────────────────────────────────
st.markdown("# Escalation Queue")
st.markdown("Review low-confidence queries escalated by the RAG agent. Submit verified answers to improve the knowledge base.")
st.markdown("---")

# ─── Session State ───────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "resolved_ids" not in st.session_state:
    st.session_state.resolved_ids = set()
if "answers" not in st.session_state:
    st.session_state.answers = {}

# ─── Fetch Button ────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 4])
with col1:
    if st.button("🔄 Fetch Escalated Queries"):
        with st.spinner("Polling SQS..."):
            msgs = receive_from_sqs(max_messages=max_fetch)
            if msgs:
                # Deduplicate by MessageId
                existing_ids = {m.get("MessageId") for m in st.session_state.messages}
                new_msgs = [m for m in msgs if m.get("MessageId") not in existing_ids]
                st.session_state.messages.extend(new_msgs)
                if new_msgs:
                    st.success(f"Fetched {len(new_msgs)} new message(s).")
                else:
                    st.info("No new messages.")
            else:
                st.info("Queue is empty or no messages available.")

with col2:
    if st.button("🗑 Clear Resolved"):
        st.session_state.messages = [
            m for m in st.session_state.messages
            if m.get("MessageId") not in st.session_state.resolved_ids
        ]
        st.session_state.resolved_ids = set()
        st.rerun()

# ─── Auto-refresh ────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.rerun()

st.markdown("---")

# ─── Message List ────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding: 60px 0; color: #555;">
        <div style="font-size: 40px;">📭</div>
        <div style="margin-top: 12px; font-size: 16px;">No escalated queries loaded.</div>
        <div style="font-size: 13px; margin-top: 6px;">Click "Fetch Escalated Queries" to poll SQS.</div>
    </div>
    """, unsafe_allow_html=True)
else:
    total = len(st.session_state.messages)
    resolved_count = len(st.session_state.resolved_ids)
    st.markdown(f"**{total} message(s) loaded** — {resolved_count} resolved, {total - resolved_count} pending")
    st.markdown("")

    for idx, msg in enumerate(st.session_state.messages):
        msg_id = msg.get("MessageId", str(idx))
        receipt = msg.get("ReceiptHandle", "")
        is_resolved = msg_id in st.session_state.resolved_ids

        # Parse body
        try:
            body = json.loads(msg.get("Body", "{}"))
        except Exception:
            body = {}

        session_id = body.get("session_id", "unknown")
        query      = body.get("query", "—")
        llm_answer = body.get("answer", "—")

        # Card
        card_class = "query-card resolved" if is_resolved else "query-card"
        badge_class = "badge resolved" if is_resolved else "badge"
        badge_text  = "RESOLVED" if is_resolved else "PENDING"

        st.markdown(f"""
        <div class="{card_class}">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="font-weight:700; font-size:15px;">Query #{idx + 1}</div>
                <span class="{badge_class}">{badge_text}</span>
            </div>
            <div class="label">Session ID</div>
            <div class="value" style="font-family:monospace; font-size:12px;">{session_id}</div>
            <div class="label">User Query</div>
            <div class="value">❓ {query}</div>
            <div class="label">LLM Answer (Low Confidence)</div>
            <div class="value" style="color:#aaa;">🤖 {llm_answer}</div>
        </div>
        """, unsafe_allow_html=True)

        if not is_resolved:
            # Answer input
            answer_key = f"answer_{msg_id}"
            verified_answer = st.text_area(
                f"Your verified answer for Query #{idx + 1}",
                key=answer_key,
                placeholder="Type the correct answer here...",
                height=100,
            )

            btn_col1, btn_col2 = st.columns([1, 5])
            with btn_col1:
                submit_key = f"submit_{msg_id}"
                if st.button("✅ Submit", key=submit_key):
                    if not verified_answer.strip():
                        st.warning("Answer cannot be empty.")
                    else:
                        with st.spinner("Storing verified answer..."):
                            # 1. Store in RDS pgvector
                            rds_ok = store_verified_answer_rds(query, verified_answer.strip())

                            # 2. Store in S3
                            s3_ok = store_verified_answer_s3(session_id, query, verified_answer.strip())

                            # 3. Update DynamoDB session
                            update_session_with_verified(session_id, query, verified_answer.strip())

                            # 4. Delete from SQS
                            sqs_ok = delete_from_sqs(receipt)

                        if rds_ok and s3_ok and sqs_ok:
                            st.success(f"✅ Query #{idx + 1} resolved and stored.")
                            st.session_state.resolved_ids.add(msg_id)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("One or more storage steps failed. Check logs.")
        else:
            st.markdown(
                "<div style='color:#27c93f; font-size:13px; margin-top:-8px; margin-bottom:16px;'>✔ Resolved — answer stored in RDS + S3</div>",
                unsafe_allow_html=True
            )

        st.markdown("---")

# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center; color:#333; font-size:12px; margin-top:40px;'>RAG Query Resolution System — Phase 7</div>",
    unsafe_allow_html=True,
)