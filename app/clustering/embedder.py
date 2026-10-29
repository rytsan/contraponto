import hashlib
import re
from typing import Callable, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Article

MAX_TEXT_PREFIX_CHARS = 1500
DEFAULT_EMBEDDING_DIM = 384


def build_embedding_input(title: str, clean_text: str) -> str:
    """Monta a string de entrada para embedding: título + primeiros 1.500 caracteres do texto."""
    t = (title or "").strip()
    body = (clean_text or "").strip()[:MAX_TEXT_PREFIX_CHARS]
    if body:
        return f"{t}\n\n{body}"
    return t


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Normaliza vetor (ou matriz 2D de vetores) pela norma L2 em float32."""
    arr = np.asarray(vector, dtype=np.float32)
    if arr.ndim == 1:
        norm = float(np.linalg.norm(arr))
        if norm > 1e-12:
            arr = arr / norm
        return arr.astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    return (arr / norms).astype(np.float32)


def serialize_embedding(vector: np.ndarray) -> bytes:
    """Serializa vetor numpy float32 normalizado para bytes (BLOB do SQLite)."""
    normalized = l2_normalize(vector)
    return normalized.astype(np.float32).tobytes()


def deserialize_embedding(blob: bytes) -> np.ndarray:
    """Reconstrói vetor numpy float32 a partir de BLOB armazenado no SQLite."""
    return np.frombuffer(blob, dtype=np.float32).copy()


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Calcula similaridade cosseno entre dois vetores normalizados L2."""
    a = l2_normalize(vec_a)
    b = l2_normalize(vec_b)
    if a.shape != b.shape or a.size == 0:
        return 0.0
    sim = float(np.dot(a, b))
    return max(-1.0, min(1.0, sim))


def _deterministic_local_encode(text: str, dim: int = DEFAULT_EMBEDDING_DIM) -> np.ndarray:
    """
    Codificador local determinístico baseado em n-gramas de palavras e caracteres,
    usado como fallback offline caso os pesos do sentence-transformers não estejam em cache.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", (text or "").lower())
    if not tokens:
        tokens = ["vazio"]

    features: List[str] = list(tokens)
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")

    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    return l2_normalize(vec)


class ArticleEmbedder:
    """Gerador e gerenciador de embeddings em SQLite (fonte da verdade) e espelho opcional no Qdrant."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        encode_fn: Optional[Callable[[str], np.ndarray]] = None,
        use_qdrant: Optional[bool] = None,
        qdrant_url: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._custom_encode_fn = encode_fn
        self._st_model = None
        self._st_load_attempted = False
        self.use_qdrant = settings.USE_QDRANT if use_qdrant is None else use_qdrant
        self.qdrant_url = qdrant_url or settings.QDRANT_URL

    def _get_sentence_transformer(self):  # type: ignore[no-untyped-def]
        if self._st_load_attempted:
            return self._st_model
        self._st_load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
            self._st_model = SentenceTransformer(self.model_name, local_files_only=True)
        except Exception:
            self._st_model = None
        return self._st_model

    def encode_text(self, text: str) -> np.ndarray:
        """Gera vetor normalizado L2 para o texto informado."""
        if self._custom_encode_fn is not None:
            return l2_normalize(self._custom_encode_fn(text))

        model = self._get_sentence_transformer()
        if model is not None:
            raw_vec = model.encode(text, normalize_embeddings=True)
            return l2_normalize(np.asarray(raw_vec, dtype=np.float32))

        return _deterministic_local_encode(text, dim=DEFAULT_EMBEDDING_DIM)

    def embed_article(self, db: Session, article: Article, force: bool = False) -> np.ndarray:
        """
        Gera e persiste o embedding de um artigo no SQLite (e espelha no Qdrant se ativo).
        Reprocessa automaticamente se o modelo registrado diferir de self.model_name.
        """
        if (
            not force
            and article.embedding_blob is not None
            and article.embedding_model == self.model_name
        ):
            return deserialize_embedding(article.embedding_blob)

        input_text = build_embedding_input(article.titulo, article.texto_limpo)
        vector = self.encode_text(input_text)
        article.embedding_blob = serialize_embedding(vector)
        article.embedding_model = self.model_name
        db.add(article)
        db.commit()
        db.refresh(article)

        if self.use_qdrant:
            self._mirror_to_qdrant(article, vector)

        return vector

    def _mirror_to_qdrant(self, article: Article, vector: np.ndarray) -> None:
        """Espelha o vetor no Qdrant quando USE_QDRANT=true (falha silenciosa caso indisponível)."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams

            client = QdrantClient(url=self.qdrant_url, timeout=5)
            collection_name = "contraponto_articles"
            collections = [c.name for c in client.get_collections().collections]
            if collection_name not in collections:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=int(vector.size), distance=Distance.COSINE),
                )
            client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=article.id,
                        vector=vector.tolist(),
                        payload={
                            "article_id": article.id,
                            "source_id": article.source_id,
                            "veiculo": article.veiculo,
                            "titulo": article.titulo,
                            "embedding_model": self.model_name,
                        },
                    )
                ],
            )
        except Exception:
            pass
