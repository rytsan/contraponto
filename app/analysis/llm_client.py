import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
import httpx
import jsonschema
from pydantic import BaseModel, ValidationError
from app.config import settings

TModel = TypeVar("TModel", bound=BaseModel)

SCHEMAS_DIR = Path(__file__).parent / "schemas"
PROMPTS_DIR = Path(__file__).parent / "prompts"

CODE_FENCE_REGEX = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass
class LLMCallMetadata:
    """Metadados de execução de uma chamada ao llama-server."""

    executed_at: datetime
    model_name: str
    num_ctx: int
    execution_time_ms: int
    used_fallback_json_object: bool
    attempts: int


def strip_code_fences(raw_text: str) -> str:
    """Remove blocos de código markdown (```json ... ```) ao redor do JSON."""
    if not raw_text:
        return ""
    cleaned = raw_text.strip()
    match = CODE_FENCE_REGEX.match(cleaned)
    if match:
        return match.group(1).strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate

    return cleaned


def load_json_schema(schema_filename: str) -> Dict[str, Any]:
    """Carrega um arquivo JSON Schema Draft 2020-12 do diretório app/analysis/schemas."""
    path = SCHEMAS_DIR / schema_filename
    return json.loads(path.read_text(encoding="utf-8"))


def load_prompt_template(prompt_filename: str) -> str:
    """Carrega um template de prompt do diretório app/analysis/prompts."""
    path = PROMPTS_DIR / prompt_filename
    return path.read_text(encoding="utf-8")


def validate_against_json_schema(
    instance: Dict[str, Any],
    schema: Dict[str, Any],
    root_schema: Optional[Dict[str, Any]] = None,
) -> None:
    """Valida um dicionário contra um JSON Schema Draft 2020-12 real."""
    if root_schema is not None and "$defs" in root_schema and "$defs" not in schema:
        schema = {**schema, "$defs": root_schema["$defs"]}
    validator_cls = jsonschema.Draft202012Validator
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        messages = [
            f"campo '{'.'.join(str(p) for p in err.path) or '<raiz>'}': {err.message}"
            for err in errors
        ]
        raise jsonschema.ValidationError("; ".join(messages))


