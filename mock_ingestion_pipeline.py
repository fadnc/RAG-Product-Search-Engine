# Mock Data Ingestion + Vector DB Upsert Pipeline

"""
This script simulates the product ingestion + chunking + embedding + vector DB upsert flow.
It works without any real API keys or external services.

You can later swap the MockVectorDB and MockEmbeddingModel with real providers.
"""

import uuid
import json
from typing import List, Dict

# -----------------------------
# Mock Embedding Model
# -----------------------------
class MockEmbeddingModel:
    def embed(self, text: str) -> List[float]:
        # Fake embedding (deterministic hash --> vector of floats)
        seed = abs(hash(text)) % 1000
        return [float((seed * i) % 97) for i in range(128)]  # 128-dim vector

# -----------------------------
# Mock Vector Database
# -----------------------------
class MockVectorDB:
    def __init__(self):
        self.store = {}

    def upsert(self, vector: List[float], metadata: Dict) -> str:
        vector_id = str(uuid.uuid4())
        self.store[vector_id] = {
            "vector": vector,
            "metadata": metadata
        }
        return vector_id

# -----------------------------
# Chunking Utility
# -----------------------------
def chunk_text(text: str, max_words: int = 120, overlap: int = 20) -> List[str]:
    words = text.split()
    chunks = []
    step = max_words - overlap

    for i in range(0, len(words), step):
        chunk = " ".join(words[i: i + max_words])
        chunks.append(chunk)
    return chunks

# -----------------------------
# Product Ingestion Pipeline
# -----------------------------
class ProductIngestionPipeline:
    def __init__(self):
        self.embedder = MockEmbeddingModel()
        self.vector_db = MockVectorDB()
        self.products_table = {}  # acts like Postgres
        self.embeddings_table = []

    def ingest_product(self, product: Dict):
        product_id = product.get("id", str(uuid.uuid4()))
        self.products_table[product_id] = product

        chunks = chunk_text(product["description"], max_words=100, overlap=25)

        for idx, chunk in enumerate(chunks):
            vector = self.embedder.embed(chunk)
            metadata = {
                "product_id": product_id,
                "chunk_id": f"{product_id}_{idx}",
                "title": product["title"],
                "category": product.get("category", "unknown"),
                "price": product.get("price", None),
            }

            vector_id = self.vector_db.upsert(vector, metadata)

            self.embeddings_table.append({
                "product_id": product_id,
                "chunk_id": metadata["chunk_id"],
                "text_chunk": chunk,
                "embedding_model": "mock",
                "vector_id": vector_id
            })

        print(f"Ingested product: {product_id} with {len(chunks)} chunks")

# -----------------------------
# Run Example
# -----------------------------
if __name__ == "__main__":
    pipeline = ProductIngestionPipeline()

    sample_product = {
        "id": "P123",
        "title": "Noise Cancelling Headphones",
        "description": "High quality wireless headphones with active noise cancellation. Long battery life, comfortable design, deep bass, and clear sound for travel and work.",
        "category": "electronics",
        "price": 2999
    }

    pipeline.ingest_product(sample_product)

    print("\nVector DB entries:")
    print(json.dumps(list(pipeline.vector_db.store.items())[:1], indent=2))

    print("\nEmbeddings table sample:")
    print(json.dumps(pipeline.embeddings_table[:1], indent=2))
