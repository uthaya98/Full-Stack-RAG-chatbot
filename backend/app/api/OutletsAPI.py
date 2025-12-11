from fastapi import APIRouter, HTTPException, Query
import feedparser
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import logging
import uuid
import asyncio
import time
import concurrent.futures
import re
import os

# -----------------------------
# Setup logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OutletsAPI")

router = APIRouter()

# -----------------------------
# API Keys
# -----------------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")

# --- Clients ---
openai_client = OpenAI(api_key=OPENAI_KEY)
pc = Pinecone(api_key=PINECONE_KEY)
index_name = "zuscoffee-outlets"

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
index = pc.Index(index_name)

from fastapi import APIRouter, HTTPException, Query
import feedparser
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import logging
import uuid
import asyncio
import time
import re

# -----------------------------
# Setup logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OutletsAPI")

router = APIRouter()

# -----------------------------
# API Keys
# -----------------------------
OPENAI_KEY = "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"
PINECONE_KEY = "pcsk_3PkahH_5DtkkCHW8df2u94x5poEss4Jbp9GdL9hVhp7hjt1Jt5sEz4TNTfHj5BhzJFUBqE"

# --- Clients ---
openai_client = OpenAI(api_key=OPENAI_KEY)
pc = Pinecone(api_key=PINECONE_KEY)
index_name = "zuscoffee-outlets"

if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
index = pc.Index(index_name)

# ---------------------------------------------------------
# City list
# ---------------------------------------------------------
CITY_LIST = [
    "Kuala Lumpur", "Shah Alam", "Petaling Jaya", "Subang Jaya", "Puchong",
    "Kajang", "Selayang", "Rawang", "Ampang", "Bangi", "Cyberjaya", "Putrajaya",
    "Cheras", "Sungai Buloh", "Klang", "Serdang", "Gombak", "Damansara",
    "Sepang", "Seri Kembangan"
]


def extract_cities(query: str):
    """Simple rule-based city extractor."""
    return [c for c in CITY_LIST if c.lower() in query.lower()]


# ---------------------------------------------------------
# Fetch outlets (RSS pagination)
# ---------------------------------------------------------
def fetch_outlets(
    feed_url="https://zuscoffee.com/category/store/kuala-lumpur-selangor/feed/",
    max_pages=20
):
    all_outlets = []

    for page in range(1, max_pages + 1):
        feed = feedparser.parse(f"{feed_url}?paged={page}")
        if not feed.entries:
            break

        for entry in feed.entries:
            name = entry.title.strip()
            address = (
                entry.get("description", "")
                .replace("<br>", " ")
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )
            all_outlets.append({
                "name": name,
                "address": address,
                "city": "KL/SEL"
            })

    logger.info(f"Fetched {len(all_outlets)} outlets")
    return all_outlets


# ---------------------------------------------------------
# Correct Async Embedding Helper
# (OpenAI does NOT support async embeddings)
# ---------------------------------------------------------
async def get_embedding(text: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_embed, text)


def _sync_embed(text: str):
    """Runs in a background thread."""
    resp = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding


# ---------------------------------------------------------
# Ingest outlets into Pinecone
# ---------------------------------------------------------
async def ingest_outlets():
    try:
        outlets = fetch_outlets()
        if not outlets:
            return []

        semaphore = asyncio.Semaphore(5)

        async def embed(outlet, idx):
            async with semaphore:
                text = f"{outlet['name']} - {outlet['address']}"
                emb = await get_embedding(text)

                return {
                    "id": f"outlet-{idx}-{uuid.uuid4().hex[:6]}",
                    "values": emb,
                    "metadata": {
                        "name": outlet["name"],
                        "address": outlet["address"],
                        "city": outlet["city"],
                        "text": text,
                        "type": "outlet",
                        "hours": "Not available"
                    }
                }

        vectors = await asyncio.gather(*[
            embed(o, i) for i, o in enumerate(outlets)
        ])

        vectors = [v for v in vectors if v]

        # Batch upsert
        for i in range(0, len(vectors), 50):
            index.upsert(vectors[i:i + 50])

        logger.info(f"✅ Ingested {len(vectors)} outlets.")
        return vectors

    except Exception as e:
        logger.exception("Error ingesting outlets")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# Query Outlets
# ---------------------------------------------------------
@router.get("/query", tags=["Outlets"])
async def query_outlets(
    query: str = Query(..., description="Natural-language query about outlets"),
    top_k: int = 40
):
    try:
        q_lower = query.lower()

        # Extract city names
        cities = extract_cities(query)

        # Compute embedding
        embedding = await get_embedding(query)

        # Pinecone filter
        filter_dict = {"type": "outlet"}
        if cities:
            filter_dict["city"] = {"$in": cities}

        # Perform semantic search
        results = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict
        )
        matches = results.get("matches", [])

        # ---------------------------------------------------------
        # COUNT QUERY DETECTION
        # ---------------------------------------------------------
        count_regex = (
            r"\b(how many|count|number of|total outlets|store count|"
            r"outlet count|stores)\b"
        )

        if re.search(count_regex, q_lower):

            # GLOBAL COUNT
            stats = index.describe_index_stats()
            total = stats.get("total_vector_count", 0)

            if not cities:
                return {
                    "query": query,
                    "response": f"There are {total} outlets across all cities.",
                    "matches_found": total,
                    "cities_detected": []
                }

            # CITY-SPECIFIC COUNT
            all_city_matches = []
            city_total = 0

            for city in cities:
                city_results = index.query(
                    vector=[0] * 1536,
                    top_k=5000,
                    include_metadata=True,
                    filter={
                        "type": "outlet",
                        "city": {"$eq": city}
                    }
                )
                matches_city = city_results.get("matches", [])
                all_city_matches.extend(matches_city)
                city_total += len(matches_city)

            return {
                "query": query,
                "response": f"There are {city_total} outlets in {', '.join(cities)}.",
                "matches_found": city_total,
                "cities_detected": cities,
                "outlets": [
                    {
                        "name": m["metadata"]["name"],
                        "address": m["metadata"]["address"],
                        "city": m["metadata"]["city"],
                        "hours": m["metadata"].get("hours", "Not available")
                    }
                    for m in all_city_matches
                ]
            }

        # ---------------------------------------------------------
        # NORMAL QUERY RESPONSE
        # ---------------------------------------------------------
        if not matches:
            return {
                "query": query,
                "response": "No matching outlets found.",
                "cities_detected": cities
            }

        outlets = [
            {
                "name": m["metadata"]["name"],
                "address": m["metadata"]["address"],
                "city": m["metadata"]["city"],
                "hours": m["metadata"].get("hours", "Not available")
            }
            for m in matches
        ]

        if "hour" in q_lower:
            for o in outlets:
                o["hours"] = "Check website for updated operating hours"

        return {
            "query": query,
            "response": "Outlets retrieved successfully.",
            "matches_found": len(outlets),
            "cities_detected": cities,
            "outlets": outlets
        }

    except Exception as e:
        logger.exception("Error querying outlets")
        raise HTTPException(status_code=500, detail=str(e))
