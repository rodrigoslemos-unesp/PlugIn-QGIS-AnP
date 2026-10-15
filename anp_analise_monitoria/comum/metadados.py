# -*- coding: utf-8 -*-
"""
AnP Integrado — geração PADRONIZADA da aba "Metadados e Como Citar".

Todo módulo que gera Excel usa escrever_metadados(), de modo que:
  • o bloco geral (institucional) é IDÊNTICO em todos os resultados;
  • os parâmetros específicos da rodada aparecem abaixo, para reprodutibilidade;
  • existe UMA única redação de "Como Citar", na mesma aba, igual em todos os arquivos.

Usa exclusivamente o motor xlsx_writer (sem openpyxl).
"""

# ── Metadados gerais (institucionais) — fonte única da verdade ────────────────
VERSAO_SUITE  = "1.1"
AUTOR         = "Prof. Dr. Rodrigo Silva Lemos"
INSTITUICAO   = ("Departamento de Geografia e Planejamento Ambiental "
                 "(DGPA/IGCE) — Unesp, Câmpus Rio Claro")
GRUPO         = ("Grupo de Pesquisa Planejamento Ambiental e Dinâmicas "
                 "da Paisagem (CNPq)")
REPOSITORIO   = "https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP"
FONTE_DADOS   = ("MapBiomas — Coleção 10 da Série Anual de Mapas de "
                 "Cobertura e Uso da Terra do Brasil")

AVISO = (
    "\u26a0 SOFTWARE EM DESENVOLVIMENTO — Este plugin está em fase de testes e "
    "aprimoramento contínuo. Os resultados devem ser conferidos e validados "
    "pelo usuário antes de qualquer uso científico, técnico ou institucional. "
    "O autor e a instituição não se responsabilizam por eventuais erros, "
    "omissões, imprecisões ou uso indevido dos resultados gerados por esta "
    "ferramenta."
)

NOTA_CRS = (
    "Métricas de área absoluta (ha/km²) só são válidas em CRS projetado "
    "(metros). Em CRS geográfico (graus), a área é estimada por um pixel de "
    "30 m fixo e pode superestimar valores (~8% na latitude de São Paulo); "
    "os percentuais não são afetados. Recomenda-se rodar a Preparação com "
    "reprojeção (ex.: EPSG:31983) antes das análises."
)

CABECALHO = "AnP — Análise e Monitoria da Paisagem"

# ── Como Citar — redação única ────────────────────────────────────────────────
CITACAO_ANP = (
    "LEMOS, Rodrigo Silva. AnP — Análise da Paisagem: conjunto de plugins QGIS "
    "para análise de cobertura e uso da terra e fragmentação de paisagens "
    "naturais. Rio Claro: Departamento de Geografia e Planejamento Ambiental, "
    "IGCE — Unesp, 2025. Disponível em: "
    "https://github.com/rodrigoslemos-unesp/PlugIn-QGIS-AnP. "
    "DOI: 10.5281/zenodo.21364767")
CITACAO_MAPBIOMAS = (
    "MAPBIOMAS. Coleção 10 da Série Anual de Mapas de Cobertura e Uso da Terra "
    "do Brasil. São Paulo: MapBiomas, 2025. Disponível em: https://mapbiomas.org.")
OBS_CITACAO = ("Recomenda-se citar as duas fontes: os dados (MapBiomas) e o "
               "software (AnP).")

NOME_ABA = "Metadados e Como Citar"
_LARG_A, _LARG_B = 24, 92


def _altura(texto, largura):
    """Altura de linha (pt) para o texto quebrado caber na coluna."""
    import math
    linhas = max(1, math.ceil(len(str(texto)) * 1.05 / largura))
    return max(15, 13.5 * linhas + 3)


def escrever_metadados(wb, titulo_modulo, params=None):
    """
    Cria a aba única 'Metadados e Como Citar' (sempre a primeira do arquivo):
    cabeçalho, aviso, metadados institucionais, parâmetros desta análise e
    as referências para citação (AnP e MapBiomas).
    `params`: lista opcional de (rótulo, valor) com os parâmetros da rodada.
    """
    ws = wb.add_sheet(NOME_ABA)
    ws.set_col_width(1, _LARG_A)
    ws.set_col_width(2, _LARG_B)

    def linha(r, rotulo, valor, negrito=True, cor=None):
        if cor:
            ws.write(r, 1, rotulo, color=cor)
            ws.write(r, 2, valor, color=cor)
        else:
            ws.write(r, 1, rotulo, bold=negrito, align=None if negrito else 'left')
            ws.write(r, 2, valor, align='left')
        ws.set_row_height(r, max(_altura(rotulo, _LARG_A - 2),
                                 _altura(valor, _LARG_B)))

    ws.write(1, 1, CABECALHO, bold=True)
    ws.write(1, 2, f"Módulo: {titulo_modulo}  ·  v{VERSAO_SUITE}", bold=True)
    ws.set_row_height(1, _altura(CABECALHO, _LARG_A - 2))

    linha(3, "AVISO", AVISO, cor="FFFF00")

    r = 4
    for k, v in [("Autor", AUTOR),
                 ("Instituição", INSTITUICAO),
                 ("Grupo de pesquisa", GRUPO),
                 ("Repositório", REPOSITORIO),
                 ("Fonte dos dados", FONTE_DADOS),
                 ("Nota sobre CRS/área", NOTA_CRS)]:
        linha(r, k, v); r += 1

    r += 1
    ws.write(r, 1, "PARÂMETROS DESTA ANÁLISE", bold=True, align='left')
    ws.write(r, 2, "", align='left')
    r += 1
    for k, v in (params or []):
        linha(r, str(k), "" if v is None else str(v)); r += 1

    linha(r, "Como Citar", CITACAO_ANP, negrito=False);              r += 1
    linha(r, "OBS.:", OBS_CITACAO, negrito=False);                    r += 1
    linha(r, "Como Citar o MapBiomas", CITACAO_MAPBIOMAS, negrito=False)
    return ws
