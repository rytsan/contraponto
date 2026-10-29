import re
from typing import Dict, List, Optional, Set

ENTITY_CATEGORIES = (
    "pessoas",
    "empresas",
    "leis",
    "paises",
    "sindicatos",
    "movimentos",
    "instituicoes",
    "lugares",
)

ALIAS_NORMALIZATION: Dict[str, str] = {
    "lula": "Luiz Inácio Lula da Silva",
    "lula da silva": "Luiz Inácio Lula da Silva",
    "luiz inacio lula da silva": "Luiz Inácio Lula da Silva",
    "luiz inácio lula da silva": "Luiz Inácio Lula da Silva",
    " presidente lula": "Luiz Inácio Lula da Silva",
    "haddad": "Fernando Haddad",
    "fernando haddad": "Fernando Haddad",
    "bolsonaro": "Jair Bolsonaro",
    "jair bolsonaro": "Jair Bolsonaro",
    "tarcisio": "Tarcísio de Freitas",
    "tarcísio": "Tarcísio de Freitas",
    "tarcisio de freitas": "Tarcísio de Freitas",
    "tarcísio de freitas": "Tarcísio de Freitas",
    "campos neto": "Roberto Campos Neto",
    "roberto campos neto": "Roberto Campos Neto",
    "galipolo": "Gabriel Galípolo",
    "galípolo": "Gabriel Galípolo",
    "gabriel galípolo": "Gabriel Galípolo",
    "stf": "Supremo Tribunal Federal",
    "supremo tribunal federal": "Supremo Tribunal Federal",
    "bc": "Banco Central",
    "bacen": "Banco Central",
    "banco central": "Banco Central",
    "copom": "Comitê de Política Monetária",
    "camara dos deputados": "Câmara dos Deputados",
    "câmara dos deputados": "Câmara dos Deputados",
    "senado": "Senado Federal",
    "senado federal": "Senado Federal",
    "congresso": "Congresso Nacional",
    "congresso nacional": "Congresso Nacional",
    "mpt": "Ministério Público do Trabalho",
    "tst": "Tribunal Superior do Trabalho",
    "ibama": "IBAMA",
    "incra": "INCRA",
    "bndes": "BNDES",
    "onu": "Organização das Nações Unidas",
    "fmi": "Fundo Monetário Internacional",
    "otan": "OTAN",
    "cut": "Central Única dos Trabalhadores",
    "central unica dos trabalhadores": "Central Única dos Trabalhadores",
    "central única dos trabalhadores": "Central Única dos Trabalhadores",
    "forca sindical": "Força Sindical",
    "força sindical": "Força Sindical",
    "csp-conlutas": "CSP-Conlutas",
    "ctb": "Central dos Trabalhadores e Trabalhadoras do Brasil",
    "fup": "Federação Única dos Petroleiros",
    "mst": "Movimento dos Trabalhadores Rurais Sem Terra",
    "movimento dos trabalhadores rurais sem terra": "Movimento dos Trabalhadores Rurais Sem Terra",
    "mtst": "Movimento dos Trabalhadores Sem-Teto",
    "movimento dos trabalhadores sem-teto": "Movimento dos Trabalhadores Sem-Teto",
    "mab": "Movimento dos Atingidos por Barragens",
    "une": "União Nacional dos Estudantes",
    "petrobras": "Petrobras",
    "vale": "Vale S.A.",
    "eletrobras": "Eletrobras",
    "sabesp": "Sabesp",
    "jbs": "JBS",
    "brf": "BRF",
    "embraer": "Embraer",
    "itaú": "Itaú Unibanco",
    "itau": "Itaú Unibanco",
    "bradesco": "Bradesco",
    "fiesp": "FIESP",
    "febraban": "FEBRABAN",
    "cni": "Confederação Nacional da Indústria",
    "cna": "Confederação da Agricultura e Pecuária do Brasil",
    "eua": "Estados Unidos",
    "estados unidos": "Estados Unidos",
    "usa": "Estados Unidos",
    "reino unido": "Reino Unido",
    "uk": "Reino Unido",
    "uniao europeia": "União Europeia",
    "união europeia": "União Europeia",
    "sp": "São Paulo",
    "sao paulo": "São Paulo",
    "são paulo": "São Paulo",
    "rj": "Rio de Janeiro",
    "rio de janeiro": "Rio de Janeiro",
    "df": "Brasília",
    "brasilia": "Brasília",
    "brasília": "Brasília",
}

