import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple
import numpy as np
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Article, Event, Source, VALID_THEMES, utcnow
from app.clustering.embedder import (
    ArticleEmbedder,
    cosine_similarity,
    deserialize_embedding,
    l2_normalize,
)
from app.clustering.entity_extractor import (
    classify_theme,
    entity_jaccard_similarity,
    extract_entities,
    extract_primary_location,
)

TIME_WINDOWS_HOURS = (24, 48, 72)


class NominatimGeocoderCache:
    """Geocodificador Nominatim com cache local em JSON. Nunca usa LLM para inferir coordenadas."""

    def __init__(
        self,
        cache_path: str = ".nominatim_cache.json",
        enabled: bool = True,
        geocode_fn: Optional[Callable[[str], Optional[Tuple[float, float]]]] = None,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.enabled = enabled
        self._custom_geocode_fn = geocode_fn
        self._cache: Dict[str, Optional[Dict[str, float]]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._cache = data
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def geocode(self, location_name: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        """Retorna (lat, lon) para um nome de local claro ou (None, None) se ausente/indisponível."""
        if not location_name or not location_name.strip():
            return None, None

        key = location_name.strip().lower()
        if key in self._cache:
            cached = self._cache[key]
            if cached and "lat" in cached and "lon" in cached:
                return float(cached["lat"]), float(cached["lon"])
            return None, None

        if self._custom_geocode_fn is not None:
            coords = self._custom_geocode_fn(location_name.strip())
            if coords is not None:
                lat, lon = float(coords[0]), float(coords[1])
                self._cache[key] = {"lat": lat, "lon": lon}
                self._save_cache()
                return lat, lon
            self._cache[key] = None
            self._save_cache()
            return None, None

        if not self.enabled:
            return None, None

        try:
            from geopy.geocoders import Nominatim  # type: ignore[import-untyped]

            geolocator = Nominatim(user_agent="ContrapontoGeocode/1.0", timeout=5)
            loc = geolocator.geocode(location_name.strip())
            if loc is not None and loc.latitude is not None and loc.longitude is not None:
                lat, lon = float(loc.latitude), float(loc.longitude)
                self._cache[key] = {"lat": lat, "lon": lon}
                self._save_cache()
                return lat, lon
        except Exception:
            pass

        self._cache[key] = None
        self._save_cache()
        return None, None


def compute_cohesion_score(vectors: List[np.ndarray]) -> float:
    """
    Calcula o score_coesao (0 a 1) como a média da similaridade cosseno
    de cada artigo em relação ao centróide do cluster.
    """
    if not vectors:
        return 0.0
    if len(vectors) == 1:
        return 1.0

    norm_vecs = [l2_normalize(v) for v in vectors]
    centroid = l2_normalize(np.mean(np.stack(norm_vecs, axis=0), axis=0))
    sims = [max(0.0, cosine_similarity(v, centroid)) for v in norm_vecs]
    mean_sim = float(np.mean(sims))
    return round(max(0.0, min(1.0, mean_sim)), 4)


def _merge_cluster_entities(
    articles: List[Article],
    indices: List[int],
) -> Dict[str, List[str]]:
    merged: Dict[str, Set[str]] = {}
    for i in indices:
        ent = articles[i].entidades_extraidas or {}
        for k, vals in ent.items():
            if isinstance(vals, list):
                merged.setdefault(k, set()).update(str(v) for v in vals)
    return {k: sorted(v) for k, v in merged.items()}


def _within_time_window(
    articles: List[Article],
    cluster_a: List[int],
    cluster_b: List[int],
    max_hours: int,
) -> bool:
    """Verifica se todos os artigos da união de dois clusters cabem na janela temporal (em horas)."""
    timestamps: List[datetime] = []
    for idx in cluster_a + cluster_b:
        art = articles[idx]
        dt = art.data_publicacao or art.data_coleta
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamps.append(dt)
    if len(timestamps) < 2:
        return True
    span = max(timestamps) - min(timestamps)
    return span <= timedelta(hours=max_hours)


def agglomerative_average_linkage_clusters(
    articles: List[Article],
    vectors: List[np.ndarray],
    similarity_threshold: float,
    window_hours: int = 72,
) -> List[List[int]]:
    """
    Executa agrupamento aglomerativo (average linkage) sobre similaridade cosseno,
    reforçado por sobreposição de entidades (Jaccard >= 0.3 permite unir clusters
    com similaridade até 0.05 abaixo do limiar), respeitando a janela de horas.
    """
    n = len(articles)
    if n == 0:
        return []
    if n == 1:
        return [[0]]

    sim_matrix = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        sim_matrix[i, i] = 1.0
        for j in range(i + 1, n):
            s = cosine_similarity(vectors[i], vectors[j])
            sim_matrix[i, j] = s
            sim_matrix[j, i] = s

    clusters: List[List[int]] = [[i] for i in range(n)]

    for current_window in TIME_WINDOWS_HOURS:
        if current_window > window_hours:
            break

        while len(clusters) > 1:
            best_pair: Optional[Tuple[int, int]] = None
            best_effective_score = -1.0

            for ci in range(len(clusters)):
                for cj in range(ci + 1, len(clusters)):
                    c_a = clusters[ci]
                    c_b = clusters[cj]

                    if not _within_time_window(articles, c_a, c_b, current_window):
                        continue

                    pair_sims = [sim_matrix[idx_a, idx_b] for idx_a in c_a for idx_b in c_b]
                    avg_sim = float(np.mean(pair_sims))

                    ent_a = _merge_cluster_entities(articles, c_a)
                    ent_b = _merge_cluster_entities(articles, c_b)
                    jaccard = entity_jaccard_similarity(ent_a, ent_b)

                    effective_threshold = (
                        similarity_threshold - 0.05
                        if jaccard >= 0.3
                        else similarity_threshold
                    )

                    if avg_sim >= effective_threshold and avg_sim > best_effective_score:
                        best_effective_score = avg_sim
                        best_pair = (ci, cj)

            if best_pair is None:
                break

            i_merge, j_merge = best_pair
            clusters[i_merge] = clusters[i_merge] + clusters[j_merge]
            del clusters[j_merge]

    return clusters


class EventClusterer:
    """Agrupador de matérias em eventos com seleção de divergência de enquadramento."""

    def __init__(
        self,
        db: Session,
        embedder: Optional[ArticleEmbedder] = None,
        geocoder: Optional[NominatimGeocoderCache] = None,
        similarity_threshold: Optional[float] = None,
    ) -> None:
        self.db = db
        self.embedder = embedder or ArticleEmbedder()
        self.geocoder = geocoder or NominatimGeocoderCache(enabled=False)
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.EMBEDDING_SIMILARITY_THRESHOLD
        )

    def prepare_articles(self, articles: List[Article]) -> List[np.ndarray]:
        """Garante que todos os artigos possuam entidades extraídas e embeddings persistidos."""
        vectors: List[np.ndarray] = []
        for art in articles:
            if not art.entidades_extraidas:
                combined_text = f"{art.titulo}\n{art.texto_limpo}"
                art.entidades_extraidas = extract_entities(combined_text)
                self.db.add(art)
                self.db.commit()
            vec = self.embedder.embed_article(self.db, art)
            vectors.append(vec)
        return vectors

    def cluster_articles(
        self,
        articles: Optional[List[Article]] = None,
        window_hours: int = 72,
    ) -> List[Event]:
        """Agrupa artigos e persiste/atualiza registros na tabela events."""
        if articles is None:
            articles = (
                self.db.query(Article)
                .filter(Article.is_demo.is_(False))
                .order_by(Article.data_publicacao.asc().nullsfirst(), Article.data_coleta.asc())
                .all()
            )
        if not articles:
            return []

        vectors = self.prepare_articles(articles)
        cluster_indices_list = agglomerative_average_linkage_clusters(
            articles=articles,
            vectors=vectors,
            similarity_threshold=self.similarity_threshold,
            window_hours=window_hours,
        )

        persisted_events: List[Event] = []
        for idx_group in cluster_indices_list:
            cluster_arts = [articles[i] for i in idx_group]
            cluster_vecs = [vectors[i] for i in idx_group]

            existing_event: Optional[Event] = None
            for art in cluster_arts:
                if art.event_id:
                    ev = self.db.query(Event).filter(Event.id == art.event_id).first()
                    if ev is not None and not ev.is_demo:
                        existing_event = ev
                        break

            cohesion = compute_cohesion_score(cluster_vecs)
            combined_text = "\n".join(f"{a.titulo} {a.resumo} {a.texto_limpo[:600]}" for a in cluster_arts)
            tema = classify_theme(combined_text)
            if tema not in VALID_THEMES:
                tema = "outros"

            merged_entities = _merge_cluster_entities(articles, idx_group)
            local_name = extract_primary_location(merged_entities)
            lat, lon = self.geocoder.geocode(local_name) if local_name else (None, None)

            dates: List[datetime] = []
            for a in cluster_arts:
                dt = a.data_publicacao or a.data_coleta or utcnow()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dates.append(dt)
            periodo_inicio = min(dates) if dates else utcnow()
            periodo_fim = max(dates) if dates else utcnow()

            titulo_provisorio = cluster_arts[0].titulo
            resumo_evento = " | ".join(
                f"[{a.veiculo}] {a.titulo}" for a in cluster_arts[:4]
            )

            if existing_event is None:
                event_obj = Event(
                    titulo_provisorio=titulo_provisorio[:512],
                    resumo=resumo_evento,
                    periodo_inicio=periodo_inicio,
                    periodo_fim=periodo_fim,
                    score_coesao=cohesion,
                    tema=tema,
                    local=local_name,
                    lat=lat,
                    lon=lon,
                    is_demo=False,
                )
                self.db.add(event_obj)
                self.db.commit()
                self.db.refresh(event_obj)
            else:
                event_obj = existing_event
                event_obj.titulo_provisorio = titulo_provisorio[:512]
                event_obj.resumo = resumo_evento
                event_obj.periodo_inicio = periodo_inicio
                event_obj.periodo_fim = periodo_fim
                event_obj.score_coesao = cohesion
                event_obj.tema = tema
                if local_name:
                    event_obj.local = local_name
                    event_obj.lat = lat
                    event_obj.lon = lon
                self.db.add(event_obj)
                self.db.commit()
                self.db.refresh(event_obj)

            for art in cluster_arts:
                art.event_id = event_obj.id
                self.db.add(art)
            self.db.commit()
            self.db.refresh(event_obj)
            persisted_events.append(event_obj)

        return persisted_events


def select_divergent_articles(
    db: Session,
    event_id: str,
    max_articles: int = 4,
) -> List[Article]:
    """
    Seleciona automaticamente de 2 a 4 matérias de um evento com maior potencial de
    divergência de enquadramento para enviar ao LLM.
    Prioriza matérias de categoria_editorial e posicao_editorial_declarada distintas
    combinadas com a maior distância semântica (menor similaridade cosseno no cluster).
    """
    articles = (
        db.query(Article)
        .filter(Article.event_id == event_id)
        .order_by(Article.data_publicacao.asc().nullsfirst(), Article.data_coleta.asc())
        .all()
    )
    if len(articles) <= 2:
        return articles

    sources_by_id: Dict[str, Source] = {
        s.id: s for s in db.query(Source).filter(Source.id.in_([a.source_id for a in articles])).all()
    }

    def _get_cat_and_pos(art: Article) -> Tuple[str, str]:
        src = sources_by_id.get(art.source_id)
        if src:
            return src.categoria_editorial, src.posicao_editorial_declarada
        meta = art.metadados or {}
        return (
            str(meta.get("categoria_editorial", "")),
            str(meta.get("posicao_editorial_declarada", "")),
        )

    def _get_vec(art: Article) -> Optional[np.ndarray]:
        if art.embedding_blob:
            return deserialize_embedding(art.embedding_blob)
        return None

    best_pair: Tuple[int, int] = (0, 1)
    best_pair_score = -1.0

    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            a_i, a_j = articles[i], articles[j]
            cat_i, pos_i = _get_cat_and_pos(a_i)
            cat_j, pos_j = _get_cat_and_pos(a_j)

            score = 0.0
            if a_i.source_id != a_j.source_id:
                score += 1.0
            if cat_i != cat_j:
                score += 2.0
            if pos_i != pos_j:
                score += 1.5

            vec_i, vec_j = _get_vec(a_i), _get_vec(a_j)
            if vec_i is not None and vec_j is not None:
                semantic_distance = 1.0 - cosine_similarity(vec_i, vec_j)
                score += semantic_distance
            if score > best_pair_score:
                best_pair_score = score
                best_pair = (i, j)

    selected_indices: List[int] = [best_pair[0], best_pair[1]]

    while len(selected_indices) < min(max_articles, len(articles)):
        best_next_idx: Optional[int] = None
        best_next_score = -1.0

        selected_cats = {_get_cat_and_pos(articles[idx])[0] for idx in selected_indices}
        selected_sources = {articles[idx].source_id for idx in selected_indices}

        for candidate_idx in range(len(articles)):
            if candidate_idx in selected_indices:
                continue
            cand = articles[candidate_idx]
            cand_cat, cand_pos = _get_cat_and_pos(cand)

            score = 0.0
            if cand.source_id not in selected_sources:
                score += 2.0
            if cand_cat not in selected_cats:
                score += 2.0

            cand_vec = _get_vec(cand)
            if cand_vec is not None:
                dists = []
                for sel_idx in selected_indices:
                    sel_vec = _get_vec(articles[sel_idx])
                    if sel_vec is not None:
                        dists.append(1.0 - cosine_similarity(cand_vec, sel_vec))
                if dists:
                    score += float(np.mean(dists))

            if score > best_next_score:
                best_next_score = score
                best_next_idx = candidate_idx

        if best_next_idx is None:
            break
        selected_indices.append(best_next_idx)

    return [articles[i] for i in selected_indices]
