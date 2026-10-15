"""
AnP v1.1 — Legendas MapBiomas Coleção 10.
Suporte a Landsat (30m) e Sentinel-2 (10m).
Hierarquia de 4 níveis para agregação comparativa.
"""

# ── Coleções disponíveis ──────────────────────────────────────────────────────
COLECOES = {
    "MapBiomas Coleção 10 (Landsat, 30m)": {
        "codigo"     : "col10_landsat",
        "resolucao_m": 30,
        "px_m2"      : 900,
        "nivel_max"  : 4,
        "descricao"  : "Série histórica 1985–2024, resolução 30m, até nível 4",
    },
    "MapBiomas Sentinel-2 (10m)": {
        "codigo"     : "col10_sentinel",
        "resolucao_m": 10,
        "px_m2"      : 100,
        "nivel_max"  : 3,
        "descricao"  : "Alta resolução 10m, até nível 3 de legenda",
    },
    "MapBiomas Landsat — outra coleção": {
        "codigo"     : "landsat_generico",
        "resolucao_m": 30,
        "px_m2"      : 900,
        "nivel_max"  : 4,
        "descricao"  : "Coleções anteriores (Landsat, 30m)",
    },
}

# ── Classes excluídas dos cálculos (nodata) ───────────────────────────────────
CLASSES_EXCLUIR = {0, 255, -1, 27}

# ── Classes naturais (para categorização de transições) ───────────────────────
CLASSES_NATURAIS = {1, 3, 4, 5, 6, 49, 10, 11, 12, 13, 29, 32, 50, 23, 26, 33}

