from datetime import datetime, timedelta, timezone
import numpy as np
from sqlalchemy.orm import Session
from app.models import Article, Source, VALID_THEMES
from app.clustering.embedder import ArticleEmbedder, deserialize_embedding, l2_normalize
from app.clustering.entity_extractor import (
    entity_jaccard_similarity,
    extract_entities,
    normalize_entity_name,
)
from app.clustering.event_clusterer import (
    EventClusterer,
    NominatimGeocoderCache,
    select_divergent_articles,
)


def test_entity_extractor_normalizes_aliases_and_computes_jaccard() -> None:
    assert normalize_entity_name("Lula") == "Luiz Inácio Lula da Silva"
    assert normalize_entity_name("Lula da Silva") == "Luiz Inácio Lula da Silva"
    assert normalize_entity_name("CUT") == "Central Única dos Trabalhadores"
    assert normalize_entity_name("MST") == "Movimento dos Trabalhadores Rurais Sem Terra"

    ent_a = extract_entities(
        "Em São Paulo, Lula e a CUT discutiram a PEC 8/2025 com o Sindicato dos Metroviários."
    )
    ent_b = extract_entities(
        "Luiz Inácio Lula da Silva recebeu a Central Única dos Trabalhadores em São Paulo sobre a PEC 8/2025."
    )
    assert "Luiz Inácio Lula da Silva" in ent_a["pessoas"]
    assert "Luiz Inácio Lula da Silva" in ent_b["pessoas"]
    assert "Central Única dos Trabalhadores" in ent_a["sindicatos"]
    assert "São Paulo" in ent_a["lugares"]

    jaccard = entity_jaccard_similarity(ent_a, ent_b)
    assert jaccard >= 0.75


def test_cluster_two_articles_same_fact_and_separate_different_fact(
    db_session: Session,
    fake_embedder: ArticleEmbedder,
    tmp_path,
) -> None:
    src_liberal = Source(
        id="folha_demo",
        nome="Diário Liberal Demo",
        url_rss="https://liberal.demo.local/rss",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal de mercado",
        descricao="Fonte liberal fictícia",
    )
    src_popular = Source(
        id="popular_demo",
        nome="Jornal Sindical Demo",
        url_rss="https://popular.demo.local/rss",
        categoria_editorial="imprensa_popular_sindical_esquerda",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Sindical e classista",
        descricao="Fonte popular fictícia",
    )
    db_session.add_all([src_liberal, src_popular])
    db_session.commit()

    base_time = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

    art1 = Article(
        id="art-greve-1",
        source_id=src_liberal.id,
        titulo="Paralisação do metrô em São Paulo afeta comércio e gera reação da FIESP",
        url_canonica="https://liberal.demo.local/greve-sp-1",
        guid="guid-greve-1",
        veiculo=src_liberal.nome,
        data_publicacao=base_time,
        data_coleta=base_time,
        texto_limpo=(
            "A greve decretada pelo Sindicato dos Metroviários e pela CUT em São Paulo "
            "afetou o comércio na manhã desta quarta-feira e provocou nota da FIESP."
        ),
        resumo="Greve do metrô em SP afeta comércio.",
        idioma="pt",
        hash_conteudo="hash-greve-1",
        metodo_coleta="rss_full",
        metadados={"categoria_editorial": src_liberal.categoria_editorial},
    )
    art2 = Article(
        id="art-greve-2",
        source_id=src_popular.id,
        titulo="Trabalhadores metroviários de São Paulo entram em greve contra terceirização",
        url_canonica="https://popular.demo.local/greve-sp-2",
        guid="guid-greve-2",
        veiculo=src_popular.nome,
        data_publicacao=base_time + timedelta(hours=2),
        data_coleta=base_time + timedelta(hours=2),
        texto_limpo=(
            "O Sindicato dos Metroviários e a Central Única dos Trabalhadores paralisaram "
            "as linhas em São Paulo contra a precarização e as terceirizações."
        ),
        resumo="Metroviários cruzam os braços em SP.",
        idioma="pt",
        hash_conteudo="hash-greve-2",
        metodo_coleta="rss_full",
        metadados={"categoria_editorial": src_popular.categoria_editorial},
    )
    art3_outro_evento = Article(
        id="art-terra-3",
        source_id=src_popular.id,
        titulo="MST realiza encontro nacional por reforma agrária e agroecologia em Brasília",
        url_canonica="https://popular.demo.local/mst-brasilia-3",
        guid="guid-terra-3",
        veiculo=src_popular.nome,
        data_publicacao=base_time + timedelta(hours=3),
        data_coleta=base_time + timedelta(hours=3),
        texto_limpo=(
            "O Movimento dos Trabalhadores Rurais Sem Terra (MST) cobrou do INCRA em Brasília "
            "a desapropriação de terras improdutivas para reforma agrária popular."
        ),
        resumo="MST cobra reforma agrária em Brasília.",
        idioma="pt",
        hash_conteudo="hash-terra-3",
        metodo_coleta="rss_full",
        metadados={"categoria_editorial": src_popular.categoria_editorial},
    )

    db_session.add_all([art1, art2, art3_outro_evento])
    db_session.commit()

    fake_geocoder = NominatimGeocoderCache(
        cache_path=str(tmp_path / "geocode.json"),
        enabled=True,
        geocode_fn=lambda loc: (-23.5505, -46.6333) if "São Paulo" in loc else (-15.7939, -47.8828),
    )

    clusterer = EventClusterer(
        db=db_session,
        embedder=fake_embedder,
        geocoder=fake_geocoder,
        similarity_threshold=0.82,
    )
    events = clusterer.cluster_articles([art1, art2, art3_outro_evento])

    assert len(events) == 2

    db_session.refresh(art1)
    db_session.refresh(art2)
    db_session.refresh(art3_outro_evento)

    assert art1.event_id is not None
    assert art1.event_id == art2.event_id
    assert art3_outro_evento.event_id != art1.event_id

    assert art1.embedding_blob is not None
    assert art1.embedding_model == "fake-multilingual-minilm-test"
    vec1 = deserialize_embedding(art1.embedding_blob)
    assert abs(float(np.linalg.norm(vec1)) - 1.0) < 1e-5

    strike_event = next(e for e in events if e.id == art1.event_id)
    assert strike_event.tema in VALID_THEMES
    assert strike_event.tema == "trabalho"
    assert 0.8 <= strike_event.score_coesao <= 1.0
    assert strike_event.local == "São Paulo, Brasil"
    assert strike_event.lat == -23.5505
    assert strike_event.lon == -46.6333

    divergent = select_divergent_articles(db_session, strike_event.id, max_articles=4)
    assert len(divergent) == 2
    assert {a.source_id for a in divergent} == {"folha_demo", "popular_demo"}


