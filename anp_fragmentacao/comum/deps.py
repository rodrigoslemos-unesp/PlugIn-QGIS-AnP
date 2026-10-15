# -*- coding: utf-8 -*-
"""
AnP — Fragmentação: checagem CONTEXTUAL de dependências, SEM instalar via pip.
Cada estrutura declara o que precisa; a análise de fragmentos exige só scipy,
a temporal exige também PyLandStats. Nunca chama pip (o erro típico de NumPy
'failed to import' vem justamente de instalar/atualizar pacote por fora).
"""
import sys, os, importlib.util

# perfis de dependência por estrutura
DEPS = {
    "temporal": [
        ("numpy",       "numpy — arrays raster (vem com o QGIS)"),
        ("scipy",       "scipy — erosão morfológica (área núcleo)"),
        ("pylandstats", "pylandstats — métricas de fragmentação"),
    ],
    "fragmentos": [
        ("numpy", "numpy — arrays raster (vem com o QGIS)"),
        ("scipy", "scipy — rotulagem, erosão (núcleo) e vizinho mais próximo"),
    ],
}


def faltando(estrutura):
    return [(imp, rot) for imp, rot in DEPS.get(estrutura, [])
            if importlib.util.find_spec(imp) is None]


def _python_real():
    exe = sys.executable
    if 'qgis' not in os.path.basename(exe).lower():
        return exe
    for c in (os.path.join(os.path.dirname(exe), 'python3.exe'),
              os.path.join(os.path.dirname(exe), 'python.exe')):
        if os.path.exists(c):
            return c
    return exe


def mensagem(faltas):
    pk = " ".join(imp for imp, _ in faltas)
    cmd = f'"{_python_real()}" -m pip install {pk}'
    linhas = ["Faltam bibliotecas Python para esta estrutura:", ""]
    for imp, rot in faltas:
        linhas.append(f"  • {rot}")
    linhas += ["", "COMO INSTALAR (no OSGeo4W Shell, com o QGIS fechado):",
               "", f"   {cmd}", "",
               "Depois reabra o QGIS. Não instale pelo cmd comum do Windows —",
               "isso pode quebrar o NumPy do QGIS."]
    return "\n".join(linhas)
