"""
AnP — Gerador de QML e raster de mudanças de cobertura.
Formato QML compatível com QGIS 3.x (paletteEntry, não item).
"""

from ..comum.legenda import (
    CAT_NATURAL_NATURAL, CAT_ANTROP_ANTROP,
    CAT_ENTRE_NATURAIS,  CAT_ENTRE_ANTROP,
    CAT_ANTROP_NATURAL,  CAT_NATURAL_ANTROP)

# valor raster → (label, cor_hex_minúscula, alpha)
# Paleta de alto contraste — máxima separação visual no mapa
CATEGORIAS_RASTER = [
    (0, "Sem mudança / Nodata",               "ffffff",  0),
    (1, CAT_NATURAL_NATURAL,                   "388e3c", 255),  # verde médio
    (2, CAT_ANTROP_ANTROP,                     "f57c00", 255),  # laranja
    (3, CAT_ENTRE_NATURAIS,                    "aed581", 255),  # verde lima
    (4, CAT_ENTRE_ANTROP,                      "9c27b0", 255),  # roxo
    (5, CAT_ANTROP_NATURAL,                    "1976d2", 255),  # azul
    (6, CAT_NATURAL_ANTROP,                    "d32f2f", 255),  # vermelho
]


def gerar_qml(caminho_qml, ano1, ano2):
    """
    Gera QML compatível com QGIS 3.16+.
    Usa <paletteEntry> dentro de <colorPalette> — formato exigido pelo QGIS.
    """
    entradas = '\n'.join(
        f'        <paletteEntry value="{val}" '
        f'color="#{cor}" alpha="{alpha}" '
        f'label="{label}"/>'
        for val, label, cor, alpha in CATEGORIAS_RASTER
    )

    qml = f'''<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
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
{entradas}
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
'''
    with open(caminho_qml, 'w', encoding='utf-8') as f:
        f.write(qml)


def gerar_raster_mudancas(arr1, arr2, nodata, gt, proj,
                           caminho_tif, progresso_fn=None):
    """
    Gera raster de categorias de mudança (uint8, valores 1–6, 0=nodata).
    Categorias:
      1 = Manteve-se em cobertura natural
      2 = Manteve-se em cobertura antrópica
      3 = Mudou entre coberturas naturais
      4 = Mudou entre coberturas antrópicas
      5 = Mudou de antrópico para natural
      6 = Mudou de natural para antrópico
      0 = Nodata
    """
    import numpy as np
    from osgeo import gdal
    from ..comum.legenda import CLASSES_NATURAIS, CLASSES_EXCLUIR

    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    excluir = set(CLASSES_EXCLUIR)
    if nodata is not None:
        excluir.add(int(nodata))

    rows, cols = arr1.shape
    out = np.zeros((rows, cols), dtype=np.uint8)

    mask = (
        (arr1 > 0) & (arr2 > 0) &
        (~np.isin(arr1, list(excluir))) &
        (~np.isin(arr2, list(excluir))))

    a1 = arr1[mask]
    a2 = arr2[mask]

    nat1  = np.isin(a1, list(CLASSES_NATURAIS))
    nat2  = np.isin(a2, list(CLASSES_NATURAIS))
    igual = (a1 == a2)

    cat = np.zeros(a1.shape, dtype=np.uint8)
    cat[igual  &  nat1]          = 1
    cat[igual  & ~nat1]          = 2
    cat[~igual &  nat1 &  nat2]  = 3
    cat[~igual & ~nat1 & ~nat2]  = 4
    cat[~igual & ~nat1 &  nat2]  = 5
    cat[~igual &  nat1 & ~nat2]  = 6
    out[mask] = cat

    drv = gdal.GetDriverByName('GTiff')
    ds  = drv.Create(caminho_tif, cols, rows, 1, gdal.GDT_Byte,
                     options=['COMPRESS=LZW', 'TILED=YES'])
    ds.SetGeoTransform(gt)
    ds.SetProjection(proj)
    b = ds.GetRasterBand(1)
    b.SetNoDataValue(0)
    b.WriteArray(out)
    b.FlushCache()
    ds = None

    fname = caminho_tif.replace('\\', '/').split('/')[-1]
    prog(f"  ✓ Raster: {fname}")
    return caminho_tif
