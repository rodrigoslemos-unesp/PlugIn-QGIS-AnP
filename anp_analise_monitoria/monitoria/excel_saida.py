"""
AnP — Geração das planilhas Excel de saída.
Saídas: ano1_ano2_monitoria.xlsx | ano1_ano2_Matriz.xlsx
Suporta ha, km² e percentual; adapta-se a CRS não projetado.
"""

import os, math
from ..comum.xlsx_writer import XlsxBook
from ..comum.metadados import escrever_metadados, VERSAO_SUITE
from ..comum.legenda import (LEGENDA, CORES_CATEGORIA, TEXTO_BRANCO_CAT,
                      CAT_NATURAL_NATURAL, CAT_ANTROP_ANTROP,
                      CAT_ENTRE_NATURAIS, CAT_ENTRE_ANTROP,
                      CAT_ANTROP_NATURAL, CAT_NATURAL_ANTROP)

# CRED removido — creditação consta apenas no aplicativo, não nos produtos.
# Deixava uma linha de texto solta na área de dados do Excel (fora do
# cabeçalho), que readxl/openpyxl liam como parte dos dados, gerando
# avisos de tipo e podendo confundir ferramentas de análise externas.

COR_A = "F5F5F5"
COR_B = "FFFFFF"


def _aba_metadados(wb, resultado, ano1, ano2, titulo_modulo):
    """Aba de metadados — sempre a primeira do arquivo, com aviso de
    software em desenvolvimento bem destacado."""
    ws = wb.add_sheet("Metadados")
    ws.set_col_width(1, 22)
    ws.set_col_width(2, 90)

    ws.write(1, 1, titulo_modulo, bold=True)
    ws.write(1, 2, f"v{VERSAO_SUITE}", bold=True)

    aviso_txt = (
        "⚠ SOFTWARE EM DESENVOLVIMENTO — Este plugin está em fase de "
        "testes e aprimoramento contínuo. Os resultados devem ser "
        "conferidos e validados pelo usuário antes de qualquer uso "
        "científico, técnico ou institucional. O autor e a instituição "
        "não se responsabilizam por eventuais erros, omissões, "
        "imprecisões ou uso indevido dos resultados gerados por esta "
        "ferramenta.")
    ws.write(3, 1, "AVISO", color="FFF3E0", bold=True)
    ws.write(3, 2, aviso_txt, color="FFF3E0")

    ws.write(5, 1, "Anos analisados", bold=True)
    ws.write(5, 2, f"{ano1} → {ano2}")

    avisos = resultado.get('avisos', [])
    ws.write(6, 1, "Observações de CRS", bold=True)
    ws.write(6, 2, " | ".join(avisos) if avisos else
            "CRS projetado — área calculada exatamente do geotransform")

    n_recortes = len([k for k, v in resultado.items()
                      if isinstance(v, dict) and 'tab_cob' in v])
    ws.write(7, 1, "Unidades de análise", bold=True)
    ws.write(7, 2, str(n_recortes))


def _aba_como_citar(wb):
    """Aba com orientação de citação — MapBiomas e AnP como software."""
    ws = wb.add_sheet("Como_Citar")
    ws.set_col_width(1, 100)
    linhas = [
        "COMO CITAR OS DADOS DESTE RELATÓRIO",
        "",
        "Este relatório foi gerado a partir de dados de cobertura e uso "
        "da terra do projeto MapBiomas. Ao utilizar estes dados, cite a "
        "fonte primária:",
        "",
        "MAPBIOMAS. Coleção 10 da Série Anual de Mapas de Cobertura e Uso "
        "da Terra do Brasil. São Paulo: MapBiomas, 2025. "
        "Disponível em: https://mapbiomas.org.",
        "",
        "Se este relatório for citado como produto metodológico (citando "
        "o processamento realizado, não apenas os dados brutos), a "
        "referência do software é:",
        "",
        "LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de "
        "plugins QGIS para análise de cobertura e uso da terra e "
        "fragmentação de paisagens naturais. Rio Claro: Departamento de "
        "Geografia e Planejamento Ambiental, IGCE — Unesp, 2025. "
        "Disponível em: https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. "
        "DOI: 10.5281/zenodo.21364767",
    ]
    for i, txt in enumerate(linhas, 2):
        ws.write(i, 1, txt, header=(i == 2))

# Ordem das categorias na Matriz
ORDEM_CAT = [
    CAT_NATURAL_NATURAL, CAT_ANTROP_ANTROP,
    CAT_ENTRE_NATURAIS,  CAT_ENTRE_ANTROP,
    CAT_ANTROP_NATURAL,  CAT_NATURAL_ANTROP,
]


