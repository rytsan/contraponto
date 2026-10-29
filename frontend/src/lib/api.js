const DEFAULT_API_BASE = 'http://localhost:8000';

export function getApiBase() {
  if (typeof window !== 'undefined' && window.__CONTRAPONTO_API_URL__) {
    return window.__CONTRAPONTO_API_URL__;
  }
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE;
}

export const DEMO_FALLBACK_DOSSIER = {
  event_id: 'demo-event-transporte-sp-2026',
  title: '[DEMO] Greve unificada no transporte metropolitano expõe conflito entre tarifas, subsídios às concessionárias e escala de trabalho',
  is_demo: true,
  factual_anchor:
    'Em 28 de outubro de 2026, trabalhadores do transporte metropolitano de São Paulo iniciaram greve unificada. O movimento motivou decisão liminar do Tribunal Regional do Trabalho exigindo 85% da frota em operação sob multa diária de R$ 600 mil e convocação de audiência de conciliação entre o sindicato (SUTTD) e a concessionária (Consórcio ViaPrivada Demo).',
  theme: 'trabalho',
  location: 'São Paulo, Brasil',
  coordinates: {
    lat: -23.5505,
    lon: -46.6333
  },
  coverage_pairs: [
    {
      article_id: 'demo-art-001',
      source: 'Veículo Demo A — Diário Mercantil (Posição Editorial: Fictícia Liberal)',
      source_position: 'Fictícia — Liberalismo econômico e defesa de concessões privadas (DEMO)',
      url: 'https://demo-a.contraponto.local/economia/paralisacao-transporte-prejuizo-comercio',
      headline: '[DEMO] Paralisação no transporte paralisa corredores financeiros e gera prejuízo estimado em R$ 180 milhões ao comércio',
      central_thesis:
        'A greve é enquadrada como perturbação econômica e ameaça à segurança jurídica dos contratos de concessão privada, justificando repressão judicial e policial.',
      valued_actors: [
        'Federação Empresarial Metropolitana Fictícia (FEMF)',
        'Consórcio ViaPrivada Demo',
        'Analistas de investimentos',
        'Procuradoria estadual'
      ],
      devalued_actors: [
        'Operadores do sistema metropolitano de transporte',
        'Sindicato da categoria'
      ],
      ideological_vocabulary: [
        'congestionamentos recordes',
        'equilíbrio econômico-financeiro',
        'pressão grevista',
        'insegurança jurídica'
      ],
      privileged_sources: [
        'Federação Empresarial Metropolitana Fictícia (FEMF)',
        'Diretores do Consórcio ViaPrivada Demo',
        'Analistas de investimentos'
      ],
      likely_omissions: [
        'Volume de subsídios públicos recebidos pela concessionária privada',
        'Remessa de dividendos aos acionistas do consórcio',
        'Condições de trabalho na escala 6x1 e riscos de segurança operacional por terceirização'
      ],
      state_framing:
        'Estado aparece como garantidor legítimo dos contratos privados e aparato repressor acionado para aplicar multas e enviar tropa de choque.',
      market_framing:
        'O faturamento do comércio e a atratividade de leilões de privatização são tratados como interesse geral e técnico.',
      labor_framing:
        'A reivindicação de redução de jornada é tratada como violação contratual e custo incompatível.',
      protest_framing:
        'A greve é reduzida a transtorno viário e prejuízo financeiro, sem expor suas causas materiais.',
      political_effect:
        'Naturaliza a privatização do transporte e mobiliza a opinião pública contra os trabalhadores em greve.',
      evidence_quotes: [
        {
          quote:
            'o varejo e o setor de serviços deixam de faturar cerca de R$ 180 milhões por dia de interrupção das linhas concedidas',
          context:
            'Destaque inicial atribuído à federação patronal para quantificar a greve apenas pelo prejuízo mercantil.',
          verified: true
        },
        {
          quote:
            'ceder à pressão grevista criaria insegurança jurídica para os próximos leilões de privatização da malha ferroviária urbana',
          context:
            'Uso de analistas financeiros para subordinar direitos trabalhistas à agenda de privatizações.',
          verified: true
        },
        {
          quote:
            'O sindicato admitiu em nota reservada que a paralisação ignora a capacidade orçamentária do estado',
          context:
            'Exemplo sintético de citação não verificada no texto original (para demonstração do filtro de verificação).',
          verified: false
        }
      ]
    },
    {
      article_id: 'demo-art-002',
      source: 'Veículo Demo B — Tribuna Operária (Posição Editorial: Fictícia Sindical)',
      source_position: 'Fictícia — Imprensa sindical classista e popular (DEMO)',
      url: 'https://demo-b.contraponto.local/lutas/trabalhadores-transporte-greve-contra-terceirizacao',
      headline: '[DEMO] Trabalhadores do transporte cruzam os braços contra terceirização, escala exaustiva e remessa recorde de lucros',
      central_thesis:
        'A greve é apresentada como resposta coletiva à superexploração na escala 6x1, à precarização por terceirizações e à transferência de fundo público para lucros privados.',
      valued_actors: [
        'Trabalhadores (maquinistas, motoristas e técnicos de manutenção)',
        'Sindicato Unificado dos Trabalhadores em Transporte Demo (SUTTD)',
        'Comitês de usuários dos bairros periféricos',
        'Movimento Popular pelo Transporte Público Demo'
      ],
      devalued_actors: ['Consórcio ViaPrivada Demo', 'Fundos acionistas'],
      ideological_vocabulary: [
        'jornadas exaustivas',
        'contratos terceirizados precarizados',
        'subsídios diretos',
        'controle público e social'
      ],
      privileged_sources: [
        'Assembleia geral dos trabalhadores',
        'Departamento econômico do SUTTD',
        'Movimento Popular pelo Transporte Público Demo'
      ],
      likely_omissions: [
        'Argumentos jurídicos detalhados da concessionária sobre cláusulas contratuais'
      ],
      state_framing:
        'O Estado é criticado por transferir R$ 2,4 bilhões em subsídios públicos ao consórcio privado enquanto reprime a greve.',
      market_framing:
        'A concessão privada é exposta como mecanismo de extração de dividendos às custas do fundo público e da manutenção.',
      labor_framing:
        'Os trabalhadores aparecem como sujeitos políticos e produtores diretos do serviço essencial.',
      protest_framing:
        'A greve e a aliança com movimentos de bairros periféricos aparecem como instrumento legítimo de defesa da vida e do serviço público.',
      political_effect:
        'Articula a pauta salarial e de jornada dos operários com o interesse da população usuária por tarifa zero e reestatização.',
      evidence_quotes: [
        {
          quote:
            'o Consórcio ViaPrivada Demo recebeu R$ 2,4 bilhões em subsídios diretos do orçamento público estadual no último ano e distribuiu R$ 790 milhões em dividendos',
          context:
            'Evidência material da apropriação privada do fundo público destacada pelo sindicato.',
          verified: true
        },
        {
          quote:
            'exigindo congelamento da tarifa, reversão das privatizações e controle público e social sobre as planilhas de custos do sistema',
          context:
            'Reivindicação conjunta entre trabalhadores do transporte e movimentos populares periféricos.',
          verified: true
        }
      ]
    },
    {
      article_id: 'demo-art-003',
      source: 'Veículo Demo C — Boletim Oficial (Posição Editorial: Fictícia Institucional)',
      source_position: 'Fictícia — Comunicação institucional de órgãos públicos (DEMO)',
      url: 'https://demo-c.contraponto.local/institucional/secretaria-mesa-conciliacao-contingencia',
      headline: '[DEMO] Secretaria de Transportes instala mesa de conciliação e determina operação de contingência nas linhas metropolitanas',
      central_thesis:
        'O relato adota linguagem burocrática de gestão de crise, apresentando o Estado como árbitro técnico acima do conflito entre capital e trabalho.',
      valued_actors: [
        'Secretaria Estadual de Transportes Metropolitanos Demo',
        'Tribunal Regional do Trabalho',
        'Ministério Público do Trabalho'
      ],
      devalued_actors: [],
      ideological_vocabulary: [
        'Plano de Contingência Operacional',
        'mitigar os impactos',
        'audiência de conciliação'
      ],
      privileged_sources: [
        'Nota oficial da Secretaria Estadual de Transportes',
        'Decisão cautelar do Tribunal Regional do Trabalho'
      ],
      likely_omissions: [
        'Causas trabalhistas da greve (escala 6x1 e terceirização)',
        'Dados financeiros sobre subsídios e lucros do consórcio'
      ],
      state_framing:
        'Estado retratado como mediador neutro e garante técnico da circulação urbana.',
      market_framing: 'sem_evidencia_suficiente',
      labor_framing:
        'Trabalhadores citados apenas como objeto de fiscalização do percentual mínimo de frota.',
      protest_framing:
        'A greve é tratada como evento operacional a ser gerenciado administrativamente.',
      political_effect:
        'Oculta a natureza de classe da liminar judicial sob a aparência de neutralidade administrativa.',
      evidence_quotes: [
        {
          quote:
            'fiscais da agência reguladora monitoram nas estações o cumprimento da decisão cautelar do Tribunal Regional do Trabalho, que fixou frota mínima de 85%',
          context: 'Enquadramento administrativo da restrição ao direito de greve.',
          verified: true
        }
      ]
    }
  ],
  actors: [
    {
      name: 'Sindicato Unificado dos Trabalhadores em Transporte Demo (SUTTD)',
      type: 'sindicato',
      role: 'Organização sindical dos maquinistas, motoristas e técnicos de manutenção',
      material_interest:
        'Redução da jornada sem corte salarial, fim da escala 6x1, reversão das terceirizações e recomposição salarial',
      relations: [
        {
          target: 'Consórcio ViaPrivada Demo',
          relation: 'resiste',
          evidence: 'Greve unificada contra demissões, terceirização e arrocho salarial'
        },
        {
          target: 'Trabalhadores do Transporte Metropolitano',
          relation: 'organiza',
          evidence: 'Assembleia geral com mais de 4 mil operários aprovou a paralisação'
        }
      ]
    },
    {
      name: 'Trabalhadores do Transporte Metropolitano',
      type: 'trabalhador',
      role: 'Força de trabalho que opera e mantém os trens e ônibus urbanos',
      material_interest:
        'Preservação da saúde física e mental, estabilidade no emprego e valorização salarial',
      relations: [
        {
          target: 'Consórcio ViaPrivada Demo',
          relation: 'resiste',
          evidence: 'Paralisação das atividades às 4h da manhã contra a precarização'
        }
      ]
    },
    {
      name: 'Consórcio ViaPrivada Demo',
      type: 'empresa',
      role: 'Concessionária privada detentora dos contratos de operação das linhas',
      material_interest:
        'Maximização da remessa de dividendos (R$ 790 milhões), manutenção dos subsídios estatais (R$ 2,4 bilhões) e redução do custo do trabalho via terceirização',
      relations: [
        {
          target: 'Trabalhadores do Transporte Metropolitano',
          relation: 'lucra',
          evidence: 'Extração de mais-valia ampliada por escala 6x1 e terceirização de técnicos'
        }
      ]
    },
    {
      name: 'Federação Empresarial Metropolitana Fictícia (FEMF)',
      type: 'empresa',
      role: 'Entidade patronal do grande comércio e setor de serviços',
      material_interest:
        'Garantir o deslocamento pontual da força de trabalho para o comércio e impedir precedentes de redução de jornada',
      relations: [
        {
          target: 'Sindicato Unificado dos Trabalhadores em Transporte Demo (SUTTD)',
          relation: 'enquadra',
          evidence: 'Divulgação de estimativa de R$ 180 milhões em perdas diárias para pressionar pelo fim da greve'
        }
      ]
    },
    {
      name: 'Governo Estadual e Tribunal Regional do Trabalho (Estado)',
      type: 'estado',
      role: 'Poder concedente, aparelho judiciário e força policial',
      material_interest:
        'Assegurar a reprodução da ordem capitalista urbana, blindar os contratos de concessão e conter paralisações operárias',
      relations: [
        {
          target: 'Consórcio ViaPrivada Demo',
          relation: 'financia',
          evidence: 'Repasse de R$ 2,4 bilhões em subsídios diretos do orçamento público estadual'
        },
        {
          target: 'Sindicato Unificado dos Trabalhadores em Transporte Demo (SUTTD)',
          relation: 'reprime',
          evidence: 'Imposição de 85% de frota mínima, multa diária de R$ 600 mil e autorização para tropa de choque'
        }
      ]
    },
    {
      name: 'Movimento Popular pelo Transporte Público Demo',
      type: 'movimento_popular',
      role: 'Comitês de usuários das periferias organizados pela mobilidade pública',
      material_interest:
        'Transporte seguro, tarifa zero e fim da subordinação da mobilidade ao lucro privado',
      relations: [
        {
          target: 'Sindicato Unificado dos Trabalhadores em Transporte Demo (SUTTD)',
          relation: 'organiza',
          evidence: 'Atos conjuntos nas estações em defesa dos grevistas e do controle público'
        }
      ]
    }
  ],
  marxist_leninist_analysis: {
    central_contradiction:
      'Contradição entre o caráter social e essencial do transporte público metropolitano — produzido coletivamente pelos trabalhadores e financiado pela população via impostos e tarifas — e a apropriação privada dos resultados pelo Consórcio ViaPrivada Demo sob a forma de dividendos bilionários.',
    class_relations:
      'Enfrentamento direto entre o proletariado do setor de transportes (aliado às camadas trabalhadoras periféricas usuárias do sistema) e a fração burguesa concessionária de serviços públicos, respaldada pela burguesia comercial e financeira (FEMF).',
    property_and_power:
      'O modelo de concessão privada transfere a gestão de uma infraestrutura pública estratégica para fundos privados que detêm o poder de demitir, terceirizar e comprimir salários, ao mesmo tempo em que socializam os custos operacionais por meio de R$ 2,4 bilhões em subsídios estatais.',
    role_of_state:
      'Longe de atuar como árbitro neutro como sugere o boletim institucional (Veículo Demo C), o Estado burguês opera em duas frentes complementares: garante a acumulação privada via subsídios orçamentários e aciona imediatamente seu braço jurídico-repressivo (liminar de 85% de frota, multa de R$ 600 mil e tropa de choque) para inviabilizar na prática o direito de greve.',
    imperialism_or_dependency: 'sem_evidencia_suficiente',
    ideology_and_naturalization:
      "A cobertura liberal (Veículo Demo A) naturaliza o lucro contratual sob o jargão técnico de 'equilíbrio econômico-financeiro' e 'segurança jurídica', enquanto converte o direito elementar de resistência contra a escala 6x1 em 'prejuízo ao comércio' e 'caos urbano'.",
    hegemony_and_silenced_voices:
      'No noticiário mercantil, federações patronais, diretores de concessionárias e analistas financeiros falam como representantes da racionalidade econômica universal, enquanto os trabalhadores que operam os trens e sofrem o desgaste físico têm suas razões silenciadas; somente na imprensa sindical e popular (Veículo Demo B) a relação entre subsídio público, dividendo privado e precarização vem à tona.',
    forms_of_struggle:
      'Assembleia geral massiva de base, greve unificada por tempo indeterminado e construção de unidade ativa com comitês populares de usuários nas estações.',
    immediate_demand:
      'Redução da jornada semanal sem redução salarial, fim da escala 6x1, suspensão imediata das terceirizações, revogação das multas antissindicais e abertura pública das planilhas de custos e subsídios da concessionária.',
    strategic_perspective:
      'Reversão das privatizações e reestatização integral do transporte coletivo metropolitano sob controle público direto dos trabalhadores do setor e dos conselhos populares de usuários, rumo à tarifa zero financiada progressivamente sobre o grande capital.',
    limitations_and_uncertainty: [
      'Este dossiê utiliza dados 100% sintéticos de demonstração (DEMO) e não se refere a veículos reais.',
      'As matérias não informam a composição acionária internacional ou estrangeira dos fundos controladores do consórcio.'
    ]
  },
  reader_questions: [
    'Por que a transferência de R$ 2,4 bilhões do orçamento público para uma concessionária privada é tratada como cumprimento técnico de contrato, enquanto a reivindicação salarial dos trabalhadores é tratada como ameaça fiscal?',
    'Quem aparece como sujeito legítimo quando o jornal comercial mede os efeitos de uma greve apenas pelo faturamento diário do varejo e nunca pelo desgaste físico da escala 6x1?',
    'Qual é o sentido real do direito constitucional de greve quando o aparato judiciário impõe 85% de operação compulsória sob multa de R$ 600 mil por dia?'
  ],
  data_visualizations: [
    {
      title: 'Destinação dos Recursos na Concessão (em R$ milhões)',
      type: 'bar',
      description:
        'Comparação entre subsídios públicos recebidos pelo Consórcio ViaPrivada Demo, dividendos distribuídos aos acionistas e prejuízo diário alegado pela federação patronal nas matérias do evento.',
      labels: [
        'Subsídios Públicos Anuais (Demo B)',
        'Dividendos aos Acionistas (Demo B)',
        'Perda Diária Alegada pelo Comércio (Demo A)'
      ],
      values: [2400, 790, 180],
      source_article_ids: ['demo-art-001', 'demo-art-002']
    },
    {
      title: 'Fontes Privilegiadas por Cobertura',
      type: 'bar',
      description:
        'Quantidade de fontes institucionais, patronais e sindicais/populares citadas diretamente em cada veículo do evento.',
      labels: [
        'Veículo Demo A (Liberal)',
        'Veículo Demo B (Sindical)',
        'Veículo Demo C (Institucional)'
      ],
      values: [3, 3, 2],
      source_article_ids: ['demo-art-001', 'demo-art-002', 'demo-art-003']
    }
  ],
  confidence: 0.83,
  audit_metadata: {
    analyzed_at: '2026-10-28T13:00:00Z',
    llm_model: 'Meta-Llama-3.1-8B-Instruct-Q4_K_M (Seed Sintético DEMO)',
    num_ctx: 8192,
    execution_time_ms: 0,
    is_demo: true,
    articles_registry: [
      {
        id: 'demo-art-001',
        source_id: 'demo_veiculo_a',
        veiculo: 'Veículo Demo A — Diário Mercantil (Posição Editorial: Fictícia Liberal)',
        autor: 'Editoria de Mercado Demo (Fictícia)',
        data_publicacao: '2026-10-28T08:30:00Z',
        data_coleta: '2026-10-28T13:00:00Z',
        url_canonica: 'https://demo-a.contraponto.local/economia/paralisacao-transporte-prejuizo-comercio',
        titulo: '[DEMO] Paralisação no transporte paralisa corredores financeiros e gera prejuízo estimado em R$ 180 milhões ao comércio',
        posicao_editorial_declarada: 'Fictícia — Liberalismo econômico e defesa de concessões privadas (DEMO)',
        categoria_editorial: 'grande_midia_liberal',
        metodo_coleta: 'rss_full',
        is_demo: true
      },
      {
        id: 'demo-art-002',
        source_id: 'demo_veiculo_b',
        veiculo: 'Veículo Demo B — Tribuna Operária (Posição Editorial: Fictícia Sindical)',
        autor: 'Coletivo de Base Demo (Fictício)',
        data_publicacao: '2026-10-28T09:15:00Z',
        data_coleta: '2026-10-28T13:00:00Z',
        url_canonica: 'https://demo-b.contraponto.local/lutas/trabalhadores-transporte-greve-contra-terceirizacao',
        titulo: '[DEMO] Trabalhadores do transporte cruzam os braços contra terceirização, escala exaustiva e remessa recorde de lucros',
        posicao_editorial_declarada: 'Fictícia — Imprensa sindical classista e popular (DEMO)',
        categoria_editorial: 'imprensa_popular_sindical_esquerda',
        metodo_coleta: 'rss_full',
        is_demo: true
      },
      {
        id: 'demo-art-003',
        source_id: 'demo_veiculo_c',
        veiculo: 'Veículo Demo C — Boletim Oficial (Posição Editorial: Fictícia Institucional)',
        autor: 'Agência Pública Demo (Fictícia)',
        data_publicacao: '2026-10-28T11:00:00Z',
        data_coleta: '2026-10-28T13:00:00Z',
        url_canonica: 'https://demo-c.contraponto.local/institucional/secretaria-mesa-conciliacao-contingencia',
        titulo: '[DEMO] Secretaria de Transportes instala mesa de conciliação e determina operação de contingência nas linhas metropolitanas',
        posicao_editorial_declarada: 'Fictícia — Comunicação institucional de órgãos públicos (DEMO)',
        categoria_editorial: 'estatal_institucional',
        metodo_coleta: 'trafilatura',
        is_demo: true
      }
    ]
  }
};