KNOWN_ENTITIES_BY_CATEGORY: Dict[str, Dict[str, str]] = {
    "pessoas": {
        "lula": "Luiz Inácio Lula da Silva",
        "lula da silva": "Luiz Inácio Lula da Silva",
        "luiz inácio lula da silva": "Luiz Inácio Lula da Silva",
        "fernando haddad": "Fernando Haddad",
        "haddad": "Fernando Haddad",
        "jair bolsonaro": "Jair Bolsonaro",
        "bolsonaro": "Jair Bolsonaro",
        "tarcísio de freitas": "Tarcísio de Freitas",
        "tarcisio de freitas": "Tarcísio de Freitas",
        "roberto campos neto": "Roberto Campos Neto",
        "campos neto": "Roberto Campos Neto",
        "gabriel galípolo": "Gabriel Galípolo",
        "arthur lira": "Arthur Lira",
        "rodrigo pacheco": "Rodrigo Pacheco",
        "alexandre de moraes": "Alexandre de Moraes",
        "joão pedro stédile": "João Pedro Stédile",
        "joao pedro stedile": "João Pedro Stédile",
        "guilherme boulos": "Guilherme Boulos",
    },
    "empresas": {
        "petrobras": "Petrobras",
        "vale": "Vale S.A.",
        "eletrobras": "Eletrobras",
        "sabesp": "Sabesp",
        "jbs": "JBS",
        "brf": "BRF",
        "embraer": "Embraer",
        "itaú": "Itaú Unibanco",
        "bradesco": "Bradesco",
        "santander": "Santander",
        "btg pactual": "BTG Pactual",
        "cargill": "Cargill",
        "bunge": "Bunge",
        "enel": "Enel",
        "ifooD": "iFood",
        "ifood": "iFood",
        "uber": "Uber",
    },
    "sindicatos": {
        "cut": "Central Única dos Trabalhadores",
        "central única dos trabalhadores": "Central Única dos Trabalhadores",
        "força sindical": "Força Sindical",
        "csp-conlutas": "CSP-Conlutas",
        "ctb": "Central dos Trabalhadores e Trabalhadoras do Brasil",
        "fup": "Federação Única dos Petroleiros",
        "sindicato dos metalúrgicos": "Sindicato dos Metalúrgicos",
        "sindicato dos metroviários": "Sindicato dos Metroviários",
        "sindicato dos bancários": "Sindicato dos Bancários",
        "sindicato dos professores": "Sindicato dos Professores",
        "apeoesp": "APEOESP",
    },
    "movimentos": {
        "mst": "Movimento dos Trabalhadores Rurais Sem Terra",
        "movimento dos trabalhadores rurais sem terra": "Movimento dos Trabalhadores Rurais Sem Terra",
        "mtst": "Movimento dos Trabalhadores Sem-Teto",
        "movimento dos trabalhadores sem-teto": "Movimento dos Trabalhadores Sem-Teto",
        "mab": "Movimento dos Atingidos por Barragens",
        "une": "União Nacional dos Estudantes",
        "apib": "Articulação dos Povos Indígenas do Brasil",
        "frente povo sem medo": "Frente Povo Sem Medo",
        "frente brasil popular": "Frente Brasil Popular",
    },
    "instituicoes": {
        "stf": "Supremo Tribunal Federal",
        "supremo tribunal federal": "Supremo Tribunal Federal",
        "banco central": "Banco Central",
        "copom": "Comitê de Política Monetária",
        "câmara dos deputados": "Câmara dos Deputados",
        "senado federal": "Senado Federal",
        "congresso nacional": "Congresso Nacional",
        "ministério do trabalho": "Ministério do Trabalho e Emprego",
        "ministério da fazenda": "Ministério da Fazenda",
        "ministério público do trabalho": "Ministério Público do Trabalho",
        "mpt": "Ministério Público do Trabalho",
        "tst": "Tribunal Superior do Trabalho",
        "ibama": "IBAMA",
        "incra": "INCRA",
        "bndes": "BNDES",
        "fiesp": "FIESP",
        "febraban": "FEBRABAN",
        "cna": "Confederação da Agricultura e Pecuária do Brasil",
        "fmi": "Fundo Monetário Internacional",
        "onu": "Organização das Nações Unidas",
    },
    "paises": {
        "brasil": "Brasil",
        "estados unidos": "Estados Unidos",
        "eua": "Estados Unidos",
        "china": "China",
        "rússia": "Rússia",
        "russia": "Rússia",
        "palestina": "Palestina",
        "israel": "Israel",
        "cuba": "Cuba",
        "venezuela": "Venezuela",
        "argentina": "Argentina",
        "colômbia": "Colômbia",
        "méxico": "México",
        "bolívia": "Bolívia",
        "chile": "Chile",
        "ucrânia": "Ucrânia",
        "frança": "França",
        "reino unido": "Reino Unido",
        "irã": "Irã",
        "áfrica do sul": "África do Sul",
    },
    "lugares": {
        "são paulo": "São Paulo",
        "sao paulo": "São Paulo",
        "rio de janeiro": "Rio de Janeiro",
        "brasília": "Brasília",
        "brasilia": "Brasília",
        "belo horizonte": "Belo Horizonte",
        "porto alegre": "Porto Alegre",
        "salvador": "Salvador",
        "recife": "Recife",
        "fortaleza": "Fortaleza",
        "curitiba": "Curitiba",
        "manaus": "Manaus",
        "belém": "Belém",
        "gaza": "Faixa de Gaza",
        "faixa de gaza": "Faixa de Gaza",
        "amazônia": "Amazônia",
        "amazonia": "Amazônia",
    },
}

