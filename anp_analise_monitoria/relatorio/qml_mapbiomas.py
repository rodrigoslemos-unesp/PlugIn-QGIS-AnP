"""
AnP — Relatório de Cobertura da Terra
Gerador de arquivo QML com a paleta oficial MapBiomas Coleção 10.

Mesma paleta validada e usada nos demais módulos do AnP (Preparação,
Monitoria) — fonte oficial: MapBiomas, Legenda-Colecao-10-Legend-Code.pdf.
"""
import os

PALETA_C10 = {
    1:  ("Floresta",                    "1F4E31", 255),
    3:  ("Formação Florestal",          "1F4E31", 255),
    4:  ("Formação Savânica",           "7DC36B", 255),
    5:  ("Mangue",                      "04381D", 255),
    6:  ("Floresta Alagável",           "026975", 255),
    49: ("Restinga Arbórea",            "02D659", 255),
    10: ("Veg. Herbácea e Arbustiva",   "AAD374", 255),
    11: ("Campo Alagado e Área Pantanosa","519799", 255),
    12: ("Formação Campestre",          "D6BC74", 255),
    29: ("Afloramento Rochoso",         "AD5100", 255),
    32: ("Apicum",                      "FF99FF", 255),
    50: ("Restinga Herbácea",           "D68FE5", 255),
    14: ("Agropecuária",                "FFEFC3", 255),
    9:  ("Silvicultura",                "935132", 255),
    15: ("Pastagem",                    "EDDE8E", 255),
    18: ("Agricultura",                 "E974ED", 255),
    21: ("Mosaico de Usos",             "FFEFC3", 255),
    19: ("Lavoura Temporária",          "C27BA0", 255),
    36: ("Lavoura Perene",              "C3814B", 255),
    39: ("Soja",                        "C3814B", 255),
    20: ("Cana-de-açúcar",              "DB7093", 255),
    40: ("Arroz",                       "9DC5A4", 255),
    62: ("Algodão (beta)",              "E1C4A4", 255),
    41: ("Outras Lavouras Temporárias", "C27BA0", 255),
    46: ("Café",                        "C8A06B", 255),
    47: ("Citrus",                      "FFC0CB", 255),
    35: ("Dendê",                       "A87C52", 255),
    48: ("Outras Lavouras Perenes",     "D4A96A", 255),
    22: ("Área não Vegetada",           "D4271E", 255),
    23: ("Praia, Duna e Areal",         "DD5F9B", 255),
    24: ("Área Urbanizada",             "D4271E", 255),
    25: ("Outras Áreas não Vegetadas",  "DB4D4F", 255),
    30: ("Mineração",                   "9C0027", 255),
    75: ("Usina Fotovoltaica (beta)",   "C12100", 255),
    26: ("Corpo D'água",                "2532E4", 255),
    31: ("Aquicultura",                 "091077", 255),
    33: ("Rio, Lago e Oceano",          "2532E4", 255),
    27: ("Não Observado",               "D3D2D2", 100),
    0:  ("NoData",                      "000000", 0),
}


def _esc_xml(txt):
    """Escapa caracteres especiais de XML em texto dinâmico do QML."""
    return (str(txt)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def gerar_qml(caminho_qml, codigos_presentes=None):
    """
    Gera QML paletted com a paleta oficial MapBiomas C10.

    codigos_presentes: se fornecido (iterável de códigos int), limita
    a paleta apenas a esses códigos — evita listar 40 classes num
    raster que só usa 8, mantendo o QML enxuto e rápido de carregar.
    """
    paleta = PALETA_C10
    if codigos_presentes is not None:
        codigos = set(int(c) for c in codigos_presentes) | {0}
        paleta = {k: v for k, v in PALETA_C10.items() if k in codigos}

    entradas = []
    for cod in sorted(paleta.keys()):
        nome, cor, alpha = paleta[cod]
        entradas.append(
            f'        <paletteEntry value="{cod}" color="#{cor}" '
            f'alpha="{alpha}" label="{_esc_xml(nome)}"/>'
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
  <customproperties><Option/></customproperties>
</qgis>
"""
    with open(caminho_qml, 'w', encoding='utf-8') as f:
        f.write(qml)


def gerar_qml_junto_tif(path_tif, codigos_presentes=None):
    """Gera QML com o mesmo nome-base do TIF, na mesma pasta."""
    base = os.path.splitext(path_tif)[0]
    path_qml = base + ".qml"
    gerar_qml(path_qml, codigos_presentes)
    return path_qml
