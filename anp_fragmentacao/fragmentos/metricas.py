"""
AnP — Fragmentos: motor de métricas por fragmento (patch-level).

Este módulo NÃO depende de GDAL/QGIS — só de numpy e scipy. Toda a
matemática das métricas mora aqui, para poder ser testada isoladamente
(fora do QGIS). A leitura do raster, a vetorização (GDAL Polygonize) e
a escrita do shapefile ficam em `processamento.py`.

Definições seguem as convenções FRAGSTATS/PyLandStats, para manter os
valores consistentes com o Módulo IV (Fragmentação) da suíte AnP:

- área (AREA)          = nº de pixels × área do pixel
- perímetro (PERIM)    = soma do comprimento das bordas de célula expostas
- área núcleo (CORE)   = pixels que sobram após erodir N anéis de borda
                         (N = profundidade de borda, em PIXELS)
- índice de forma      SHAPE = 0.25 · P / sqrt(A)      (=1 no quadrado)
- dimensão fractal     FRAC  = 2 · ln(0.25·P) / ln(A)  (∈ [1,2])
- circularidade        CIRC  = 4π·A / P²  (Polsby-Popper; =1 no círculo)
- vizinho mais próximo ENN   = menor distância borda-a-borda a outro fragmento
"""
import numpy as np
from scipy import ndimage


# ── Estruturas de vizinhança ──────────────────────────────────────────────────
def _estrutura(conn):
    """Elemento estruturante 4- ou 8-conexo (3×3)."""
    if int(conn) == 4:
        return np.array([[0, 1, 0],
                         [1, 1, 1],
                         [0, 1, 0]], dtype=bool)
    return np.ones((3, 3), dtype=bool)   # 8 (queen) — padrão


# ── Perímetro por rótulo (contagem de bordas de célula expostas) ───────────────
def _perimetro_por_rotulo(labeled, n_lab, res_x, res_y):
    """
    Soma, por rótulo, o comprimento das bordas expostas.
    Bordas verticais (vizinho esq./dir. diferente) medem res_y;
    bordas horizontais (vizinho sup./inf. diferente) medem res_x.
    Pixels na borda do array também contam como borda exposta.
    """
    per = np.zeros(n_lab + 1, dtype=np.float64)

    # Vizinhos à esquerda/direita → comprimento res_y
    for eixo, comp in ((1, res_y),):  # eixo das colunas
        # diferença com vizinho à direita
        dif = labeled[:, :-1] != labeled[:, 1:]
        for lab_side in (labeled[:, :-1][dif], labeled[:, 1:][dif]):
            c = np.bincount(lab_side.ravel(), minlength=n_lab + 1)
            per += c * comp
        # bordas do array (coluna 0 e última)
        for col in (labeled[:, 0], labeled[:, -1]):
            c = np.bincount(col.ravel(), minlength=n_lab + 1)
            per += c * comp

    # Vizinhos acima/abaixo → comprimento res_x
    dif = labeled[:-1, :] != labeled[1:, :]
    for lab_side in (labeled[:-1, :][dif], labeled[1:, :][dif]):
        c = np.bincount(lab_side.ravel(), minlength=n_lab + 1)
        per += c * res_x
    for lin in (labeled[0, :], labeled[-1, :]):
        c = np.bincount(lin.ravel(), minlength=n_lab + 1)
        per += c * res_x

    per[0] = 0.0   # fundo não tem perímetro
    return per