def _hdr(ws, col, texto, largura):
    ws.write(1, col, texto, header=True)
    ws.set_col_width(col, largura)


def _converter_area(ha, modo):
    """Converte área de ha para o modo solicitado."""
    if modo == 'ha':
        return round(ha, 4)
    elif modo == 'km2':
        return round(ha / 100, 6)
    return None  # pct não usa área


def _col_area_label(modo):
    if modo == 'ha':  return 'area_ha'
    if modo == 'km2': return 'area_km2'
    return None


def _aba_cobertura(wb, dados, ano1, ano2, modo):
    """
    Aba Cobertura — tidy.
    Colunas variam conforme modo (ha | km2 | pct | ha_km2_pct).
    """
    ws = wb.add_sheet("Cobertura")

    # Definir colunas conforme modo
    hdrs_base = [
        ("grupo", 20), ("classe", 30), ("cod_classe", 11),
        ("ano", 7), ("unidade_analise", 30)]

    hdrs_area = []
    if 'ha' in modo:
        hdrs_area.append(("area_ha", 14))
    if 'km2' in modo:
        hdrs_area.append(("area_km2", 14))
    hdrs_area.append(("percentual", 12))

    hdrs = hdrs_base + hdrs_area
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    row = 2
    for nome_unidade, d in dados.items():
        # Pular apenas entradas que não são dicts de recorte válidos
        if not isinstance(d, dict) or 'tab_cob' not in d:
            continue
        lbl  = 'Shape Completo' if nome_unidade == '__shape_completo__' \
               else nome_unidade
        tab  = d.get('tab_cob', [])
        tot1 = sum(ln['ha1'] for ln in tab) or 1
        tot2 = sum(ln['ha2'] for ln in tab) or 1

        for ln in tab:
            for ano_lbl, ha, pct in [
                (str(ano1), ln['ha1'], ln['pct1']),
                (str(ano2), ln['ha2'], ln['pct2'])
            ]:
                shade = COR_A if row % 2 == 0 else COR_B
                col_i = 1
                ws.write(row, col_i, ln['grupo'],   color=shade); col_i+=1
                ws.write(row, col_i, ln['nome'],    color=shade); col_i+=1
                ws.write(row, col_i, ln['cod'],     color=shade); col_i+=1
                ws.write(row, col_i, int(ano_lbl), color=shade); col_i+=1
                ws.write(row, col_i, lbl,          color=shade); col_i+=1
                if 'ha' in modo:
                    ws.write(row, col_i, round(ha,4) if ha else '',
                             color=shade,
                             num_fmt='num' if ha else None); col_i+=1
                if 'km2' in modo:
                    v_km2 = round(ha/100, 6) if ha else ''
                    ws.write(row, col_i, v_km2,
                             color=shade,
                             num_fmt='num' if v_km2 else None); col_i+=1
                ws.write(row, col_i, round(pct,6) if pct else '',
                         color=shade,
                         num_fmt='pct' if pct else None)
                row += 1



def _aba_alteracoes(wb, dados, ano1, ano2, modo):
    """
    Aba Alteracoes — tidy.
    Cada linha recebe a cor de fundo da categoria de mudança.
    """
    ws = wb.add_sheet("Alteracoes")

    hdrs_base = [
        ("cod_orig",9), ("classe_orig",28),
        ("cod_dest",9), ("classe_dest",28),
        ("cod_trans",11), ("categoria",38),
        ("unidade_analise",30)]

    hdrs_area = []
    if 'ha' in modo:
        hdrs_area.append(("area_ha", 14))
    if 'km2' in modo:
        hdrs_area.append(("area_km2", 14))
    hdrs_area.append(("percentual", 12))

    hdrs = hdrs_base + hdrs_area
    n_cols = len(hdrs)
    for col, (h, w) in enumerate(hdrs, 1):
        _hdr(ws, col, h, w)
    ws.set_row_height(1, 26)

    row = 2
    for nome_unidade, d in dados.items():
        if not isinstance(d, dict) or 'tab_trans' not in d:
            continue
        lbl  = 'Shape Completo' if nome_unidade == '__shape_completo__' \
               else nome_unidade
        tab  = d.get('tab_trans', [])
        tot  = sum(ln['area_ha'] for ln in tab) or 1

        for ln in tab:
            cat   = ln.get('categoria', '')
            # Cor da categoria — definida em legenda.CORES_CATEGORIA
            shade = CORES_CATEGORIA.get(cat, 'F5F5F5')
            col_i = 1
            ws.write(row, col_i, ln['cod_orig'],   color=shade); col_i+=1
            ws.write(row, col_i, ln['nome_orig'],  color=shade); col_i+=1
            ws.write(row, col_i, ln['cod_dest'],   color=shade); col_i+=1
            ws.write(row, col_i, ln['nome_dest'],  color=shade); col_i+=1
            ws.write(row, col_i, ln['cod_trans'],  color=shade); col_i+=1
            ws.write(row, col_i, cat,             color=shade); col_i+=1
            ws.write(row, col_i, lbl,             color=shade); col_i+=1
            ha = ln['area_ha']
            if 'ha' in modo:
                ws.write(row, col_i, round(ha,4),
                         color=shade, num_fmt='num'); col_i+=1
            if 'km2' in modo:
                ws.write(row, col_i, round(ha/100,6),
                         color=shade, num_fmt='num'); col_i+=1
            ws.write(row, col_i, round(ha/tot,6),
                     color=shade, num_fmt='pct')
            row += 1




