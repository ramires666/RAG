import hashlib
import re
from functools import partial

import numpy as np
from lightrag.utils import EmbeddingFunc


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


async def hash_embed(texts: list[str], embedding_dim: int = 1024, **_: object) -> np.ndarray:
    vectors: list[np.ndarray] = []
    for text in texts:
        vector = np.zeros(embedding_dim, dtype=np.float32)
        for token in TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:8], "little") % embedding_dim
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            vector[index] += sign

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        vectors.append(vector)

    if not vectors:
        return np.zeros((0, embedding_dim), dtype=np.float32)

    return np.stack(vectors)


def make_hash_embedding_func(embedding_dim: int) -> EmbeddingFunc:
    return EmbeddingFunc(
        embedding_dim=embedding_dim,
        func=partial(hash_embed, embedding_dim=embedding_dim),
        model_name=f"local-hash-{embedding_dim}",
    )
