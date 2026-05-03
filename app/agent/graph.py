import os
import json
import boto3
from groq import Groq
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, List, Optional
from app.retrieval.pgvector_client import retrieve_similar
from app.memory.dynamodb_client import get_session, save_session
from app.escalation.sqs_worker import send_to_sqs


load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_ID = os.getenv("GROQ_API_KEY")

#
# -------------State Schema------------------------

class AgentState(TypedDict):
    query: str
    session_id: str
    chat_history: List[dict]
    retrieved_chunks: List[dict]
    context: str
    answer: str
    confidence: str     #high or low
    escalate: bool
    error: Optional[str]

#------Node 1: Input ----------------------------

def input_node(state: AgentState)-> AgentState:
    query = state["query"].strip()
    if not query:
        return {**state, "error": "Empty query recived"}
    print(f"[input_node] Query: {query}")
    return {**state, "query": query, "error": None}

#------ Node 2: Session (Dummy for now) --------


def session_node(state: AgentState) -> AgentState:
    session_id = state.get("session_id", "default-session")
    history = get_session(session_id)
    print(f"[session_node] Session: {session_id}, History length: {len(history)}")
    state["history"] = history
    return state


#--------------- Node 3: Retrieval -------------------------------

def retrieval_node(state: AgentState) -> AgentState:
    query = state["query"]
    print(f"[retrieval_node] Retrieving chunks for: {query}")
    chunks = retrieve_similar(query, top_k=5)
    print(f"[retrieval_node] {len(chunks)} chunks retrieved")
    return {**state, "retrieved_chunks": chunks}



#------Node 4: Context -----------------

def context_node(state: AgentState)-> AgentState:
    chunks = state["retrieved_chunks"]
    if not chunks:
        context = "No relevant context found"
    else:
        context = "\n\n".join([
            f"[Chunk {i+1} | Similarity: {c['similarity']:.2f}]\n{c['content']}"
            for i, c in enumerate(chunks)
        ])
    print(f"[context_node] Context built - {len(chunks)} chunks")
    return {**state, "context": context}


#------Node 5: LLM -------------------

def llm_node(state: AgentState) -> AgentState:
    query = state["query"]
    context = state["context"]
    chat_history = state["chat_history"]

    history_str = ""
    for msg in chat_history[-4:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_str += f"{role.capitalize()}: {content}\n"

    prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the context provided below.
If the context does not contain enough information to answer, say exactly: "I don't have enough information to answer this."

Chat History:
{history_str}

Context:
{context}

User Question: {query}

Answer:"""

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512
    )

    answer = response.choices[0].message.content.strip()
    print(f"[llm_node] Answer: {answer[:100]}...")
    return {**state, "answer": answer}
#-------Node 6: Evalution --------------------

def evaluation_node(state: AgentState)->AgentState:
    answer = state["answer"]
    chunks = state["retrieved_chunks"]


    #Low confidence if: no chunks or llm said it doesn't know. 
    low_confidence_phrases = [
        "I don't have enough information",
        "I can not answer",
        "not enough information",
        "based only on the context provided",
        "no relevent information"
    ]

    is_low = (
        len(chunks) == 0 or 
        any(phrase in answer.lower() for phrase in low_confidence_phrases)
    )
    confidence = "low" if is_low else "high"
    escalate = is_low

    print(f"[evaluation_node] Confidence: {confidence} | Escalate: {escalate}")
    return {**state, "confidence": confidence, "escalate": escalate}

# ─── Node 7: Output ───────────────────────────────────────────────────────────

def output_node(state: AgentState) -> AgentState:
    save_session(
        state.get("session_id", "default-session"),
        state["query"],
        state["answer"]
    )
    if state["escalate"]:
        send_to_sqs(
            state["session_id"],
            state["query"],
            state["answer"]
        )
        print(f"[output_node] Escalating query to SQS - low confidence")
    else:
        print(f"[output_node] Query resolved - no escalation needed")
    return state


#-----Routing Logic---------------------------

def route_after_input(state: AgentState):
    if(state.get("erro")):
        return END
    return "session_node"


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
    graph.add_edge("evaluation_node", "output_node")
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
        error=None
    )
    result = agent.invoke(initial_state)
    return {
        "answer": result["answer"],
        "confidence": result["confidence"],
        "escalate": result["escalate"],
        "session_id": result["session_id"]
    }

if __name__ == "__main__":
    response = run_agent("What is the return policy?")
    print("\n--- FINAL OUTPUT ---")
    print(f"Answer: {response['answer']}")
    print(f"Confidence: {response['confidence']}")
    print(f"Escalate: {response['escalate']}")