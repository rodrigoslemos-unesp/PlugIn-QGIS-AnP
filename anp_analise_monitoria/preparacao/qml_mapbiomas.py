"""
AnP — Preparação de Dados
Gerador de arquivo QML com a paleta oficial MapBiomas Coleção 10.

O QML usa o renderizador 'paletted' do QGIS 3.x.
Ao salvar o QML com o mesmo nome-base do TIF, o QGIS aplica
o estilo automaticamente ao importar o arquivo.

Paleta: MapBiomas Coleção 10 — todos os níveis (N1 a N4).
Referência: https://mapbiomas.org/codigos-de-legenda
"""

# ── Paleta completa MapBiomas Coleção 10 ────────────────────────────────────
# Formato: código → (nome, cor_hex_sem_#, alpha)
import os
PALETA_C10 = {
    # ── Nível 1 — Grandes grupos ─────────────────────────────────────────────
    1:  ("Floresta",                    "1F4E31", 255),
    10: ("Veg. Herbácea e Arbustiva",   "AAD374", 255),
    14: ("Agropecuária",                "FFEFC3", 255),
    22: ("Área não Vegetada",           "D4271E", 255),
    26: ("Corpo D'água",                "2532E4", 255),
    27: ("Não Observado",               "D3D2D2", 100),

    # ── Nível 2 — Floresta ────────────────────────────────────────────────────
    3:  ("Formação Florestal",          "1F4E31", 255),
    4:  ("Formação Savânica",           "7DC36B", 255),
    5:  ("Mangue",                      "04381D", 255),
    6:  ("Floresta Alagável",           "026975", 255),
    49: ("Restinga Arbórea",            "02D659", 255),

    # ── Nível 2 — Veg. Herbácea ───────────────────────────────────────────────
    11: ("Campo Alagado e Área Pantanosa","519799", 255),
    12: ("Formação Campestre",          "D6BC74", 255),
    32: ("Apicum",                      "FF99FF", 255),
    29: ("Afloramento Rochoso",         "AD5100", 255),
    50: ("Restinga Herbácea",           "D68FE5", 255),

    # ── Nível 2 — Agropecuária ────────────────────────────────────────────────
    15: ("Pastagem",                    "EDDE8E", 255),
    18: ("Agricultura",                 "E974ED", 255),
    9:  ("Silvicultura",                "935132", 255),
    21: ("Mosaico de Usos",             "FFEFC3", 255),

    # ── Nível 2 — Área não Vegetada ──────────────────────────────────────────
    23: ("Praia, Duna e Areal",         "DD5F9B", 255),
    24: ("Área Urbanizada",             "D4271E", 255),
    30: ("Mineração",                   "9C0027", 255),
    75: ("Usina Fotovoltaica (beta)",   "C12100", 255),
    25: ("Outras Áreas não Vegetadas",  "DB4D4F", 255),

    # ── Nível 2 — Corpo D'água ────────────────────────────────────────────────
    33: ("Rio, Lago e Oceano",          "2532E4", 255),
    31: ("Aquicultura",                 "091077", 255),

    # ── Nível 3 — Desdobramentos agrícolas ───────────────────────────────────
    19: ("Lavoura Temporária",          "C27BA0", 255),
    36: ("Lavoura Perene",              "C3814B", 255),

    # ── Nível 4 — Culturas específicas ───────────────────────────────────────
    39: ("Soja",                        "C3814B", 255),
    20: ("Cana-de-açúcar",              "DB7093", 255),
    40: ("Arroz",                       "9DC5A4", 255),
    62: ("Algodão (beta)",              "E1C4A4", 255),
    41: ("Outras Lavouras Temporárias", "C27BA0", 255),
    46: ("Café",                        "C8A06B", 255),
    47: ("Citrus",                      "FFC0CB", 255),
    35: ("Dendê",                       "A87C52", 255),
    48: ("Outras Lavouras Perenes",     "D4A96A", 255),

    # ── NoData ────────────────────────────────────────────────────────────────
    0:  ("NoData / Sem classificação",  "000000",   0),
    255:("NoData (255)",                "000000",   0),
}


def gerar_qml(caminho_qml, nivel=None):
    """
    Gera arquivo QML com a paleta MapBiomas Coleção 10.

    caminho_qml : caminho completo do arquivo .qml a criar
    nivel       : None (todos os códigos) ou 1/2/3/4
                  (filtra apenas os códigos do nível selecionado)
    """
    # Filtrar por nível se solicitado
    if nivel is not None:
        from ..comum.legenda import CODIGOS_POR_NIVEL
        codigos_nivel = CODIGOS_POR_NIVEL.get(nivel, set(PALETA_C10.keys()))
        paleta = {k: v for k, v in PALETA_C10.items()
                  if k in codigos_nivel}
    else:
        paleta = PALETA_C10

    # Construir entradas paletteEntry
    entradas = []
    for cod in sorted(paleta.keys()):
        nome, cor, alpha = paleta[cod]
        entradas.append(
            f'        <paletteEntry value="{cod}" '
            f'color="#{cor}" alpha="{alpha}" '
            f'label="{cod} — {nome}"/>'
        )

    qml = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.22" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <pipe>
    <provider>
      <resampling enabled="false" maxOversampling="2"
        zoomedInResamplingMethod="nearestNeighbour"
        zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer type="paletted" band="1" opacity="1" nodataColor="">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <colorPalette>
{chr(10).join(entradas)}
      </colorPalette>
      <colorRamp type="randomcolors" name="Random Colors">
        <Option/>
      </colorRamp>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0"
      colorizeOn="0" colorizeRed="255" colorizeGreen="128"
      colorizeBlue="128" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
  <customproperties>
    <Option/>
  </customproperties>
</qgis>
"""
    with open(caminho_qml, 'w', encoding='utf-8') as f:
        f.write(qml)


def gerar_qml_junto_tif(path_tif):
    """
    Gera QML com o mesmo nome-base do TIF, na mesma pasta.
    Ex: 1985_CerradoSP.tif  →  1985_CerradoSP.qml
    """
    base     = os.path.splitext(path_tif)[0]
    path_qml = base + ".qml"
    gerar_qml(path_qml)
    return path_qml