LAW_REGEX = re.compile(
    r"\b(?:PEC\s*n?[º°]?\s*\d+(?:/\d+)?|PL\s*n?[º°]?\s*\d+(?:/\d+)?|"
    r"Lei\s+(?:Complementar\s+)?n?[º°]?\s*[\d\.]+(?:/\d+)?|"
    r"MP\s*n?[º°]?\s*\d+(?:/\d+)?|CLT|Marco\s+Temporal|Arcabouço\s+Fiscal|"
    r"Reforma\s+Tributária|Reforma\s+Trabalhista|Escala\s+6x1)\b",
    re.IGNORECASE,
)

UNION_GENERIC_REGEX = re.compile(
    r"\b(?:Sindicato\s+d[oa]s\s+[A-ZÀ-Ÿ][a-zà-ÿ]+(?:\s+d[eao]s?\s+[A-ZÀ-Ÿ][a-zà-ÿ]+)?|"
    r"Federação\s+d[oa]s\s+[A-ZÀ-Ÿ][a-zà-ÿ]+)\b"
)

THEME_KEYWORDS: Dict[str, List[str]] = {
    "trabalho": [
        "greve", "sindicato", "trabalhador", "trabalhadores", "salário", "salario",
        "clt", "terceirização", "jornada", "escala 6x1", "demissão", "demissões",
        "paralisação", "categoria", "metalúrgicos", "metroviários", "operários",
    ],
    "terra_e_agronegocio": [
        "mst", "reforma agrária", "agronegócio", "agronegocio", "latifúndio",
        "incra", "ocupação de terra", "sem terra", "soja", "despejo rural",
        "marco temporal", "indígena", "indigenas", "quilombola", "agrotóxico",
    ],
    "economia": [
        "juros", "selic", "banco central", "copom", "inflação", "pib", "fiscal",
        "arcabouço fiscal", "dívida pública", "privatização", "mercado financeiro",
        " bolsa de valores", "lucro", "dividendos", "tributária", "orçamento",
    ],
    "politica_institucional": [
        "congresso", "câmara dos deputados", "senado", "stf", "supremo",
        "eleição", "eleições", "pec ", "projeto de lei", "planalto", "partido",
        "votação", "ministro", "constituição",
    ],
    "seguranca_e_estado": [
        "polícia", "policia", "militar", "operação policial", "repressão",
        "violência policial", "presídio", "encarceramento", "chacina", "pm ",
        "segurança pública", "tropas", "guarda civil",
    ],
    "politica_externa": [
        "imperialismo", "geopolítica", "otan", "onu", "sanções", "guerra",
        "diplomacia", "brics", "estados unidos", "palestina", "gaza", "israel",
        "ucrânia", "cuba", "venezuela", "china", "embaixada",
    ],
    "meio_ambiente": [
        "desmatamento", "amazônia", "clima", "climática", "ibama", "mineração",
        "barragem", "transição energética", "carbono", "queimadas", "secas",
        "enchente", "meio ambiente",
    ],
    "saude_educacao": [
        "sus", "hospital", "saúde pública", "vacina", "epidemia", "universidade",
        "mec", "educação pública", "escola", "professores", "estudantes", "enem",
    ],
    "cultura": [
        "cultura", "cinema", "arte", " património", "música", "teatro",
        "lei rouanet", "audiovisual", "literatura",
    ],
}


