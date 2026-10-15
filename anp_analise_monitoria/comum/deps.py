# -*- coding: utf-8 -*-
"""
AnP Integrado — checagem leve de dependências, SEM instalação automática.
Os módulos de Análise e Monitoria (Preparação, Relatório, Monitoria) usam
apenas GDAL e numpy, que já vêm no QGIS — então, na prática, nada falta.
A função existe para manter o padrão da suíte e proteger contra ambientes
atípicos. Nunca chama pip (decisão de projeto: pip automático já causou
travamentos e janelas de console no Windows).
"""
import importlib.util

# (import_name, rótulo)
DEPS_BASICAS = [
    ("osgeo", "GDAL/OGR (vem com o QGIS)"),
    ("numpy", "numpy (vem com o QGIS)"),
]


def faltando(deps=None):
    deps = deps or DEPS_BASICAS
    return [(imp, rot) for imp, rot in deps
            if importlib.util.find_spec(imp) is None]


def mensagem(faltas):
    linhas = ["Bibliotecas Python não encontradas neste QGIS:", ""]
    for imp, rot in faltas:
        linhas.append(f"  • {imp} — {rot}")
    linhas += ["",
               "Normalmente elas já acompanham o QGIS. Se estiver faltando, "
               "reinstale o QGIS pela distribuição oficial (OSGeo4W) ou "
               "instale manualmente no Python do QGIS."]
    return "\n".join(linhas)