def _matriz_bloco(ws, tab_trans, ano1, ano2, modo, r0):
    """
    Escreve uma matriz a partir da linha r0.
    Retorna a próxima linha livre após a matriz.
    Layout:
      r0+0: título (largura total)
      r0+1: vazio | vazio | "Classe {ano2}" ← span sobre colunas destino
      r0+2: Cód(ano1) | Classe(ano1) | [nomes das classes 2024]
      r0+3+: dados (diagonal em vermelho)
    """
    todas = sorted({ln['cod_orig'] for ln in tab_trans} |
                   {ln['cod_dest'] for ln in tab_trans})
    vals  = {(ln['cod_orig'], ln['cod_dest']): ln['area_ha']
             for ln in tab_trans}
    tot_p = sum(ln['area_ha'] for ln in tab_trans) or 1
    tot_o = {}
    for (o, d), ha in vals.items():
        tot_o[o] = tot_o.get(o, 0) + ha
    n = len(todas)

    eh_pct = (modo == 'pct_orig')
    ul = ('% da origem' if eh_pct else
          'ha' if 'ha' in modo else 'km²')

    # Linha título
    r = r0
    ws.write(r, 1, f"Matriz de Transição | {ano1} → {ano2} | {ul}",
             header=True)
    for c in range(2, n + 3):
        ws.write(r, c, '', header=True)
    ws.set_row_height(r, 20)
    r += 1

    # Linha "Classe {ano2}" — span sobre colunas de destino
    ws.write(r, 1, '', header=True)
    ws.write(r, 2, '', header=True)
    ws.write(r, 3, f'Classe {ano2}', header=True)
    for c in range(4, n + 3):
        ws.write(r, c, '', header=True)
    ws.set_row_height(r, 18)
    r += 1

    # Linha cabeçalho de colunas
    ws.write(r, 1, f'Cód ({ano1})',    header=True)
    ws.write(r, 2, f'Classe ({ano1})', header=True)
    for j, cls in enumerate(todas, 3):
        ws.write(r, j, LEGENDA.get(cls, str(cls)), header=True)
    ws.set_row_height(r, 40)
    r += 1

    # Dados
    COR_D = 'C62828'
    for i, o in enumerate(todas):
        shade = COR_A if i % 2 == 0 else COR_B
        ws.write(r, 1, o,                      color=shade)
        ws.write(r, 2, LEGENDA.get(o, str(o)), color=shade)
        to = tot_o.get(o, 1) or 1
        for j, d in enumerate(todas, 3):
            ha = vals.get((o, d))
            cs = COR_D if o == d else shade
            if ha is None:
                ws.write(r, j, '', color=cs)
            elif eh_pct:
                ws.write(r, j, round(ha / to, 6), color=cs, num_fmt='pct')
            elif 'ha' in modo:
                ws.write(r, j, round(ha, 4), color=cs, num_fmt='num')
            else:
                ws.write(r, j, round(ha / 100, 6), color=cs, num_fmt='num')
        r += 1

    return r


