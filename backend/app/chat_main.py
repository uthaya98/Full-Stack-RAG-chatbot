from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
import openai
import logging
import numpy as np
import asyncio
import os

# Local modules
from app.memory import ConversationMemory
from app.api.ProductsAPI import router as products_router, ingest_products, query_products
from app.api.OutletsAPI import router as outlets_router, ingest_outlets, query_outlets
from app.api.Calculator import safe_eval

# --- OpenAI setup ---
openai.api_key = os.getenv("OPENAI_API_KEY") # replace with your actual key

# --- FastAPI setup ---
app = FastAPI(title="ZusCoffee Chatbot Backend")

# Include routers
app.include_router(products_router, prefix="/products", tags=["Products"])
app.include_router(outlets_router, prefix="/outlets", tags=["Outlets"])

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --- Intent & Query Examples ---
INTENT_EXAMPLES = {
    "calc": ["calculate", "what is", "compute", "solve"],
    "products": ["what products", "show me products", "product list", "calories", "price"],
    "outlets": ["where is", "find outlet", "coffee shop near me", "location", "opening hours"],
}

QUERY_TYPE_EXAMPLES = {
    "count": ["how many", "total number", "number of", "count"],
    "time": ["opening time", "hours", "when does"],
    "attribute": ["calories", "price", "ingredients", "nutrition"],
    "general": ["what", "which", "tell me", "give me info"],
}

# --- Precompute embeddings ---
def embed_text(text: str):
    resp = openai.embeddings.create(model="text-embedding-3-small", input=text)
    return np.array(resp.data[0].embedding)

INTENT_EXAMPLES_EMBED = {
    intent: [embed_text(ex) for ex in examples]
    for intent, examples in INTENT_EXAMPLES.items()
}

QUERY_TYPE_EXAMPLES_EMBED = {
    qtype: [embed_text(ex) for ex in examples]
    for qtype, examples in QUERY_TYPE_EXAMPLES.items()
}

# --- Memory Setup ---
memory = ConversationMemory()

# --- LangChain LLM ---
llm = ChatOpenAI(
    temperature=0.9,
    model_name="gpt-3.5-turbo",
    max_tokens=200,
    openai_api_key=openai.api_key
)

# RunnableWithMessageHistory
def get_history_for_session(session_id: str):
    messages = []
    for turn in memory.get_history(session_id):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "bot":
            messages.append(AIMessage(content=turn["content"]))
    return messages

chat_history = RunnableWithMessageHistory(runnable=llm, get_session_history=get_history_for_session)

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    info: dict = {}

# --- Intent & Query Detection ---
def detect_intent_and_type(user_text: str):
    query_emb = embed_text(user_text)

    # Determine intent
    intent_scores = {}
    for intent, embeddings in INTENT_EXAMPLES_EMBED.items():
        sims = [np.dot(query_emb, ex_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(ex_emb)) for ex_emb in embeddings]
        intent_scores[intent] = max(sims)
    best_intent = max(intent_scores, key=intent_scores.get)

    # Determine query type
    type_scores = {}
    for qtype, embeddings in QUERY_TYPE_EXAMPLES_EMBED.items():
        sims = [np.dot(query_emb, ex_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(ex_emb)) for ex_emb in embeddings]
        type_scores[qtype] = max(sims)
    best_type = max(type_scores, key=type_scores.get)

    # Handle count queries
    if best_type == "count":
        if any(w in user_text.lower() for w in ["drink", "drinks", "product", "products"]):
            best_intent = "products"
        elif any(w in user_text.lower() for w in ["outlet", "store", "location", "locations"]):
            best_intent = "outlets"
        else:
            best_intent = "general"

    return {"intent": best_intent, "query_type": best_type}

# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    """
    Run ingestion for products and outlets concurrently at startup.
    """
    try:
        results = await asyncio.gather(
            ingest_products(),
            ingest_outlets(),
            return_exceptions=True
        )

        for r in results:
            if isinstance(r, Exception):
                print("⚠️ Ingestion task failed:", r)

        print("✅ Parallel ingestion completed successfully.")
    except Exception as e:
        print("⚠️ Unexpected error during startup ingestion:", e)

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Chat Endpoint ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message:
        raise HTTPException(status_code=400, detail="Message required")

    session_id = req.session_id or str(uuid.uuid4())
    user_text = req.message.strip()
    memory.add_turn(session_id, "user", user_text)
    logger.info(f"🟢 Incoming chat: session_id={session_id}, message='{user_text}'")

    # Detect intent & query type
    intent_obj = detect_intent_and_type(user_text)
    intent = intent_obj["intent"]
    query_type = intent_obj["query_type"]

    reply = ""
    try:
        if intent == "calc":
            expr = user_text.replace("calculate", "").replace("/calc", "").strip()
            try:
                result = safe_eval(expr)
                reply = f"The answer is **{result}**."
            except Exception as e:
                reply = f"Sorry, I couldn't calculate that. ({e})"

        elif intent == "products":
            product_results = await query_products(user_text)
            if query_type == "count":
                reply = f"There are **{len(product_results)} drinks/products** matching your query."
            elif query_type == "attribute":
                attr_texts = [
                    f"{r.get('metadata', {}).get('name', 'Unknown')} — Price: {r.get('metadata', {}).get('price', 'N/A')}, Calories: {r.get('metadata', {}).get('calories', 'N/A')}"
                    for r in product_results
                ]
                reply = "Here are the products with details:\n" + "\n".join(attr_texts)
            else:
                reply = "Here are some products I found:\n" + "\n".join([r["metadata"]["text"] for r in product_results])

        elif intent == "outlets":
            outlet_results = await query_outlets(user_text)  # <-- add await here
            if query_type == "count":
                reply = f"There are **{len(outlet_results)} outlets** matching your query."
            elif query_type == "time":
                times = [
                    f"{r.get('metadata', {}).get('name', 'Unknown')}: {r.get('metadata', {}).get('hours', 'N/A')}"
                    for r in outlet_results
                ]
                reply = "Outlet opening hours:\n" + "\n".join(times)
            else:
                reply = "Here are the nearby outlets:\n" + "\n".join([r["metadata"]["text"] for r in outlet_results])


        else:
            response = await chat_history.invoke_async(session_id=session_id, input=user_text)
            reply = response.content.strip() if hasattr(response, "content") else str(response)

        memory.add_turn(session_id, "bot", reply)
        return ChatResponse(reply=reply, info={"intent": intent, "query_type": query_type, "session_id": session_id})

    except Exception as e:
        reply = "Oops, something went wrong. Please try again."
        memory.add_turn(session_id, "bot", reply)
        return ChatResponse(reply=reply, info={"error": str(e), "session_id": session_id})
    