# ── Hierarquia completa — mapeia cada código aos seus pais por nível ─────────
#    l1 = código ao nível 1  (grande grupo)
#    l2 = código ao nível 2  (subgrupo)
#    l3 = código ao nível 3  (detalhado)
#    l4 = código ao nível 4  (máximo detalhe)
HIERARQUIA = {
    # ── NÍVEL 1 (grandes grupos — códigos agregadores) ──────────────────────
    1:  {'l1':1,  'l2':1,  'l3':1,  'l4':1 },  # Floresta (agregado)
    10: {'l1':10, 'l2':10, 'l3':10, 'l4':10},  # Veg. Herbácea (agregado)
    14: {'l1':14, 'l2':14, 'l3':14, 'l4':14},  # Agropecuária (agregado)
    22: {'l1':22, 'l2':22, 'l3':22, 'l4':22},  # Área não Vegetada (agregado)
    26: {'l1':26, 'l2':26, 'l3':26, 'l4':26},  # Corpo D'água (agregado)
    27: {'l1':27, 'l2':27, 'l3':27, 'l4':27},  # Não Observado

    # ── NÍVEL 2 — Floresta ───────────────────────────────────────────────────
    3:  {'l1':1,  'l2':3,  'l3':3,  'l4':3 },  # Formação Florestal
    4:  {'l1':1,  'l2':4,  'l3':4,  'l4':4 },  # Formação Savânica
    5:  {'l1':1,  'l2':5,  'l3':5,  'l4':5 },  # Mangue
    6:  {'l1':1,  'l2':6,  'l3':6,  'l4':6 },  # Floresta Alagável
    49: {'l1':1,  'l2':49, 'l3':49, 'l4':49},  # Restinga Arbórea

    # ── NÍVEL 2 — Vegetação Herbácea e Arbustiva ─────────────────────────────
    11: {'l1':10, 'l2':11, 'l3':11, 'l4':11},  # Campo Alagado e Área Pantanosa
    12: {'l1':10, 'l2':12, 'l3':12, 'l4':12},  # Formação Campestre
    32: {'l1':10, 'l2':32, 'l3':32, 'l4':32},  # Apicum
    29: {'l1':10, 'l2':29, 'l3':29, 'l4':29},  # Afloramento Rochoso
    50: {'l1':10, 'l2':50, 'l3':50, 'l4':50},  # Restinga Herbácea

    # ── NÍVEL 2 — Agropecuária ───────────────────────────────────────────────
    15: {'l1':14, 'l2':15, 'l3':15, 'l4':15},  # Pastagem
    18: {'l1':14, 'l2':18, 'l3':18, 'l4':18},  # Agricultura (agregado N2)
    9:  {'l1':14, 'l2':9,  'l3':9,  'l4':9 },  # Silvicultura
    21: {'l1':14, 'l2':21, 'l3':21, 'l4':21},  # Mosaico de Usos

    # ── NÍVEL 2 — Área não Vegetada ──────────────────────────────────────────
    23: {'l1':22, 'l2':23, 'l3':23, 'l4':23},  # Praia, Duna e Areal
    24: {'l1':22, 'l2':24, 'l3':24, 'l4':24},  # Área Urbanizada
    30: {'l1':22, 'l2':30, 'l3':30, 'l4':30},  # Mineração
    75: {'l1':22, 'l2':75, 'l3':75, 'l4':75},  # Usina Fotovoltaica (beta)
    25: {'l1':22, 'l2':25, 'l3':25, 'l4':25},  # Outras Áreas não Vegetadas

    # ── NÍVEL 2 — Corpo D'água ───────────────────────────────────────────────
    33: {'l1':26, 'l2':33, 'l3':33, 'l4':33},  # Rio, Lago e Oceano
    31: {'l1':26, 'l2':31, 'l3':31, 'l4':31},  # Aquicultura

    # ── NÍVEL 3 — Agricultura desagregada ────────────────────────────────────
    19: {'l1':14, 'l2':18, 'l3':19, 'l4':19},  # Lavoura Temporária
    36: {'l1':14, 'l2':18, 'l3':36, 'l4':36},  # Lavoura Perene

    # ── NÍVEL 4 — Lavoura Temporária ─────────────────────────────────────────
    39: {'l1':14, 'l2':18, 'l3':19, 'l4':39},  # Soja
    20: {'l1':14, 'l2':18, 'l3':19, 'l4':20},  # Cana-de-açúcar
    40: {'l1':14, 'l2':18, 'l3':19, 'l4':40},  # Arroz
    62: {'l1':14, 'l2':18, 'l3':19, 'l4':62},  # Algodão (beta)
    41: {'l1':14, 'l2':18, 'l3':19, 'l4':41},  # Outras Lavouras Temporárias

    # ── NÍVEL 4 — Lavoura Perene ─────────────────────────────────────────────
    46: {'l1':14, 'l2':18, 'l3':36, 'l4':46},  # Café
    47: {'l1':14, 'l2':18, 'l3':36, 'l4':47},  # Citrus
    35: {'l1':14, 'l2':18, 'l3':36, 'l4':35},  # Dendê
    48: {'l1':14, 'l2':18, 'l3':36, 'l4':48},  # Outras Lavouras Perenes
}

# ── Legendas por nível ────────────────────────────────────────────────────────
LEGENDA_NIVEL = {
    1: {
        1:  "Floresta",
        10: "Vegetação Herbácea e Arbustiva",
        14: "Agropecuária",
        22: "Área não Vegetada",
        26: "Corpo D'água",
        27: "Não Observado",
    },
    2: {
        1:  "Floresta",         10: "Veg. Herbácea e Arbustiva",
        14: "Agropecuária",     22: "Área não Vegetada",
        26: "Corpo D'água",     27: "Não Observado",
        3:  "Formação Florestal",   4:  "Formação Savânica",
        5:  "Mangue",               6:  "Floresta Alagável",
        49: "Restinga Arbórea",     11: "Campo Alagado e Área Pantanosa",
        12: "Formação Campestre",   32: "Apicum",
        29: "Afloramento Rochoso",  50: "Restinga Herbácea",
        15: "Pastagem",             18: "Agricultura",
        9:  "Silvicultura",         21: "Mosaico de Usos",
        23: "Praia, Duna e Areal",  24: "Área Urbanizada",
        30: "Mineração",            75: "Usina Fotovoltaica (beta)",
        25: "Outras Áreas não Vegetadas",
        33: "Rio, Lago e Oceano",   31: "Aquicultura",
    },
}
# Nível 3 = nível 2 + lavouras
LEGENDA_NIVEL[3] = {**LEGENDA_NIVEL[2],
    19: "Lavoura Temporária",
    36: "Lavoura Perene",
}
# Nível 4 = nível 3 + culturas específicas
LEGENDA_NIVEL[4] = {**LEGENDA_NIVEL[3],
    39: "Soja",                     20: "Cana-de-açúcar",
    40: "Arroz",                    62: "Algodão (beta)",
    41: "Outras Lavouras Temporárias",
    46: "Café",                     47: "Citrus",
    35: "Dendê",                    48: "Outras Lavouras Perenes",
}