class LlamaCppClient:
    """
    Cliente HTTP para llama-server (compatível com OpenAI) com:
    - response_format json_schema + fallback automático para json_object
    - cálculo de orçamento de contexto baseado em LLAMA_CPP_NUM_CTX
    - strip de code fences
    - timeout de 300s
    - retry de até 3 tentativas preservando evidências já extraídas
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        num_ctx: Optional[int] = None,
        timeout_seconds: float = 300.0,
        max_retries: int = 3,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = (base_url or settings.LLAMA_CPP_BASE_URL).rstrip("/")
        self.configured_model = model_name or settings.LLAMA_CPP_MODEL
        self.num_ctx = num_ctx or settings.LLAMA_CPP_NUM_CTX
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, min(3, max_retries))
        self.http_client = http_client

    def compute_text_budget_chars(
        self,
        system_and_template_chars: int,
        reserved_output_tokens: int = 1800,
    ) -> int:
        """
        Calcula o orçamento máximo de caracteres de texto para a requisição
        a partir de LLAMA_CPP_NUM_CTX (estimativa conservadora: ~3.2 caracteres/token).
        """
        available_input_tokens = max(512, self.num_ctx - reserved_output_tokens)
        total_input_chars = int(available_input_tokens * 3.2)
        remaining_chars = max(800, total_input_chars - system_and_template_chars)
        return remaining_chars

    def get_server_loaded_model(self, client: Optional[httpx.Client] = None) -> str:
        """Consulta GET /props no llama-server para identificar o modelo carregado ou retorna LLAMA_CPP_MODEL."""
        own_client = client is None and self.http_client is None
        http_c = client or self.http_client or httpx.Client(timeout=5.0)
        try:
            resp = http_c.get(f"{self.base_url}/props")
            if resp.status_code == 200:
                data = resp.json()
                model_path = (
                    data.get("default_generation_settings", {}).get("model")
                    or data.get("model_alias")
                    or data.get("model_path")
                )
                if model_path and isinstance(model_path, str):
                    return Path(model_path).name
        except Exception:
            pass
        finally:
            if own_client:
                http_c.close()
        return self.configured_model

    def check_health(self, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
        """Verifica GET /health e GET /props do llama-server."""
        own_client = client is None and self.http_client is None
        http_c = client or self.http_client or httpx.Client(timeout=5.0)
        try:
            resp = http_c.get(f"{self.base_url}/health")
            loaded_model = self.get_server_loaded_model(client=http_c)
            if resp.status_code == 200:
                payload = resp.json() if resp.content else {}
                return {
                    "reachable": True,
                    "status": payload.get("status", "ok"),
                    "model": loaded_model,
                    "num_ctx": self.num_ctx,
                }
            return {
                "reachable": False,
                "status": f"http_{resp.status_code}",
                "model": loaded_model,
                "num_ctx": self.num_ctx,
            }
        except Exception as exc:
            return {
                "reachable": False,
                "status": "offline",
                "model": self.configured_model,
                "num_ctx": self.num_ctx,
                "error": str(exc),
            }
        finally:
            if own_client:
                http_c.close()

    def _post_chat_completion(
        self,
        http_c: httpx.Client,
        messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        schema_name: str,
    ) -> Tuple[str, bool]:
        """
        Envia POST /v1/chat/completions com response_format type='json_schema'.
        Se o servidor rejeitar o schema, faz fallback automático para type='json_object'.
        Retorna (conteudo_texto, usou_fallback).
        """
        endpoint = f"{self.base_url}/v1/chat/completions"
        payload_schema_mode: Dict[str, Any] = {
            "model": self.configured_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }

        resp = http_c.post(endpoint, json=payload_schema_mode)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return str(content), False

        # Fallback obrigatório: servidor rejeitou json_schema (ex.: 400/422 na conversão GBNF)
        payload_object_mode: Dict[str, Any] = {
            "model": self.configured_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        resp_fallback = http_c.post(endpoint, json=payload_object_mode)
        resp_fallback.raise_for_status()
        data_fb = resp_fallback.json()
        content_fb = data_fb["choices"][0]["message"]["content"]
        return str(content_fb), True

    def generate_structured(
        self,
        prompt: str,
        pydantic_model: Type[TModel],
        json_schema: Dict[str, Any],
        schema_name: str = "structured_output",
        root_schema: Optional[Dict[str, Any]] = None,
        preserved_evidence_quotes: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[TModel, LLMCallMetadata]:
        """
        Executa chamada ao LLM validando a resposta com JSON Schema Draft 2020-12 e Pydantic v2.
        Em caso de erro de validação, realiza até 3 tentativas solicitando a correção
        apenas dos campos inválidos e mantendo as evidências já extraídas.
        """
        start_ns = time.perf_counter_ns()
        own_client = self.http_client is None
        http_c = self.http_client or httpx.Client(timeout=self.timeout_seconds)

        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Você responde exclusivamente com um objeto JSON válido em português brasileiro, "
                    "obedecendo estritamente ao JSON Schema fornecido, sem blocos markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        extracted_quotes: List[Dict[str, str]] = list(preserved_evidence_quotes or [])
        used_fallback = False
        last_error: Optional[Exception] = None

        try:
            loaded_model = self.get_server_loaded_model(client=http_c)

            for attempt in range(1, self.max_retries + 1):
                raw_response, fb = self._post_chat_completion(
                    http_c=http_c,
                    messages=messages,
                    json_schema=json_schema,
                    schema_name=schema_name,
                )
                used_fallback = used_fallback or fb
                cleaned_json_str = strip_code_fences(raw_response)

                try:
                    parsed_dict = json.loads(cleaned_json_str)
                    if not isinstance(parsed_dict, dict):
                        raise ValueError("A resposta JSON deve ser um objeto na raiz.")

                    # Preserva evidências já extraídas caso o modelo as tenha retornado antes do erro
                    if isinstance(parsed_dict.get("evidence_quotes"), list):
                        valid_qs = [
                            q for q in parsed_dict["evidence_quotes"]
                            if isinstance(q, dict) and q.get("quote") and q.get("context")
                        ]
                        if valid_qs:
                            extracted_quotes = valid_qs

                    validate_against_json_schema(
                        instance=parsed_dict,
                        schema=json_schema,
                        root_schema=root_schema,
                    )
                    validated_obj = pydantic_model.model_validate(parsed_dict)

                    elapsed_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
                    meta = LLMCallMetadata(
                        executed_at=datetime.now(timezone.utc),
                        model_name=loaded_model,
                        num_ctx=self.num_ctx,
                        execution_time_ms=max(1, elapsed_ms),
                        used_fallback_json_object=used_fallback,
                        attempts=attempt,
                    )
                    return validated_obj, meta

                except (json.JSONDecodeError, jsonschema.ValidationError, ValidationError, ValueError) as err:
                    last_error = err
                    if attempt >= self.max_retries:
                        break

                    if isinstance(err, ValidationError):
                        error_details = json.dumps(err.errors(), ensure_ascii=False)
                    else:
                        error_details = str(err)

                    preserved_note = ""
                    if extracted_quotes:
                        preserved_note = (
                            "\n\nMANTENHA estas evidências textuais já extraídas em `evidence_quotes`:\n"
                            + json.dumps(extracted_quotes, ensure_ascii=False)
                        )

                    correction_prompt = (
                        "Sua resposta anterior falhou na validação do schema.\n"
                        f"Erros detectados: {error_details}\n"
                        "Corrija APENAS os campos inválidos ou faltantes e retorne o JSON completo e válido."
                        f"{preserved_note}"
                    )
                    messages.append({"role": "assistant", "content": cleaned_json_str or "{}"})
                    messages.append({"role": "user", "content": correction_prompt})

            raise ValueError(
                f"Falha na validação estruturada após {self.max_retries} tentativas: {last_error}"
            )
        finally:
            if own_client:
                http_c.close()