def normalize_entity_name(raw_name: str) -> str:
    """Normaliza apelidos, siglas e variações de entidades para forma canônica."""
    cleaned = re.sub(r"\s+", " ", (raw_name or "").strip())
    if not cleaned:
        return ""
    key = cleaned.lower()
    if key in ALIAS_NORMALIZATION:
        return ALIAS_NORMALIZATION[key]
    return cleaned


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extrai entidades estruturadas por categoria e retorna lista deduplicada e normalizada.
    Categorias: pessoas, empresas, leis, paises, sindicatos, movimentos, instituicoes, lugares.
    """
    buckets: Dict[str, Set[str]] = {cat: set() for cat in ENTITY_CATEGORIES}
    if not text or not text.strip():
        return {cat: [] for cat in ENTITY_CATEGORIES}

    lowered = f" {text.lower()} "

    for category, mapping in KNOWN_ENTITIES_BY_CATEGORY.items():
        for trigger, canonical in mapping.items():
            pattern = r"(?<![a-zà-ÿ0-9])" + re.escape(trigger.lower()) + r"(?![a-zà-ÿ0-9])"
            if re.search(pattern, lowered):
                buckets[category].add(canonical)

    for match in LAW_REGEX.finditer(text):
        law_str = re.sub(r"\s+", " ", match.group(0).strip()).upper()
        buckets["leis"].add(law_str)

    for match in UNION_GENERIC_REGEX.finditer(text):
        union_str = normalize_entity_name(match.group(0))
        if union_str:
            buckets["sindicatos"].add(union_str)

    return {cat: sorted(buckets[cat]) for cat in ENTITY_CATEGORIES}


def flatten_entities(entities_dict: Optional[Dict[str, List[str]]]) -> Set[str]:
    """Converte dicionário de entidades em conjunto único normalizado em minúsculas."""
    if not entities_dict:
        return set()
    flat: Set[str] = set()
    for items in entities_dict.values():
        if isinstance(items, list):
            for val in items:
                norm = normalize_entity_name(str(val)).lower()
                if norm:
                    flat.add(norm)
    return flat


def entity_jaccard_similarity(
    entities_a: Optional[Dict[str, List[str]]],
    entities_b: Optional[Dict[str, List[str]]],
) -> float:
    """Calcula a similaridade de Jaccard (0.0 a 1.0) entre as entidades de dois artigos/clusters."""
    set_a = flatten_entities(entities_a)
    set_b = flatten_entities(entities_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


def classify_theme(text: str) -> str:
    """
    Classifica o texto dentro do vocabulário controlado fechado de temas:
    economia, trabalho, terra_e_agronegocio, politica_institucional,
    seguranca_e_estado, politica_externa, meio_ambiente, cultura, saude_educacao, outros.
    """
    if not text:
        return "outros"
    lowered = text.lower()
    scores: Dict[str, int] = {theme: 0 for theme in THEME_KEYWORDS}
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                scores[theme] += 1

    best_theme = max(scores, key=lambda k: scores[k])
    if scores[best_theme] == 0:
        return "outros"
    return best_theme


def extract_primary_location(entities_dict: Optional[Dict[str, List[str]]]) -> Optional[str]:
    """Extrai o nome de local claro a partir das entidades extraídas (lugares ou países)."""
    if not entities_dict:
        return None
    lugares = entities_dict.get("lugares") or []
    paises = entities_dict.get("paises") or []
    if lugares:
        if paises and lugares[0] not in paises:
            return f"{lugares[0]}, {paises[0]}"
        return f"{lugares[0]}, Brasil"
    if paises:
        return paises[0]
    return None