# Legenda padrão (nível 4 completo)
LEGENDA = LEGENDA_NIVEL[4]

# ── Agrupamentos por grupo temático (nível 2) ─────────────────────────────────
GRUPOS = {
    3:"Floresta", 4:"Floresta", 5:"Floresta", 6:"Floresta", 49:"Floresta",
    11:"Veg. Herbácea e Aquática", 12:"Veg. Herbácea e Aquática",
    32:"Veg. Herbácea e Aquática", 29:"Veg. Herbácea e Aquática",
    50:"Veg. Herbácea e Aquática",
    15:"Agropecuária", 18:"Agropecuária", 19:"Agropecuária", 36:"Agropecuária",
    39:"Agropecuária", 20:"Agropecuária", 40:"Agropecuária", 62:"Agropecuária",
    41:"Agropecuária", 46:"Agropecuária", 47:"Agropecuária", 35:"Agropecuária",
    48:"Agropecuária", 9:"Agropecuária", 21:"Agropecuária",
    23:"Área não Vegetada", 24:"Área não Vegetada", 30:"Área não Vegetada",
    75:"Área não Vegetada", 25:"Área não Vegetada",
    33:"Corpo D'água", 31:"Corpo D'água",
}

# ── Função de agregação ───────────────────────────────────────────────────────
def agregar_nivel(arr, nivel):
    """
    Remapeia array de pixels para o nível de legenda solicitado.
    Pixels de classes que não existem no nível escolhido são
    mapeados ao seu pai hierárquico correspondente.
    Pixels com códigos não reconhecidos permanecem inalterados.
    """
    import numpy as np
    chave = f'l{nivel}'
    resultado = arr.copy()
    for cod, info in HIERARQUIA.items():
        resultado[arr == cod] = info[chave]
    return resultado

def n_classes_nivel(nivel):
    """Retorna número de classes distintas no nível."""
    chave = f'l{nivel}'
    return len({v[chave] for v in HIERARQUIA.values()
                if v[chave] not in CLASSES_EXCLUIR})

def descricao_nivel(nivel):
    n = n_classes_nivel(nivel)
    exemplos = {
        1: "Floresta, Agropecuária, Área não Vegetada…",
        2: "Form. Florestal, Pastagem, Urbanizada, Mineração…",
        3: "Lavoura Temporária, Lavoura Perene (sem detalhe de culturas)",
        4: "Soja, Cana, Café, Citrus, Dendê… (máximo detalhe)",
    }
    return f"Nível {nivel} — {n} classes  |  {exemplos.get(nivel,'')}"

# ── Categorias de transição ───────────────────────────────────────────────────
CAT_NATURAL_NATURAL = "Manteve-se em cobertura natural"
CAT_ANTROP_ANTROP   = "Manteve-se em cobertura antrópica"
CAT_ENTRE_NATURAIS  = "Mudou entre coberturas naturais"
CAT_ENTRE_ANTROP    = "Mudou entre coberturas antrópicas"
CAT_ANTROP_NATURAL  = "Mudou de antrópico para natural"
CAT_NATURAL_ANTROP  = "Mudou de natural para antrópico"

CORES_CATEGORIA = {
    CAT_NATURAL_NATURAL : "388E3C",
    CAT_ANTROP_ANTROP   : "F57C00",
    CAT_ENTRE_NATURAIS  : "AED581",
    CAT_ENTRE_ANTROP    : "9C27B0",
    CAT_ANTROP_NATURAL  : "1976D2",
    CAT_NATURAL_ANTROP  : "D32F2F",
}

