from fastapi import APIRouter, HTTPException
import asyncio
import httpx
import logging
from pinecone import Pinecone, ServerlessSpec
from openai import AsyncOpenAI
import re
import os

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProductsAPI")

# --- API Keys ---
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")

# --- Clients ---
openai_client = AsyncOpenAI(api_key=OPENAI_KEY)
pc = Pinecone(api_key=PINECONE_KEY)

index_name = "zuscoffee-products"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
index = pc.Index(index_name)


# --- INGEST PRODUCTS ---
async def ingest_products(
    product_url: str = "https://shop.zuscoffee.com/collections/drinkware/products.json"
):
    try:
        logger.info("Fetching product JSON...")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(product_url)

        response.raise_for_status()
        data = response.json()
        products = data.get("products", [])

        if not products:
            logger.warning("No products found in source JSON.")
            return []

        logger.info(f"Fetched {len(products)} products. Generating embeddings...")

        semaphore = asyncio.Semaphore(5)

        async def embed_product(prod):
            async with semaphore:
                title = prod.get("title", "Unknown")
                description = prod.get("body_html", "")
                price = prod.get("variants", [{}])[0].get("price", "N/A")
                text = f"Product: {title}\nDescription: {description}\nPrice: RM{price}"

                # Get embedding
                emb = await openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )

                return {
                    "id": f"product-{prod['id']}",
                    "values": emb.data[0].embedding,
                    "metadata": {
                        "name": title,
                        "description": description,
                        "price": price,
                        "type": "product"
                    }
                }

        # Parallel embeddings
        vectors = await asyncio.gather(*[embed_product(p) for p in products])
        vectors = [v for v in vectors if v]

        # Upload in batches of 50
        for i in range(0, len(vectors), 50):
            batch = vectors[i:i + 50]
            index.upsert(batch)
            logger.info(f"Uploaded batch {i//50 + 1}: {len(batch)} vectors")

        logger.info(f"✅ Successfully ingested {len(vectors)} products.")
        return vectors

    except Exception as e:
        logger.exception("Error during product ingestion:")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# Query Products
# ---------------------------------------------------------
@router.get("/query", tags=["Products"])
async def query_products(query: str, top_k: int = 50):
    try:
        q_lower = query.lower()

        # ---------------------------------------------------------
        # Count Query Detection
        # ---------------------------------------------------------
        if re.search(r"\b(how many|count|number of|products)\b", q_lower):
            stats = index.describe_index_stats()
            total = stats.get("total_vector_count", 0)

            return {
                "query": query,
                "response": f"There are {total} products available.",
                "matches_found": total
            }

        # ---------------------------------------------------------
        # Semantic Search
        # ---------------------------------------------------------
        emb = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )

        embedding = emb.data[0].embedding

        search = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter={"type": "product"}  # ensure only product vectors returned
        )

        matches = search.get("matches", [])
        if not matches:
            return {
                "query": query,
                "response": "No matching products found.",
                "matches_found": 0
            }

        products = [
            {
                "name": m["metadata"].get("name"),
                "price": m["metadata"].get("price"),
                "description": m["metadata"].get("description")
            }
            for m in matches
        ]

        # ---------------------------------------------------------
        # Generate AI answer
        # ---------------------------------------------------------
        user_prompt = f"User question: {query}\n\nProducts:\n{products}"

        completion = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful retail assistant."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        answer = completion.choices[0].message.content

        return {
            "query": query,
            "response": answer,
            "matches_found": len(products),
            "products": products
        }

    except Exception as e:
        logger.exception("Error during product query:")
        raise HTTPException(status_code=500, detail=str(e))