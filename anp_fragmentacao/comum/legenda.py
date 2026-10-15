"""
AnP Fragmentação — Legenda e grupos de cobertura.
Trabalha apenas com Nível 1 da hierarquia MapBiomas Coleção 10.
"""

# Coleções suportadas
COLECOES = {
    "MapBiomas Coleção 10 (Landsat, 30m)": {
        "resolucao_m": 30, "px_m2": 900,
        "descricao": "Série histórica 1985–2024, resolução 30m"},
    "MapBiomas Sentinel-2 (10m)": {
        "resolucao_m": 10, "px_m2": 100,
        "descricao": "Alta resolução 10m"},
    "MapBiomas Landsat — outra coleção": {
        "resolucao_m": 30, "px_m2": 900,
        "descricao": "Coleções anteriores Landsat 30m"},
}

# Nodata MapBiomas
NODATA_VALS = {0, 255, -1, 27}

# Mapa código → nível 1 (todos os códigos da Coleção 10 → N1)
MAPA_N1 = {
    # Floresta (1)
    1:1, 3:1, 4:1, 5:1, 6:1, 49:1,
    # Veg. Herbácea e Arbustiva (10)
    10:10, 11:10, 12:10, 13:10, 29:10, 32:10, 50:10,
    # Agropecuária (14)
    14:14, 9:14, 15:14, 18:14, 19:14, 20:14, 21:14,
    35:14, 36:14, 39:14, 40:14, 41:14, 46:14, 47:14, 48:14, 62:14,
    # Área não Vegetada (22)
    22:22, 23:22, 24:22, 25:22, 30:22, 75:22,
    # Corpo D'água (26)
    26:26, 31:26, 33:26,
    # Não Observado (nodata)
    27:27,
}

# Grupos de cobertura para análise de fragmentação
# Cada grupo define quais códigos N1 compõem a máscara
# Grupos de cobertura NATURAL apenas - Corpo D'agua foi removido
# porque a analise de fragmentacao/conectividade do AnP e destinada
# a vegetacao natural (Floresta e Vegetacao Herbacea), nao a corpos
# hidricos, cuja dinamica estrutural segue logica distinta.
GRUPOS_FRAG = [
    {"id": "floresta",   "nome": "Floresta",
     "codigos_n1": [1],       "natural": True},
    {"id": "herbaceo",   "nome": "Veg. Herbácea e Arbustiva",
     "codigos_n1": [10],      "natural": True},
    {"id": "natural",    "nome": "Cobertura Natural",
     "codigos_n1": [1, 10],   "natural": True},
]

# Métricas de classe — PyLandStats
METRICAS_CLASSE_PLS = {
    "CA"      : "total_area",
    "PLAND"   : "proportion_of_landscape",
    "LPI"     : "largest_patch_index",
    "NP"      : "number_of_patches",
    "PD"      : "patch_density",
    "AREA_MN" : "area_mn",
    "TE"      : "total_edge",
    "ED"      : "edge_density",
    "SHAPE_MN": "shape_index_mn",
}

# Métricas de paisagem — PyLandStats
METRICAS_PAISAGEM_PLS = {
    "MESH": "effective_mesh_size",
    "LSI" : "landscape_shape_index",
}

# Unidades por métrica
UNIDADES = {
    "CA"      : "ha",    "PLAND"   : "%",
    "LPI"     : "%",     "NP"      : "n",
    "PD"      : "n/100ha","AREA_MN" : "ha",
    "TE"      : "m",     "ED"      : "m/ha",
    "SHAPE_MN": "adim.", "TCA"     : "ha",
    "CORE_MN" : "ha",    "NDCA"    : "n",
    "MESH"    : "ha",    "LSI"     : "adim.",
}

# Grupos temáticos para organização das abas Excel
GRUPOS_TEMATICOS = {
    "Área"        : ["CA", "PLAND", "LPI"],
    "Fragmentação": ["NP", "PD", "AREA_MN"],
    "Borda"       : ["TE", "ED"],
    "Área Núcleo" : ["TCA", "CORE_MN", "NDCA"],
    "Forma"       : ["SHAPE_MN"],
    "Paisagem"    : ["MESH", "LSI"],
}

def agregar_n1(arr):
    """Remapeia todos os códigos para Nível 1."""
    import numpy as np
    resultado = np.zeros_like(arr)
    for cod, n1 in MAPA_N1.items():
        resultado[arr == cod] = n1
    return resultado

def info_borda(resolucao_m, n_pixels):
    """Retorna texto explicativo sobre a distância de borda."""
    dist_m = resolucao_m * n_pixels
    equiv  = {}
    for nome, res in [("Landsat 30m", 30), ("Sentinel 10m", 10)]:
        equiv_px = dist_m / res
        equiv[nome] = equiv_px
    return dist_m, equiv


# ── Nomes de classe (MapBiomas) — do módulo de Fragmentos v0.2 ───────────────
NOME_CLASSE = {
    1:  "Floresta",
    3:  "Formação Florestal",
    4:  "Formação Savânica",
    5:  "Mangue",
    6:  "Floresta Alagável",
    49: "Restinga Arbórea",
    10: "Formação Natural não Florestal",
    11: "Campo Alagado e Área Pantanosa",
    12: "Formação Campestre",
    32: "Apicum",
    29: "Afloramento Rochoso",
    50: "Restinga Herbácea",
    13: "Outra Formação não Florestal",
    14: "Agropecuária",
    15: "Pastagem",
    18: "Agricultura",
    19: "Lavoura Temporária",
    39: "Soja",
    20: "Cana",
    40: "Arroz",
    62: "Algodão",
    41: "Outras Lavouras Temporárias",
    36: "Lavoura Perene",
    46: "Café",
    47: "Citrus",
    35: "Dendê",
    48: "Outras Lavouras Perenes",
    9:  "Silvicultura",
    21: "Mosaico de Usos",
    22: "Área não Vegetada",
    23: "Praia, Duna e Areal",
    24: "Área Urbanizada",
    30: "Mineração",
    25: "Outras Áreas não Vegetadas",
    26: "Corpo D'água",
    33: "Rio, Lago e Oceano",
    31: "Aquicultura",
    27: "Não Observado",
}


def nome_classe(v):
    try:
        return NOME_CLASSE.get(int(v), f"Classe {v}")
    except (TypeError, ValueError):
        return str(v)