# ── Núcleo e nº de núcleos ─────────────────────────────────────────────────────
def _core_por_rotulo(mask, labeled, n_lab, struct, depth_px):
    """
    Erode a máscara em `depth_px` anéis de pixel e devolve, por rótulo:
      core_px[lab]  — nº de pixels de núcleo
      n_core[lab]   — nº de manchas de núcleo distintas dentro do fragmento
    """
    core_px = np.zeros(n_lab + 1, dtype=np.int64)
    n_core  = np.zeros(n_lab + 1, dtype=np.int64)

    if depth_px < 1:
        # profundidade 0 → núcleo = fragmento inteiro
        c = np.bincount(labeled.ravel(), minlength=n_lab + 1)
        core_px = c.astype(np.int64)
        core_px[0] = 0
        n_core[1:] = 1
        return core_px, n_core

    core_mask = ndimage.binary_erosion(
        mask, structure=struct, iterations=int(depth_px), border_value=0)
    if not core_mask.any():
        return core_px, n_core

    # nº de pixels de núcleo por fragmento
    labs_core = labeled[core_mask]
    core_px = np.bincount(labs_core.ravel(), minlength=n_lab + 1).astype(np.int64)
    core_px[0] = 0

    # nº de manchas de núcleo distintas por fragmento
    core_lab, _ = ndimage.label(core_mask, structure=struct)
    # para cada componente de núcleo, qual o fragmento-pai
    pares = np.stack([labeled[core_mask], core_lab[core_mask]], axis=1)
    if pares.size:
        pares = np.unique(pares, axis=0)          # (frag_id, core_comp)
        frags = pares[:, 0]
        cont = np.bincount(frags, minlength=n_lab + 1)
        n_core = cont.astype(np.int64)
        n_core[0] = 0
    return core_px, n_core


# ── Vizinho mais próximo (ENN, borda-a-borda) ──────────────────────────────────
def _enn_por_rotulo(labeled, n_lab, res_x, res_y, k=32):
    """
    Distância borda-a-borda ao fragmento mais próximo, por rótulo.
    Aproximação: considera as células de borda de cada fragmento e usa
    uma KDTree global, filtrando vizinhos do mesmo fragmento (até k).
    Para fragmentos muito grandes o valor pode ser superestimado — é uma
    métrica de conferência nesta primeira versão.
    """
    from scipy.spatial import cKDTree
    # células de borda: têm ao menos um vizinho (4-conex) de rótulo diferente
    dif = np.zeros(labeled.shape, dtype=bool)
    dif[:, :-1] |= labeled[:, :-1] != labeled[:, 1:]
    dif[:, 1:]  |= labeled[:, :-1] != labeled[:, 1:]
    dif[:-1, :] |= labeled[:-1, :] != labeled[1:, :]
    dif[1:, :]  |= labeled[:-1, :] != labeled[1:, :]
    borda = dif & (labeled > 0)

    enn = np.full(n_lab + 1, np.nan, dtype=np.float64)
    ys, xs = np.nonzero(borda)
    if ys.size < 2:
        return enn
    ids = labeled[ys, xs]
    pts = np.column_stack([xs * res_x, ys * res_y]).astype(np.float64)
    tree = cKDTree(pts)
    kk = min(k, pts.shape[0])
    dists, idxs = tree.query(pts, k=kk)
    if kk == 1:
        return enn
    viz_ids = ids[idxs]
    for i in range(pts.shape[0]):
        a = ids[i]
        for j in range(1, kk):
            if viz_ids[i, j] != a:
                d = dists[i, j]
                if np.isnan(enn[a]) or d < enn[a]:
                    enn[a] = d
                break
    return enn


# ── Métricas de forma (vetorizadas por rótulo) ─────────────────────────────────
def _formas(area_m2, perim_m):
    """SHAPE, FRAC e CIRC a partir de área (m²) e perímetro (m)."""
    with np.errstate(divide='ignore', invalid='ignore'):
        shape_idx = 0.25 * perim_m / np.sqrt(area_m2)
        frac = np.where(area_m2 > 1.0,
                        2.0 * np.log(0.25 * perim_m) / np.log(area_m2),
                        np.nan)
        circ = np.where(perim_m > 0,
                        4.0 * np.pi * area_m2 / (perim_m ** 2),
                        np.nan)
    return shape_idx, frac, circ