def test_entity_overlap_merges_clusters_up_to_005_below_threshold(
    db_session: Session,
    tmp_path,
) -> None:
    """
    Testa a regra 2.3: sobreposição de entidades (Jaccard >= 0.3) une clusters
    com similaridade cosseno até 0.05 abaixo do limiar (ex.: 0.79 com limiar 0.82).
    """
    source = Source(
        id="src_test",
        nome="Fonte Teste",
        url_rss="https://teste.demo.local/rss",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Fictícia",
        descricao="Teste",
    )
    db_session.add(source)
    db_session.commit()

    def _encode_borderline(text: str) -> np.ndarray:
        if "artigo_a" in text:
            return l2_normalize(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
        # cos(theta) = 0.79 (abaixo de 0.82, mas >= 0.82 - 0.05 = 0.77)
        return l2_normalize(np.array([0.79, 0.6131, 0.0, 0.0], dtype=np.float32))

    embedder = ArticleEmbedder(
        model_name="borderline-test",
        encode_fn=_encode_borderline,
        use_qdrant=False,
    )

    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        id="border-1",
        source_id=source.id,
        titulo="artigo_a: Lula e CUT debatem Petrobras em Brasília",
        url_canonica="https://teste.demo.local/1",
        guid="b-1",
        veiculo="Fonte Teste",
        data_publicacao=now,
        data_coleta=now,
        texto_limpo="Luiz Inácio Lula da Silva reuniu a CUT e a Petrobras em Brasília.",
        resumo="Resumo 1",
        idioma="pt",
        hash_conteudo="hb-1",
        metodo_coleta="rss_summary",
        metadados={},
    )
    a2 = Article(
        id="border-2",
        source_id=source.id,
        titulo="artigo_b: Lula da Silva recebe Central Única dos Trabalhadores e Petrobras em Brasília",
        url_canonica="https://teste.demo.local/2",
        guid="b-2",
        veiculo="Fonte Teste",
        data_publicacao=now + timedelta(hours=1),
        data_coleta=now + timedelta(hours=1),
        texto_limpo="O presidente Lula e a Central Única dos Trabalhadores discutiram investimentos da Petrobras em Brasília.",
        resumo="Resumo 2",
        idioma="pt",
        hash_conteudo="hb-2",
        metodo_coleta="rss_summary",
        metadados={},
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    clusterer = EventClusterer(
        db=db_session,
        embedder=embedder,
        geocoder=NominatimGeocoderCache(cache_path=str(tmp_path / "geo.json"), enabled=False),
        similarity_threshold=0.82,
    )
    events = clusterer.cluster_articles([a1, a2])
    assert len(events) == 1
    assert events[0].lat is None
    assert events[0].lon is None
