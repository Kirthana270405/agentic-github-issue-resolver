from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.repository.chunker import CodeChunk


class CodeEmbedder:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2"
    ):
        print(f"Loading embedding model: {model_name}")

        self.model = SentenceTransformer(model_name)

    def embed_chunks(
        self,
        chunks: List[CodeChunk]
    ) -> np.ndarray:

        texts = [
            chunk.content
            for chunk in chunks
        ]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True
        )

        return embeddings.astype("float32")

    def embed_query(
        self,
        query: str
    ) -> np.ndarray:

        embedding = self.model.encode(
            [query],
            convert_to_numpy=True
        )

        return embedding.astype("float32")