def _aba_matriz(wb, nome_aba, tab_trans, ano1, ano2, modo):
    """
    Uma aba por unidade de análise.
    Contém duas matrizes empilhadas:
      1. Área (ha ou km²) com nota explicativa
      2. % da área de origem com nota explicativa
    Cabeçalho 'Classe {ano2}' em linha própria sobre as colunas destino.
    Diagonal em vermelho — indica permanência na mesma classe.
    """
    ws = wb.add_sheet(nome_aba)   # add_sheet() já limita a 31 caracteres
    n  = len(sorted({ln['cod_orig'] for ln in tab_trans} |
                    {ln['cod_dest'] for ln in tab_trans}))

    ws.set_col_width(1, 10)
    ws.set_col_width(2, 28)
    for j in range(3, n + 3):
        ws.set_col_width(j, 14)

    ul = 'ha' if 'ha' in modo else 'km²'

    # ── Bloco 1: área ────────────────────────────────────────────────────
    r = _matriz_bloco(ws, tab_trans, ano1, ano2, modo, 1)
    r += 1  # linha em branco

    nota1 = (f"Interpretação: cada célula indica a área ({ul}) que pertencia "
             f"à classe da linha ({ano1}) e passou à classe da coluna ({ano2}). "
             f"A diagonal (vermelho) = área que permaneceu na mesma classe nos "
             f"dois períodos. A soma de cada linha = área total da classe em {ano1}.")
    ws.write(r, 1, nota1)
    ws.set_row_height(r, 40)
    r += 2

    # ── Bloco 2: % da origem ─────────────────────────────────────────────
    r = _matriz_bloco(ws, tab_trans, ano1, ano2, 'pct_orig', r)
    r += 1

    nota2 = (f"Interpretação: cada célula indica o percentual da área da "
             f"classe de origem (linha, {ano1}) que se converteu para a "
             f"classe da coluna ({ano2}). A soma de cada linha = 100% da "
             f"classe de origem. A diagonal (vermelho) = taxa de permanência.")
    ws.write(r, 1, nota2)
    ws.set_row_height(r, 40)
    r += 2

    # Nome completo da unidade — o nome da aba é limitado a 31 caracteres
    # pelo Excel; esta linha preserva o nome integral para leitura posterior
    # (ex: script R de visualizações).
    ws.write(r, 1, "Unidade de análise:", header=True)
    ws.write(r, 2, nome_aba)




def _params_moni(resultado, ano1, ano2, modo):
    n = len([k for k, v in resultado.items()
             if isinstance(v, dict) and 'tab_cob' in v])
    av = resultado.get('avisos', [])
    crs = " | ".join(av) if av else ("CRS projetado — área exata do geotransform")
    modos = {'ha': 'hectares', 'km2': 'km²', 'pct': 'percentual',
             'ha_km2_pct': 'ha + km² + percentual'}
    return [("Anos analisados", f"{ano1} \u2192 {ano2}"),
            ("Unidades de análise", n),
            ("Modo de área", modos.get(modo, modo)),
            ("Observações de CRS", crs)]


def exportar(resultado, pasta, ano1, ano2, modo='ha',
             progresso_fn=None):
    """
    Gera dois arquivos Excel.
    modo: 'ha' | 'km2' | 'pct' | 'ha_km2_pct'
    """
    def prog(msg):
        if progresso_fn: progresso_fn(msg)

    # Avisos de CRS
    for av in resultado.get('avisos', []):
        prog(f"⚠ {av}")

    # Separar metadados dos dados de recortes
    # Incluir apenas entradas que sejam dicts com tab_cob (recortes reais)
    # Incluir apenas recortes válidos (dicts com tab_cob)
    dados_ord = {k: v for k, v in resultado.items()
                 if isinstance(v, dict) and 'tab_cob' in v}

    # ── monitoria.xlsx ────────────────────────────────────────────────────
    prog("  Gerando monitoria.xlsx...")
    wb1 = XlsxBook()
    escrever_metadados(wb1, "Monitoria de Cobertura da Terra",
                       params=_params_moni(resultado, ano1, ano2, modo))
    _aba_cobertura(wb1, dados_ord, ano1, ano2, modo)
    _aba_alteracoes(wb1, dados_ord, ano1, ano2, modo)
    p1  = os.path.join(pasta, f"{ano1}_{ano2}_monitoria.xlsx")
    wb1.save(p1)
    prog(f"  ✓ {os.path.basename(p1)}")

    # ── Matriz.xlsx ──────────────────────────────────────────────────────
    prog("  Gerando Matriz.xlsx...")
    wb2 = XlsxBook()
    escrever_metadados(wb2, "Matriz de Transição",
                       params=_params_moni(resultado, ano1, ano2, modo))
    for nome, d in dados_ord.items():
        if not isinstance(d, dict):
            continue
        lbl   = 'Shape Completo' if nome == '__shape_completo__' else nome
        tab_t = d.get('tab_trans', [])
        if tab_t:
            _aba_matriz(wb2, lbl, tab_t, ano1, ano2, modo)
            prog(f"  ✓ Matriz: {lbl}")
    p2 = os.path.join(pasta, f"{ano1}_{ano2}_Matriz.xlsx")
    wb2.save(p2)
    prog(f"  ✓ {os.path.basename(p2)}")

    return [p1, p2]
