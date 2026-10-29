# Contraponto

> **"Toda notícia tem enquadramento. Análise sob ótica marxista-leninista."**

**Contraponto** é uma ferramenta de leitura crítica da mídia e agregador de notícias brasileiras e internacionais que coleta matérias de fontes distintas, agrupa coberturas sobre o mesmo acontecimento, expõe disputas de enquadramento e produz um **Dossiê de Contradição** interativo fundamentado no método marxista-leninista e no materialismo histórico.

---

## 1. O que é o Contraponto e a Premissa Editorial

Não existe notícia sem viés. Toda cobertura jornalística seleciona fatos, hierarquiza atores sociais, escolhe vocabulário, omite relações estruturais e materializa interesses de classe.

Por isso, o **Contraponto**:
- **Não busca uma "notícia neutra" nem um "meio-termo"** artificial entre veículos.
- Extrai apenas uma **âncora factual mínima** (o núcleo verificável comum entre as fontes) para agrupar matérias sobre o mesmo evento e evitar alucinação.
- Explicita os enquadramentos em disputa (Estado, mercado, trabalho, protesto/luta, atores valorizados e desvalorizados, fontes privilegiadas e omissões prováveis).
- Realiza uma análise política estrutural, material e de classe (propriedade, mais-valia, trabalho, papel do Estado, imperialismo, ideologia, hegemonia e formas de luta), sempre ancorada em evidências textuais verificadas programaticamente.
- Não faz condenações morais automatizadas de indivíduos nem classifica veículos de forma simplista como "confiáveis" ou "não confiáveis" — a origem de cada matéria é tratada como dado de posição editorial e social.

---

## 2. Instalação (Python, llama.cpp, Dependências e Qdrant)

### 2.1. Python e Dependências do Backend

Requer **Python 3.11+**.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Opcional: instalar modelo spaCy em português e inglês para extração de entidades
python -m spacy download pt_core_news_md
python -m spacy download en_core_web_sm
```

*(Nota: Caso os pacotes do spaCy não estejam instalados no ambiente, o extrator de entidades utiliza automaticamente o fallback de regex avançado e heurísticas léxicas sem interromper o pipeline).*

### 2.2. Instalação do `llama.cpp` (`llama-server`)

O Contraponto consome um servidor local `llama-server` compatível com a API HTTP da OpenAI. Você pode instalá-lo de três maneiras:

1. **Binário pré-compilado:** Baixe a release oficial correspondente ao seu sistema operacional/GPU em [github.com/ggerganov/llama.cpp/releases](https://github.com/ggerganov/llama.cpp/releases).
2. **Compilação com CMake:**
   ```bash
   git clone https://github.com/ggerganov/llama.cpp
   cd llama.cpp
   cmake -B build -DGGML_CUDA=ON   # omita -DGGML_CUDA=ON se for rodar apenas em CPU
   cmake --build build --config Release -j
   # O binário estará em ./build/bin/llama-server
   ```
3. **Via Docker Compose (profile `llm`):**
   ```bash
   docker compose --profile llm up -d
   ```

### 2.3. Quando o Qdrant é necessário?

O **SQLite é sempre a fonte da verdade** do Contraponto (incluindo os vetores de embedding serializados como BLOB numpy com registro do modelo). O sistema funciona **100% sem Qdrant** (`USE_QDRANT=false` por padrão).

O **Qdrant** é opcional e recomendado apenas se você desejar espelhar os vetores em um banco vetorial dedicado para consultas em grande volume de artigos:
```bash
docker compose --profile vector up -d
```

---

## 3. Requisitos de Hardware e Tamanho de Contexto (`-c`)

| Tamanho do Modelo (Quantização Q4_K_M) | RAM / VRAM Mínima Recomendada | Uso Indicado |
| :--- | :--- | :--- |
| **7B – 8B** (ex.: `Meta-Llama-3.1-8B-Instruct-Q4_K_M`) | **8 GB RAM** (ou 6 GB VRAM) | Execução rápida local em notebooks e desktops padrão |
| **14B** (ex.: `Qwen2.5-14B-Instruct-Q4_K_M`) | **16 GB+ RAM** (ou 12 GB VRAM) | Maior precisão na extração estruturada e síntese crítica |

### O que é o tamanho de contexto (`-c`) e por que o padrão é `8192`?

No `llama.cpp`, o tamanho da janela de contexto é alocado na inicialização do servidor através da flag `-c` (ex.: `-c 8192`), e não por requisição individual.
O valor padrão de **8192 tokens** permite enviar simultaneamente o prompt de sistema, o JSON Schema de saída estruturada e os textos/resumos de 2 a 4 matérias divergentes sem truncamento prematuro e sem estourar a memória em máquinas com 8 GB a 16 GB de RAM. O valor `LLAMA_CPP_NUM_CTX=8192` no `.env` deve refletir exatamente o valor passado ao `llama-server`, pois o cliente Python o utiliza para calcular o orçamento de texto por chamada.

---

## 4. Como Baixar um Modelo GGUF e Iniciar o `llama-server`

Instale a CLI do Hugging Face (`pip install huggingface_hub`) e baixe um modelo quantizado em formato GGUF:

```bash
mkdir -p models
huggingface-cli download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF \
  --include "*Q4_K_M*" \
  --local-dir ./models
