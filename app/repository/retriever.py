from typing import List, Tuple

import faiss
import numpy as np

from app.repository.chunker import CodeChunk
from app.repository.embedder import CodeEmbedder


class CodeRetriever:

    def __init__(
        self,
        chunks: List[CodeChunk],
        embeddings: np.ndarray,
        embedder: CodeEmbedder
    ):
        self.chunks = chunks
        self.embedder = embedder

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatL2(dimension)

        self.index.add(embeddings)

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Tuple[CodeChunk, float]]:

        query_embedding = self.embedder.embed_query(query)

        distances, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for distance, index in zip(
            distances[0],
            indices[0]
        ):
            if index == -1:
                continue

            results.append(
                (
                    self.chunks[index],
                    float(distance)
                )
            )

        return results