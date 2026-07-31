import os
import uuid
import time
import logging
from groq import Groq
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from app.retrieval.pgvector_client import retrieve_similar
from app.memory.dynamodb_client import get_session, save_session
from app.escalation.sqs_worker import send_to_sqs
from app.utils.sanitizer import mask_pii


load_dotenv()

logger = logging.getLogger(__name__)

#
# -------------State Schema------------------------

class AgentState(TypedDict):
    query: str
    session_id: str
    chat_history: List[dict]
    retrieved_chunks: List[dict]
    context: str
    answer: str
    confidence: str     # high, low, or retry
    escalate: bool
    retry_count: int
    error: Optional[str]
    truncated: bool

#------Node 1: Input ----------------------------

def input_node(state: AgentState)-> AgentState:
    query = state["query"].strip()
    if not query:
        return {**state, "error": "Empty query received"}
    logger.info(f"[input_node] Query: {mask_pii(query[:80])}")
    return {**state, "query": query, "error": None}

#------ Node 2: Session (Dummy for now) --------


def session_node(state: AgentState) -> AgentState:
    session_id = state.get("session_id", "default-session")
    history = get_session(session_id)
    logger.info(f"[session_node] Session: {session_id}, History length: {len(history)}")
    return {**state, "chat_history": history}


#--------------- Node 3: Retrieval -------------------------------

def retrieval_node(state: AgentState) -> AgentState:
    query = state["query"]
    retry_count = state.get("retry_count", 0)
    logger.info(f"[retrieval_node] Retrieving chunks (attempt {retry_count + 1}/3)")

    # Widen search parameters on each retry
    human_threshold = max(0.40, 0.55 - (retry_count * 0.05))  # 0.55 → 0.50 → 0.45
    top_k = 5 + (retry_count * 3)                              # 5 → 8 → 11
    min_sim = max(0.10, 0.30 - (retry_count * 0.10))           # 0.30 → 0.20 → 0.10

    try:
        # Step 1: Human-verified answers first (semantic match)
        from app.retrieval.pgvector_client import search_human_verified
        human_results = search_human_verified(query, top_k=3)
        if human_results and human_results[0][2] > human_threshold:
            logger.info(f"[retrieval_node] Human-verified answer found. Similarity: {human_results[0][2]:.2f} (threshold: {human_threshold})")
            return {
                **state,
                "retrieved_chunks": [{"content": human_results[0][0], "metadata": human_results[0][1], "similarity": human_results[0][2]}],
                "context": human_results[0][0]
            }

        # Step 2: Fallback to general search with progressive widening
        chunks = retrieve_similar(query, top_k=top_k, min_similarity=min_sim)
        logger.info(f"[retrieval_node] {len(chunks)} chunks retrieved (top_k={top_k}, min_sim={min_sim})")
        return {**state, "retrieved_chunks": chunks}
    except Exception as e:
        logger.error(f"[retrieval_node] Retrieval failed: {e}")
        return {**state, "retrieved_chunks": []}


#------Node 4: Context -----------------
def context_node(state: AgentState) -> AgentState:
    chunks = list(state.get("retrieved_chunks", []))
    # Check if context was already set by the human-verified retrieval path
    if state.get("context") and state["context"].strip():
        logger.info(f"[context_node] Using pre-set human-verified context")
        context = state["context"]
    elif not chunks:
        context = "No relevant context found"
    else:
        context = "\n\n".join([
            f"[Chunk {i+1} | Similarity: {c.get('similarity', 0.0):.2f}]\n{c['content']}"
            for i, c in enumerate(chunks)
        ])

    est_tokens = len(context) // 4
    if est_tokens > 6000 and chunks:
        sorted_chunks = sorted(chunks, key=lambda c: c.get("similarity", 0.0), reverse=True)
        dropped_count = 0
        while len(context) // 4 > 6000 and sorted_chunks:
            sorted_chunks.pop()  # Drop lowest-similarity chunk
            dropped_count += 1
            if not sorted_chunks:
                context = "No relevant context found"
            else:
                context = "\n\n".join([
                    f"[Chunk {i+1} | Similarity: {c.get('similarity', 0.0):.2f}]\n{c['content']}"
                    for i, c in enumerate(sorted_chunks)
                ])

        chunks = sorted_chunks
        final_est_tokens = len(context) // 4
        logger.info(
            f"[context_node] Exceeded token budget (6000). Dropped {dropped_count} lowest-similarity chunk(s). Final estimated tokens: {final_est_tokens}"
        )
    else:
        logger.info(f"[context_node] Context built - {len(chunks)} chunks (Est. tokens: {est_tokens})")

    return {**state, "context": context, "retrieved_chunks": chunks}


