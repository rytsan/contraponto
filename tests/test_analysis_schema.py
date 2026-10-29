import json
from typing import Any, Dict, List
import httpx
import jsonschema
import pytest
from pydantic import ValidationError
from app.schemas import BiasAnalysisLLMOutput, DossierSchema, EventConsolidationLLMOutput
from app.analysis.llm_client import (
    LlamaCppClient,
    load_json_schema,
    strip_code_fences,
    validate_against_json_schema,
)


def test_json_schemas_are_valid_draft_2020_12() -> None:
    bias_schema = load_json_schema("bias_analysis.json")
    event_schema = load_json_schema("event_analysis.json")

    assert bias_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert event_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    jsonschema.Draft202012Validator.check_schema(bias_schema)
    jsonschema.Draft202012Validator.check_schema(event_schema)


def test_bias_schema_accepts_valid_and_rejects_out_of_contract_payload() -> None:
    bias_schema = load_json_schema("bias_analysis.json")

    valid_payload: Dict[str, Any] = {
        "central_thesis": "A cobertura enquadra a greve a partir dos prejuízos ao setor comercial.",
        "valued_actors": ["FIESP", "Concessionárias privadas"],
        "devalued_actors": ["Sindicato dos Metroviários"],
        "ideological_vocabulary": ["prejuízos milionários", "equilíbrio econômico-financeiro"],
        "privileged_sources": ["Porta-vozes das concessionárias", "Analistas de mercado"],
        "likely_omissions": ["Condições de trabalho e defasagem salarial dos operadores"],
        "state_framing": "Estado acionado como garantidor da ordem contratual e aplicador de multas.",
        "market_framing": "Mercado tratado como referência técnica de eficiência.",
        "labor_framing": "Trabalho reduzido a fator de custo operacional.",
        "protest_framing": "Greve tratada como transtorno urbano.",
        "political_effect": "Deslegitimação do direito de greve perante os usuários.",
        "evidence_quotes": [
            {
                "quote": "o setor de comércio e serviços pode registrar perdas superiores a R$ 120 milhões",
                "context": "Estimativa patronal destacada no primeiro parágrafo.",
            }
        ],
    }

    validate_against_json_schema(valid_payload, bias_schema)
    parsed = BiasAnalysisLLMOutput.model_validate(valid_payload)
    assert len(parsed.evidence_quotes) == 1

    # O LLM nunca pode definir o campo `verified` na Etapa 3.1
    invalid_with_verified = json.loads(json.dumps(valid_payload))
    invalid_with_verified["evidence_quotes"][0]["verified"] = True
    with pytest.raises(jsonschema.ValidationError):
        validate_against_json_schema(invalid_with_verified, bias_schema)
    with pytest.raises(ValidationError):
        BiasAnalysisLLMOutput.model_validate(invalid_with_verified)

    # Rejeita payload com campo obrigatório ausente
    missing_field = json.loads(json.dumps(valid_payload))
    del missing_field["protest_framing"]
    with pytest.raises(jsonschema.ValidationError):
        validate_against_json_schema(missing_field, bias_schema)