```

Inicie o servidor `llama-server` na porta `8080` com contexto de `8192` tokens:

```bash
llama-server \
  -m ./models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  -c 8192 \
  -ngl 99 \
  --port 8080
```

*(Ajuste `-ngl 99` para descarregar camadas na GPU ou `-ngl 0` para execução exclusiva em CPU).*

---

## 5. Configuração do `.env`

Copie o arquivo `.env.example` para `.env`:

```bash
cp .env.example .env
```

Variáveis configuráveis:
- `DATABASE_URL`: URL do banco SQLite (padrão `sqlite:///./data/contraponto.db`).
- `LLAMA_CPP_BASE_URL`: URL do `llama-server` (padrão `http://127.0.0.1:8080`).
- `LLAMA_CPP_MODEL`: Identificador do modelo carregado.
- `LLAMA_CPP_NUM_CTX`: Tamanho do contexto configurado no `llama-server` (padrão `8192`).
- `USE_QDRANT`: `false` (padrão) ou `true` para espelhar vetores no Qdrant.
- `QDRANT_URL`: URL do Qdrant (padrão `http://localhost:6333`).
- `COLLECT_INTERVAL_MINUTES`: Intervalo da coleta periódica via APScheduler (padrão `60`).
- `REQUEST_TIMEOUT_SECONDS`: Timeout HTTP para coleta de RSS/páginas (padrão `20`).
- `RATE_LIMIT_SECONDS`: Pausa mínima entre requisições ao mesmo domínio (padrão `2`).
- `FRONTEND_ORIGIN`: Origem permitida no CORS para o frontend SvelteKit (padrão `http://localhost:5173`).
- `EMBEDDING_MODEL`: Modelo local `sentence-transformers` (padrão `paraphrase-multilingual-MiniLM-L12-v2`).
- `EMBEDDING_SIMILARITY_THRESHOLD`: Limiar de similaridade cosseno para clustering de eventos (padrão `0.82`).

---

## 6. Como Rodar Migrações, Coletor, API, Frontend e Testes

### 6.1. Migrações do Banco de Dados (Alembic)

```bash
alembic upgrade head
```

### 6.2. Iniciar a API (FastAPI)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API aplica/verifica a estrutura do banco e, caso o banco esteja vazio na listagem inicial de eventos, popula automaticamente o evento de demonstração 100% sintético (`tests/fixtures/demo_event.yaml`), permitindo testar o frontend imediatamente.

### 6.3. Executar o Coletor Manualmente

O APScheduler roda junto à API periodicamente, mas você também pode disparar a coleta e agrupamento via linha de comando:

```bash
python -m app.collectors.rss_collector
```

### 6.4. Iniciar o Frontend (SvelteKit)

```bash
cd frontend
npm install
npm run dev
```

Acesse `http://localhost:5173`.

### 6.5. Executar a Suíte de Testes

Nenhum teste acessa a internet ou exige `llama-server`/`Qdrant` reais:

```bash
pytest -q
```

---

## 7. Como Validar e Adicionar Fontes RSS (`sources_loader --check`)

As fontes ficam definidas em `data/sources.yaml`. Para validar todas as fontes configuradas (checando estrutura e acessibilidade HTTP dos feeds RSS/Atom):

```bash
python -m app.collectors.sources_loader --check
```

Para adicionar uma nova fonte:
1. Edite `data/sources.yaml` (sem necessidade de alterar código) **ou** envie um `POST /sources` para a API, que persistirá a nova fonte simultaneamente no banco SQLite e no arquivo `data/sources.yaml`.