#------Node 5: LLM -------------------

def llm_node(state: AgentState) -> AgentState:
    query = state["query"]
    context = state["context"]
    chat_history = state["chat_history"]

    # Build history string from DynamoDB format {"query", "answer", "timestamp"}
    history_str = ""
    for msg in chat_history[-4:]:
        q = msg.get("query", "")
        a = msg.get("answer", "")
        if q:
            history_str += f"User: {q}\n"
        if a:
            history_str += f"Assistant: {a}\n"

    prompt = f"""You are a helpful customer care assistant. Use the following information to answer the user's question:

1. **Chat History** — Use this to understand conversational context (e.g., follow-up questions, references to previous messages).
2. **Retrieved Context** — Use this for factual/domain-specific answers.

Rules:
- If the user is asking about something discussed in the chat history (e.g., "what did I ask before?", "repeat that", etc.), answer from the chat history.
- If the user is asking a factual question, answer from the retrieved context.
- If NEITHER the chat history NOR the retrieved context contains enough information to answer, say exactly: "I don't have enough information to answer this."
- Do NOT make up information. Only use what is provided.
- Answer naturally and directly. Do NOT say things like "based on our previous conversation", "according to chat history", or "from our earlier discussion". Just answer as if you always knew the answer.
- Only mention past conversations when the user explicitly asks about them (e.g., "what did I ask before?").

Chat History:
{history_str}

Retrieved Context:
{context}

User Question: {query}

Answer:"""

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    delays = [1, 2]
    max_retries = len(delays)

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )

            answer = response.choices[0].message.content.strip()
            finish_reason = response.choices[0].finish_reason
            truncated = (finish_reason == "length")
            if truncated:
                logger.warning("[llm_node] Response was truncated due to length limit (finish_reason='length')")
            logger.info(f"[llm_node] Answer generated ({len(answer)} chars)")
            return {**state, "answer": answer, "truncated": truncated}
        except Exception as e:
            exc_type = type(e).__name__
            if attempt < max_retries:
                delay = delays[attempt]
                logger.warning(
                    f"[llm_node] Call failed ({exc_type}: {e}). Retrying in {delay}s (attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(delay)
            else:
                logger.error(f"[llm_node] LLM call failed after {max_retries} retries ({exc_type}: {e})")
                return {
                    **state,
                    "answer": "I'm sorry, I'm experiencing technical difficulties. Please try again shortly.",
                    "truncated": False
                }


# ------- Groundedness Check --------------------

def check_groundedness(answer: str, context: str) -> bool:
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        prompt = f"Context:\n{context}\n\nAnswer:\n{answer}\n\nIs this answer fully supported by the context above? Reply with exactly one word: YES or NO."
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10
        )
        res_text = response.choices[0].message.content.strip()
        is_grounded = res_text.upper().startswith("YES")
        return is_grounded
    except Exception as e:
        logger.warning(f"[check_groundedness] Groundedness check failed: {e}")
        return True


#-------Node 6: Evaluation --------------------