# ── Função principal (por máscara/classe) ─────────────────────────────────────
def metricas_de_mascara(mask, res_x, res_y, depth_px, conn=8,
                        classe=None, unidade=None, area_min_ha=0.0,
                        id_offset=0):
    """
    Rotula os fragmentos de `mask` e calcula as métricas de cada um.

    Parâmetros
    ----------
    mask        : array bool (True = pertence à classe/valor sob análise)
    res_x, res_y: tamanho do pixel em metros (x e y)
    depth_px    : profundidade de borda em PIXELS (núcleo)
    conn        : 8 (padrão) ou 4
    classe      : rótulo de classe a gravar em cada fragmento (opcional)
    unidade     : rótulo de unidade a gravar em cada fragmento (opcional)
    area_min_ha : descarta fragmentos menores que este valor (ha)
    id_offset   : deslocamento para o id global (encadear entre unidades)

    Retorna (labeled, registros, prox_offset):
      labeled     : int32 com o id GLOBAL de cada fragmento (0 = fora);
                    fragmentos abaixo de area_min_ha já saem zerados.
      registros   : lista de dicts (um por fragmento)
      prox_offset : id_offset + nº de fragmentos mantidos
    """
    struct = _estrutura(conn)
    px_ha = (res_x * res_y) / 10000.0

    labeled, n_lab = ndimage.label(mask, structure=struct)
    if n_lab == 0:
        return (np.zeros(mask.shape, dtype=np.int32), [], id_offset)

    labeled = labeled.astype(np.int32)
    area_px = np.bincount(labeled.ravel(), minlength=n_lab + 1).astype(np.int64)

    # filtro de tamanho mínimo — zera fragmentos pequenos ANTES das métricas
    if area_min_ha and area_min_ha > 0:
        min_px = area_min_ha / px_ha
        pequenos = np.where(area_px < min_px)[0]
        pequenos = pequenos[pequenos > 0]
        if pequenos.size:
            remover = np.isin(labeled, pequenos)
            labeled[remover] = 0
            mask = labeled > 0
            # re-rotula para ids contíguos
            labeled, n_lab = ndimage.label(mask, structure=struct)
            labeled = labeled.astype(np.int32)
            area_px = np.bincount(labeled.ravel(),
                                  minlength=n_lab + 1).astype(np.int64)
            if n_lab == 0:
                return (np.zeros(mask.shape, dtype=np.int32), [], id_offset)

    perim = _perimetro_por_rotulo(labeled, n_lab, res_x, res_y)
    core_px, n_core = _core_por_rotulo(mask, labeled, n_lab, struct, depth_px)
    enn = _enn_por_rotulo(labeled, n_lab, res_x, res_y)

    area_m2 = area_px.astype(np.float64) * (res_x * res_y)
    shape_idx, frac, circ = _formas(area_m2, perim)

    registros = []
    for lab in range(1, n_lab + 1):
        gid = id_offset + lab
        a_ha = area_px[lab] * px_ha
        c_ha = core_px[lab] * px_ha
        registros.append({
            'id_frag'  : gid,
            'classe'   : classe,
            'unidade'  : unidade,
            'area_ha'  : round(float(a_ha), 4),
            'perim_m'  : round(float(perim[lab]), 2),
            'core_ha'  : round(float(c_ha), 4),
            'n_core'   : int(n_core[lab]),
            'cai_pct'  : round(float(100.0 * c_ha / a_ha), 2) if a_ha > 0 else 0.0,
            'shape_idx': round(float(shape_idx[lab]), 4),
            'frac'     : (round(float(frac[lab]), 4)
                          if np.isfinite(frac[lab]) else None),
            'circ'     : (round(float(circ[lab]), 4)
                          if np.isfinite(circ[lab]) else None),
            'enn_m'    : (round(float(enn[lab]), 2)
                          if np.isfinite(enn[lab]) else None),
            '_lab_local': lab,   # uso interno (mapear id global no raster)
        })

    # remapeia o raster rotulado para o id GLOBAL
    if id_offset:
        labeled = np.where(labeled > 0, labeled + id_offset, 0).astype(np.int32)

    return labeled, registros, id_offset + n_lab
