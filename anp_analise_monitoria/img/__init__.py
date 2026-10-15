# AnP — Análise e Monitoria da Paisagem (plugin integrado)
# Preparação + Relatório + Monitoria  ·  v1.1
# Prof. Dr. Rodrigo Silva Lemos | DGPA/IGCE — Unesp Rio Claro


def classFactory(iface):
    from .plugin import AnPIntegradoPlugin
    return AnPIntegradoPlugin(iface)