def test_event_schema_enforces_strict_enums_and_accepts_sem_evidencia_suficiente() -> None:
    event_schema = load_json_schema("event_analysis.json")

    valid_dossier: Dict[str, Any] = {
        "event_id": "evt-001",
        "factual_anchor": "Trabalhadores metroviários realizaram paralisação em São Paulo em 28/10/2026.",
        "theme": "trabalho",
        "location": "São Paulo, Brasil",
        "coordinates": {"lat": -23.5505, "lon": -46.6333},
        "coverage_pairs": [
            {
                "article_id": "art-001",
                "source": "Veículo Demo A",
                "source_position": "Liberal fictícia",
                "url": "https://demo.local/1",
                "headline": "Manchete Demo 1",
                "central_thesis": "Tese central 1",
                "valued_actors": ["Empresas"],
                "devalued_actors": ["Sindicato"],
                "ideological_vocabulary": ["caos"],
                "privileged_sources": ["Federação patronal"],
                "likely_omissions": ["Salários"],
                "state_framing": "Garantidor de contratos",
                "market_framing": "Neutro",
                "labor_framing": "Custo",
                "protest_framing": "Transtorno",
                "political_effect": "Pressão contra greve",
                "evidence_quotes": [
                    {
                        "quote": "paralisação decretada pelo Sindicato dos Metroviários",
                        "context": "Abertura da matéria",
                        "verified": True,
                    }
                ],
            }
        ],
        "actors": [
            {
                "name": "Sindicato dos Metroviários",
                "type": "sindicato",
                "role": "Representação coletiva dos trabalhadores do metrô",
                "material_interest": "Recomposição salarial e barrar terceirizações",
                "relations": [
                    {
                        "target": "Concessionárias Privadas",
                        "relation": "resiste",
                        "evidence": "Paralisação contra cláusulas de terceirização",
                    }
                ],
            }
        ],
        "marxist_leninist_analysis": {
            "central_contradiction": "Conflito entre valorização do capital concessionário e reprodução da força de trabalho.",
            "class_relations": "Proletariado urbano do transporte versus burguesia de infraestrutura e finanças.",
            "property_and_power": "Concessões privadas apropriando-se de fundo público tarifário.",
            "role_of_state": "Aparato jurídico-policial mobilizado para impor multas ao sindicato.",
            "imperialism_or_dependency": "sem_evidencia_suficiente",
            "ideology_and_naturalization": "Naturalização do lucro contratual como interesse público.",
            "hegemony_and_silenced_voices": "Vozes patronais tratadas como técnicas; trabalhadores silenciados.",
            "forms_of_struggle": "Greve por tempo indeterminado e assembleia de base.",
            "immediate_demand": "Reajuste salarial e suspensão das terceirizações.",
            "strategic_perspective": "Reestatização sob controle público dos trabalhadores e usuários.",
            "limitations_and_uncertainty": ["Cobertura restrita ao primeiro dia de paralisação"],
        },
        "reader_questions": [
            "Quem se beneficia dos subsídios estatais às concessionárias privadas?"
        ],
        "data_visualizations": [
            {
                "title": "Fontes ouvidas por categoria",
                "type": "bar",
                "description": "Contagem de fontes citadas nas matérias",
                "labels": ["Patronais", "Sindicais"],
                "values": [3, 2],
                "source_article_ids": ["art-001"],
            }
        ],
        "confidence": 1.0,
    }

    validate_against_json_schema(valid_dossier, event_schema)
    dossier_obj = DossierSchema.model_validate(valid_dossier)
    assert dossier_obj.marxist_leninist_analysis.imperialism_or_dependency == "sem_evidencia_suficiente"

    # Rejeita enum inválido em actors[].type
    bad_actor = json.loads(json.dumps(valid_dossier))
    bad_actor["actors"][0]["type"] = "bilionario_invalido"
    with pytest.raises(jsonschema.ValidationError):
        validate_against_json_schema(bad_actor, event_schema)

    # Rejeita enum inválido em relations[].relation
    bad_rel = json.loads(json.dumps(valid_dossier))
    bad_rel["actors"][0]["relations"][0]["relation"] = "elogia_invalido"
    with pytest.raises(jsonschema.ValidationError):
        validate_against_json_schema(bad_rel, event_schema)

    # Rejeita enum inválido em data_visualizations[].type
    bad_viz = json.loads(json.dumps(valid_dossier))
    bad_viz["data_visualizations"][0]["type"] = "pie_chart_invalido"
    with pytest.raises(jsonschema.ValidationError):
        validate_against_json_schema(bad_viz, event_schema)


def test_llm_client_json_schema_fallback_code_fence_strip_and_retry() -> None:
    bias_schema = load_json_schema("bias_analysis.json")
    calls: List[Dict[str, Any]] = []

    valid_json_obj = {
        "central_thesis": "Tese corrigida na segunda tentativa",
        "valued_actors": ["Trabalhadores"],
        "devalued_actors": ["Concessionária"],
        "ideological_vocabulary": ["arrocho salarial"],
        "privileged_sources": ["Sindicato"],
        "likely_omissions": ["sem_evidencia_suficiente"],
        "state_framing": "Estado aplica multas contra grevistas",
        "market_framing": "Concessionárias buscam lucro",
        "labor_framing": "Defesa de condições dignas",
        "protest_framing": "Greve legítima decidida em assembleia",
        "political_effect": "Mobilização da categoria",
        "evidence_quotes": [
            {
                "quote": "Sindicato dos Metroviários e a Central Única dos Trabalhadores (CUT) decretaram greve",
                "context": "Abertura da matéria",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/props"):
            return httpx.Response(
                200,
                json={"default_generation_settings": {"model": "/models/Qwen2.5-14B-Instruct-Q4_K_M.gguf"}},
            )
        if url.endswith("/v1/chat/completions"):
            body = json.loads(request.content.decode("utf-8"))
            calls.append(body)
            rf_type = body.get("response_format", {}).get("type")

            # Simula servidor rejeitando json_schema para testar fallback json_object
            if rf_type == "json_schema":
                return httpx.Response(400, json={"error": "GBNF grammar unsupported construct"})

            # Primeira chamada json_object retorna JSON incompleto dentro de code fence
            if len([c for c in calls if c.get("response_format", {}).get("type") == "json_object"]) == 1:
                incomplete = {
                    "central_thesis": "Incompleto sem demais campos",
                    "evidence_quotes": valid_json_obj["evidence_quotes"],
                }
                fenced = f"```json\n{json.dumps(incomplete, ensure_ascii=False)}\n```"
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": fenced}}]},
                )

            # Segunda chamada json_object (retry) retorna JSON válido envolto em code fence
            fenced_ok = f"```json\n{json.dumps(valid_json_obj, ensure_ascii=False)}\n```"
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": fenced_ok}}]},
            )
        return httpx.Response(404)

    assert strip_code_fences("```json\n{\"a\": 1}\n```") == '{"a": 1}'

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        client = LlamaCppClient(
            base_url="http://127.0.0.1:8080",
            num_ctx=8192,
            max_retries=3,
            http_client=mock_http,
        )
        result, meta = client.generate_structured(
            prompt="Analise a matéria de teste",
            pydantic_model=BiasAnalysisLLMOutput,
            json_schema=bias_schema,
            schema_name="bias_analysis",
        )

    assert meta.used_fallback_json_object is True
    assert meta.attempts == 2
    assert meta.model_name == "Qwen2.5-14B-Instruct-Q4_K_M.gguf"
    assert result.central_thesis == "Tese corrigida na segunda tentativa"