---

## 8. Como Interpretar o Dossiê de Contradição e os Selos de Verificação

Cada acontecimento é apresentado em **6 cenas horizontais interativas**:
1. **[ 01 FATO ]**: Declaração editorial explícita, título do evento e **âncora factual mínima** (núcleo comum verificável, que não se confunde com neutralidade).
2. **[ 02 DISPUTA ]**: Comparação lado a lado de coberturas com enquadramentos distintos (tese central, atores valorizados/desvalorizados, vocabulário ideológico destacável por hover ou toque, omissões prováveis e trechos citados).
3. **[ 03 MAPA DE PODER ]**: Alternância entre Mapa Geográfico (Leaflet/OpenStreetMap, exibido apenas quando há coordenadas reais verificadas via Nominatim) e Grafo de Atores (Cytoscape.js, exibindo relações de controle, financiamento, citação, enquadramento, resistência, regulação, repressão, lucro e organização).
4. **[ 04 DADOS ]**: Gráficos em Chart.js gerados exclusivamente a partir de métricas reais e auditáveis vinculadas às matérias do evento.
5. **[ 05 ANÁLISE ML ]**: Cartões sequenciais de análise marxista-leninista (contradição central, luta de classes, propriedade e poder, papel do Estado, imperialismo/dependência, ideologia, hegemonia, formas de luta, demanda imediata, perspectiva estratégica) e perguntas críticas ao leitor.
6. **[ 06 FONTES ]**: Registro completo de auditoria das matérias, autores, URLs, método de coleta (`rss_full`, `rss_summary`, `trafilatura`), modelo LLM utilizado, contexto e botões de exportação.

### Selos `Verificado` vs. `Não Verificado` e Nível de Confiança
- Toda citação extraída pelo LLM (`evidence_quotes`) passa pelo verificador programático (`evidence_verifier.py`), que compara o trecho contra o texto original armazenado da matéria usando `rapidfuzz.fuzz.partial_ratio >= 92`.
- **`Verificado` (`verified: true`)**: O trecho existe literalmente ou com correspondência exata normalizada no texto-fonte da matéria.
- **`Não verificado` (`verified: false`)**: O trecho não atingiu o limiar de verificação textual (possível paráfrase ou alucinação do modelo). Por padrão, a interface exibe apenas trechos verificados, oferecendo um botão manual para inspecionar os não verificados.
- **Confiança recalculada**: O índice `confidence` do dossiê **nunca** confia na autoavaliação do LLM — é calculado estritamente pelo código como `trechos_verificados / total_de_trechos`.
- **`sem_evidencia_suficiente`**: Quando as matérias não trazem base material para responder a determinado eixo, o sistema preserva o valor `"sem_evidencia_suficiente"` e renderiza um estado vazio honesto.

---

## 9. Como Exportar em Markdown, JSON e PDF

Na **Cena 06 — Fontes** (ou diretamente pela API):
- **Markdown:** `GET /events/{id}/export?format=markdown` — baixa o dossiê completo formatado em Markdown com todas as citações e metadados de auditoria.
- **JSON:** `GET /events/{id}/export?format=json` — baixa o contrato estruturado completo do dossiê validado pelo schema.
- **PDF:** Clique em **"Imprimir / Exportar PDF"** na interface (aciona `window.print()` com folha de estilo `@media print` dedicada que expande todas as 6 cenas em layout editorial de relatório).

---

## 10. Limites do Sistema

- **O LLM pode errar:** Modelos locais de linguagem estão sujeitos a simplificações, omissões e erros de interpretação sintática, mesmo com gramática restrita (GBNF) e verificação textual via `rapidfuzz`.
- **A análise é interpretativa:** O Dossiê de Contradição é um instrumento auxiliar de crítica de mídia sob ótica marxista-leninista, e **não substitui a leitura integral das fontes originais**.
- **Limites da janela de coleta:** Artigos protegidos por paywall severo terão apenas título e resumo do RSS analisados (`metodo_coleta="rss_summary"`), o que limita a profundidade das citações disponíveis.
- **Não substitui a práxis:** Esta ferramenta apoia o estudo e a leitura crítica do noticiário, mas não substitui a pesquisa histórica rigorosa, o trabalho de base, o jornalismo investigativo nem a organização política real.