TEXTO_BRANCO_CAT = {
    CAT_NATURAL_NATURAL: True,  CAT_ANTROP_ANTROP: True,
    CAT_ENTRE_NATURAIS : False, CAT_ENTRE_ANTROP : True,
    CAT_ANTROP_NATURAL : True,  CAT_NATURAL_ANTROP: True,
}

def categoria_transicao(cod_orig, cod_dest):
    o_nat = cod_orig in CLASSES_NATURAIS
    d_nat = cod_dest in CLASSES_NATURAIS
    if cod_orig == cod_dest:
        return CAT_NATURAL_NATURAL if o_nat else CAT_ANTROP_ANTROP
    if o_nat  and d_nat:  return CAT_ENTRE_NATURAIS
    if not o_nat and not d_nat: return CAT_ENTRE_ANTROP
    if not o_nat and d_nat:  return CAT_ANTROP_NATURAL
    return CAT_NATURAL_ANTROP


# ── Cores por classe (N1/N2) e utilitários vindos do Relatório ────────────────
CORES_N1 = {
    1:  "1F4E31",  # Floresta
    10: "AAD374",  # Veg. Herbácea
    14: "EDDE8E",  # Agropecuária
    22: "D4271E",  # Área não Vegetada
    26: "2532E4",  # Corpo D'água
    27: "D3D2D2",  # Não Observado
}

CORES_N2 = {
    3:"1F4E31", 4:"7DC36B", 5:"04381D", 6:"026975", 49:"02D659",
    11:"519799", 12:"D6BC74", 32:"FF99FF", 29:"AD5100", 50:"D68FE5",
    15:"EDDE8E", 18:"E974ED", 9:"935132", 21:"FFEFC3",
    19:"C27BA0", 36:"C3814B",
    23:"DD5F9B", 24:"D4271E", 30:"9C0027", 75:"C12100", 25:"DB4D4F",
    33:"2532E4", 31:"091077",
}

def cor_classe(cod, nivel=1):
    """Retorna cor hex sem # para uso em gráficos openpyxl."""
    if nivel == 1:
        return CORES_N1.get(cod, "CCCCCC")
    return CORES_N2.get(cod, "CCCCCC")

def nome_classe(cod):
    return LEGENDA.get(cod, f"Código {cod}")

def ancestrais(cod):
    """
    Retorna dict com códigos e nomes de todos os níveis (1-4)
    para um código original de pixel.
    Se o código não estiver na hierarquia, usa ele mesmo em todos os níveis.
    """
    info = HIERARQUIA.get(cod)
    if info is None:
        return {
            'cod_n1': cod, 'nome_n1': nome_classe(cod),
            'cod_n2': cod, 'nome_n2': nome_classe(cod),
            'cod_n3': cod, 'nome_n3': nome_classe(cod),
            'cod_n4': cod, 'nome_n4': nome_classe(cod),
        }
    return {
        'cod_n1': info['l1'], 'nome_n1': nome_classe(info['l1']),
        'cod_n2': info['l2'], 'nome_n2': nome_classe(info['l2']),
        'cod_n3': info['l3'], 'nome_n3': nome_classe(info['l3']),
        'cod_n4': info['l4'], 'nome_n4': nome_classe(info['l4']),
    }

def cor_original(cod):
    """
    Cor oficial MapBiomas para um código original de pixel.
    Tenta CORES_N2 primeiro (mais específica); cai para CORES_N1
    do grupo ancestral se não encontrar.
    """
    if cod in CORES_N2:
        return CORES_N2[cod]
    anc = ancestrais(cod)
    return CORES_N1.get(anc['cod_n1'], "CCCCCC")



# ── Códigos presentes em cada nível (usado no filtro de QML da Preparação) ─────
CODIGOS_POR_NIVEL = {n: set(LEGENDA_NIVEL[n].keys()) for n in (1, 2, 3, 4)}