def evaluation_node(state: AgentState)->AgentState:
    answer = state["answer"]
    chunks = state["retrieved_chunks"]
    retry_count = state.get("retry_count", 0)

    low_confidence_phrases = [
    "i don't have enough information",
    "i don't have the information",
    "i can not answer",
    "i cannot answer",
    "i'm not able to answer",
    "i am not able to answer",
    "not enough information",
    "no relevant information",
    "no information available",
    "cannot provide an answer",
    "don't have enough context",
    "does not contain enough information",
    "i'm sorry, i don't know",
    "i'm unable to",
    "the context does not",
    "not mentioned in the context",
    "no relevant context",
    ]

    llm_refused = any(phrase in answer.lower() for phrase in low_confidence_phrases)

    if not llm_refused:
        is_grounded = check_groundedness(state["answer"], state["context"])
        logger.info(f"[evaluation_node] Groundedness check result: {is_grounded}")
        if is_grounded:
            # LLM gave a confident answer — accept it
            logger.info(f"[evaluation_node] Confidence: high | Attempt: {retry_count + 1}")
            return {**state, "confidence": "high", "escalate": False}

    # LLM couldn't answer — decide: retry or escalate
    if retry_count < 2:
        # Retry with wider search params (max 3 attempts: 0, 1, 2)
        new_retry = retry_count + 1
        logger.info(f"[evaluation_node] LLM refused — retrying ({new_retry}/3) with wider search")
        return {
            **state,
            "confidence": "retry",
            "escalate": False,
            "retry_count": new_retry,
            "context": "",             # clear so context_node rebuilds from new chunks
            "retrieved_chunks": [],    # clear so retrieval_node fetches fresh
        }
    else:
        # All 3 attempts exhausted — escalate to human
        logger.info(f"[evaluation_node] All 3 attempts failed — escalating to human")
        return {**state, "confidence": "low", "escalate": True}

# ─── Node 7: Output ───────────────────────────────────────────────────────────

def output_node(state: AgentState) -> AgentState:
    session_id = state.get("session_id", "default-session")

    if state["escalate"]:
        send_to_sqs(
            session_id,
            state["query"],
            state["answer"]
        )
        escalation_msg = (
           "I don't have the answer for this. "
           "I've asked my team — they're on it. "
           "Ask me the same question again in about 1 minute. I'll have the answer."
        )
        # Save the escalation message to history (not the bad LLM answer)
        save_session(session_id, state["query"], escalation_msg)
        logger.info(f"[output_node] Escalating query to SQS - low confidence")
        return {**state, "answer": escalation_msg}
    else:
        # Save the good answer to history
        save_session(session_id, state["query"], state["answer"])
        logger.info(f"[output_node] Query resolved - no escalation needed")
    return state


#-----Routing Logic---------------------------

def route_after_input(state: AgentState):
    if state.get("error"):
        return END
    return "session_node"


def route_after_evaluation(state: AgentState):
    """After evaluation: retry retrieval or proceed to output."""
    if state.get("confidence") == "retry":
        return "retrieval_node"    # loop back for another attempt
    return "output_node"           # high or low → output


#--------------------build-Graph------------------------------------
def build_agent():
    graph = StateGraph(AgentState)

    graph.add_node("input_node", input_node)
    graph.add_node("session_node", session_node)
    graph.add_node("retrieval_node", retrieval_node)
    graph.add_node("context_node", context_node)
    graph.add_node("llm_node", llm_node)
    graph.add_node("evaluation_node", evaluation_node)
    graph.add_node("output_node", output_node)

    graph.set_entry_point("input_node")

    graph.add_conditional_edges("input_node", route_after_input)
    graph.add_edge("session_node", "retrieval_node")
    graph.add_edge("retrieval_node", "context_node")
    graph.add_edge("context_node", "llm_node")
    graph.add_edge("llm_node", "evaluation_node")
    # Retry loop: evaluation can route back to retrieval or forward to output
    graph.add_conditional_edges("evaluation_node", route_after_evaluation)
    graph.add_edge("output_node", END)

    return graph.compile()

agent = build_agent()

# ─── Run Function ─────────────────────────────────────────────────────────────

def run_agent(query: str, session_id: str = "test-session") -> dict:
    if session_id is None:
        session_id = str(uuid.uuid4())
    initial_state = AgentState(
        query=query,
        session_id=session_id,
        chat_history=[],
        retrieved_chunks=[],
        context="",
        answer="",
        confidence="",
        escalate=False,
        retry_count=0,
        error=None,
        truncated=False
    )
    result = agent.invoke(initial_state)
    return {
        "answer": result["answer"],
        "confidence": result["confidence"],
        "escalate": result["escalate"],
        "session_id": result["session_id"],
        "truncated": result.get("truncated", False)
    }

if __name__ == "__main__":
    response = run_agent("What is the return policy?")
    print("\n--- FINAL OUTPUT ---")
    print(f"Answer: {response['answer']}")
    print(f"Confidence: {response['confidence']}")
    print(f"Escalate: {response['escalate']}")
    print(f"Truncated: {response['truncated']}")