export const DEMO_FALLBACK_EVENT_SUMMARY = {
  id: 'demo-event-transporte-sp-2026',
  titulo_provisorio: DEMO_FALLBACK_DOSSIER.title,
  resumo:
    'Evento de demonstração 100% sintético comparando três enquadramentos distintos sobre paralisação fictícia no transporte coletivo de São Paulo.',
  periodo_inicio: '2026-10-28T06:00:00Z',
  periodo_fim: '2026-10-28T13:00:00Z',
  score_coesao: 0.91,
  tema: 'trabalho',
  local: 'São Paulo, Brasil',
  lat: -23.5505,
  lon: -46.6333,
  is_demo: true,
  articles_count: 3,
  has_dossier: true,
  confidence: 0.83
};

export async function fetchEvents({ theme = '', limit = 20, offset = 0 } = {}) {
  const base = getApiBase();
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (theme) params.set('theme', theme);
  try {
    const res = await fetch(`${base}/events?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    const items =
      !theme || theme === DEMO_FALLBACK_EVENT_SUMMARY.tema
        ? [DEMO_FALLBACK_EVENT_SUMMARY]
        : [];
    return {
      total: items.length,
      limit,
      offset,
      items
    };
  }
}

export async function fetchEventDetail(eventId) {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/events/${encodeURIComponent(eventId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return {
      ...DEMO_FALLBACK_EVENT_SUMMARY,
      id: eventId,
      articles: DEMO_FALLBACK_DOSSIER.audit_metadata.articles_registry,
      dossier: DEMO_FALLBACK_DOSSIER
    };
  }
}

export async function fetchEventDossier(eventId) {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/events/${encodeURIComponent(eventId)}/dossier`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return { ...DEMO_FALLBACK_DOSSIER, event_id: eventId };
  }
}

export async function triggerEventAnalysis(eventId) {
  const base = getApiBase();
  const res = await fetch(`${base}/events/${encodeURIComponent(eventId)}/analyze`, {
    method: 'POST'
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erro HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchAnalysisStatus(eventId) {
  const base = getApiBase();
  const res = await fetch(`${base}/events/${encodeURIComponent(eventId)}/analysis-status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export function getExportUrl(eventId, format = 'markdown') {
  const base = getApiBase();
  return `${base}/events/${encodeURIComponent(eventId)}/export?format=${encodeURIComponent(format)}`;
}
