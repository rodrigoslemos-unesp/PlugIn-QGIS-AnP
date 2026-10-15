# AnP — Fragmentação da Paisagem (plugin integrado)
# Fragmentação temporal + Análise de fragmentos  ·  v1.1
# Prof. Dr. Rodrigo Silva Lemos | DGPA/IGCE — Unesp Rio Claro
def classFactory(iface):
    from .plugin import AnPFragmentacaoPlugin
    return AnPFragmentacaoPlugin(iface)
