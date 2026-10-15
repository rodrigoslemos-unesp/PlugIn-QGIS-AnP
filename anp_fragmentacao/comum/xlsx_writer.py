"""
MACE v2.8.1 — Escritor xlsx puro Python.
Correção: fontes pretas para fundos claros, brancas para fundos escuros.
"""

import zipfile, io, re
from collections import OrderedDict


def _esc(s):
    if s is None: return ''
    s = str(s)
    for a, b in [('&','&amp;'),('<','&lt;'),('>','&gt;'),
                 ('"','&quot;'),("'","&apos;")]:
        s = s.replace(a, b)
    return s


def _luminance(hex6):
    """Luminância relativa de uma cor hex — decide fonte preta ou branca."""
    r = int(hex6[0:2], 16)
    g = int(hex6[2:4], 16)
    b = int(hex6[4:6], 16)
    return 0.299*r + 0.587*g + 0.114*b


# Paleta completa: cor → (índice no fills, fonte branca?)
_COLORS = {
    '1F3864': (2,  True ),   # azul escuro header
    '2E5F8A': (3,  True ),   # azul médio
    '1565C0': (4,  True ),   # azul cls
    '37474F': (5,  True ),   # cinza escuro
    'D6E4F0': (6,  False),   # azul claro
    'F5F5F5': (7,  False),   # cinza claro zebra A
    'C8E6C9': (8,  False),   # verde claro
    'FFCCBC': (9,  False),   # laranja claro
    'A5D6A7': (10, False),   # verde claro médio
    'EF9A9A': (11, False),   # vermelho claro
    'BBDEFB': (12, False),   # azul claro
    'FFCC80': (13, False),   # laranja médio
    '388E3C': (14, True ),   # cat 1: verde médio — manteve natural
    'F57C00': (15, True ),   # cat 2: laranja — manteve antrópico
    'AED581': (16, False),   # cat 3: verde lima — entre naturais
    '9C27B0': (17, True ),   # cat 4: roxo — entre antrópicos
    '1976D2': (18, True ),   # cat 5: azul — antrópico→natural
    'D32F2F': (19, True ),   # cat 6: vermelho — natural→antrópico
    'C62828': (20, True ),   # vermelho diagonal matriz
    'FFFDE7': (21, False),   # amarelo clarissimo
    'FFFFFF': (22, False),   # branco zebra B
    'FFFF00': (23, False),   # amarelo — destaque do AVISO (Metadados)
}

_PALETTE_ORDER = list(_COLORS.keys())  # manter ordem dos fills

# Número de xf fixos antes dos coloridos
_XF_DEFAULT  = 0   # default texto preto
_XF_BOLD     = 1   # bold preto
_XF_NUM      = 2   # número
_XF_PCT      = 3   # percentual
_XF_BOLD_NUM = 4   # bold número
_XF_FIXED    = 6   # quantos xf fixos existem  (total cores agora = 21)
_XF_HEADER   = 5   # cabeçalho: bold, sem fill, borda escura
# Texto alinhado à esquerda (sem cor) — acrescentados no FIM da lista de
# xf para não deslocar os índices existentes (ver _styles_xml).
_XF_LEFT      = _XF_FIXED + 6 * len(_PALETTE_ORDER)
_XF_BOLD_LEFT = _XF_LEFT + 1

def _xf_for_color(color):
    """Retorna (xf_index, font_white) para uma cor."""
    color = color.upper().lstrip('#')
    if color in _COLORS:
        fill_idx, white = _COLORS[color]
        # xf index = _XF_FIXED + 2*(fill_idx-2) + (0 se preto, 1 se branco)
        base = _XF_FIXED + 2 * (fill_idx - 2)
        return base
    return _XF_DEFAULT

def _xf_for_color_num(color):
    """xf com número formatado + cor."""
    color = color.upper().lstrip('#')
    if color in _COLORS:
        fill_idx, white = _COLORS[color]
        n_colors = len(_PALETTE_ORDER)
        base = _XF_FIXED + 2 * n_colors + 2 * (fill_idx - 2)
        return base
    return _XF_NUM

def _xf_for_color_pct(color):
    """xf com percentual + cor."""
    color = color.upper().lstrip('#')
    if color in _COLORS:
        fill_idx, white = _COLORS[color]
        n_colors = len(_PALETTE_ORDER)
        base = _XF_FIXED + 4 * n_colors + 2 * (fill_idx - 2)
        return base
    return _XF_PCT


class XlsxBook:

    def __init__(self):
        self._sheets  = []
        self._strings = OrderedDict()
        self._str_idx = 0

    def add_sheet(self, name):
        name = re.sub(r'[\\/*?:\[\]]', '_', name)[:31]
        # Garantir nome único — Excel não permite abas duplicadas
        existing = {n for n, _ in self._sheets}
        if name in existing:
            for i in range(2, 999):
                candidate = name[:28] + f'_{i}'
                if candidate not in existing:
                    name = candidate
                    break
        ws = XlsxSheet(self)
        self._sheets.append((name, ws))
        return ws

    def _str_id(self, s):
        s = str(s)
        if s not in self._strings:
            self._strings[s] = self._str_idx
            self._str_idx += 1
        return self._strings[s]

    def save(self, path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('[Content_Types].xml', self._content_types())
            zf.writestr('_rels/.rels', self._root_rels())
            zf.writestr('xl/workbook.xml', self._workbook_xml())
            zf.writestr('xl/_rels/workbook.xml.rels', self._workbook_rels())
            zf.writestr('xl/styles.xml', self._styles_xml())
            zf.writestr('xl/sharedStrings.xml', self._shared_strings_xml())
            for i, (name, ws) in enumerate(self._sheets, 1):
                zf.writestr(f'xl/worksheets/sheet{i}.xml', ws._to_xml())
        with open(path, 'wb') as f:
            f.write(buf.getvalue())

    def _content_types(self):
        sheets = ''.join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument'
            f'.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(self._sheets)+1))
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            + sheets + '</Types>')

    def _root_rels(self):
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')

    def _workbook_xml(self):
        sheets = ''.join(
            f'<sheet name="{_esc(n)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (n, _) in enumerate(self._sheets, 1))
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>' + sheets + '</sheets></workbook>')

    def _workbook_rels(self):
        n = len(self._sheets)
        rels = ''.join(
            f'<Relationship Id="rId{i}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, n+1))
        rels += (
            f'<Relationship Id="rId{n+1}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            f'Target="styles.xml"/>'
            f'<Relationship Id="rId{n+2}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            f'Target="sharedStrings.xml"/>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + rels + '</Relationships>')

    def _styles_xml(self):
        n = len(_PALETTE_ORDER)

        # Fontes: 0=preto 10pt, 1=bold preto, 2=bold branco, 3=preto 9pt
        fonts = (
            '<font><sz val="10"/><color rgb="FF000000"/><name val="Calibri"/></font>'
            '<font><b/><sz val="10"/><color rgb="FF000000"/><name val="Calibri"/></font>'
            '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
            '<font><sz val="9"/><color rgb="FF000000"/><name val="Calibri"/></font>'
        )

        # Fills: 0=none, 1=gray125, 2+= paleta
        fills = (
            '<fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
        ) + ''.join(
            f'<fill><patternFill patternType="solid">'
            f'<fgColor rgb="FF{c}"/></patternFill></fill>'
            for c in _PALETTE_ORDER)

        # Bordas
        borders = (
            '<border><left/><right/><top/><bottom/><diagonal/></border>'
            '<border>'
            '<left style="thin"><color rgb="FFCCCCCC"/></left>'
            '<right style="thin"><color rgb="FFCCCCCC"/></right>'
            '<top style="thin"><color rgb="FFCCCCCC"/></top>'
            '<bottom style="thin"><color rgb="FFCCCCCC"/></bottom>'
            '<diagonal/></border>'
            '<border>'
            '<left style="medium"><color rgb="FF000000"/></left>'
            '<right style="medium"><color rgb="FF000000"/></right>'
            '<top style="medium"><color rgb="FF000000"/></top>'
            '<bottom style="medium"><color rgb="FF000000"/></bottom>'
            '<diagonal/></border>'
        )

        def xf(numFmt, fontId, fillId, borderId=1, halign="center"):
            return (f'<xf numFmtId="{numFmt}" fontId="{fontId}" '
                    f'fillId="{fillId}" borderId="{borderId}" xfId="0">'
                    f'<alignment horizontal="{halign}" vertical="center" '
                    f'wrapText="1"/></xf>')

        # XF fixos (0-4)
        xfs = (
            xf(0,   0, 0, 1) +  # 0: default, borda cinza
            xf(0,   1, 0, 1) +  # 1: bold, borda cinza
            xf(164, 0, 0, 1) +  # 2: número
            xf(165, 0, 0, 1) +  # 3: percentual
            xf(164, 1, 0, 1) +  # 4: bold número
            xf(0,   1, 0, 2) +  # 5: cabeçalho bold, borda escura
        '')

        # XF por cor — texto (preto ou branco conforme luminância)
        # Para cada cor: xf_preto, xf_branco
        for c in _PALETTE_ORDER:
            fill_idx = _COLORS[c][0]
            xfs += xf(0,   0, fill_idx, halign="left")  # preto
            xfs += xf(0,   0, fill_idx, halign="left")  # branco→preto

        # XF por cor — número
        for c in _PALETTE_ORDER:
            fill_idx = _COLORS[c][0]
            xfs += xf(164, 0, fill_idx)  # preto
            xfs += xf(164, 0, fill_idx)  # branco→preto

        # XF por cor — percentual
        for c in _PALETTE_ORDER:
            fill_idx = _COLORS[c][0]
            xfs += xf(165, 0, fill_idx)  # preto
            xfs += xf(165, 0, fill_idx)  # branco→preto

        # Texto à esquerda (normal e negrito) — _XF_LEFT, _XF_BOLD_LEFT
        xfs += xf(0, 0, 0, 1, halign="left")
        xfs += xf(0, 1, 0, 1, halign="left")

        n_xf = _XF_FIXED + 6 * n + 2

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<numFmts count="2">'
            '<numFmt numFmtId="164" formatCode="#,##0.00"/>'
            '<numFmt numFmtId="165" formatCode="0.00%"/>'
            '</numFmts>'
            f'<fonts count="4">{fonts}</fonts>'
            f'<fills count="{2+n}">{fills}</fills>'
            f'<borders count="3">{borders}</borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            f'<cellXfs count="{n_xf}">{xfs}</cellXfs>'
            '</styleSheet>')

    def _shared_strings_xml(self):
        items = ''.join(
            f'<si><t xml:space="preserve">{_esc(s)}</t></si>'
            for s in self._strings)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{self._str_idx}" uniqueCount="{self._str_idx}">'
            + items + '</sst>')


class XlsxSheet:

    def __init__(self, book):
        self._book = book
        self._rows = {}
        self._col_widths = {}
        self._row_heights = {}

    def write(self, row, col, value,
              bold=False, color=None, num_fmt=None, header=False,
              align=None):
        """
        color: hex string (ex: '1F3864') → fundo colorido, fonte automática
        num_fmt: None | 'num' | 'pct'
        bold: aplicado somente sem cor
        header: True → bold, sem fill, borda escura (ignora color)
        align: 'left' → texto alinhado à esquerda (somente sem cor)
        """
        # Se valor for vazio, não aplicar num_fmt — evita inconsistência XML
        is_empty = value is None or value == ''
        if is_empty:
            num_fmt = None

        if header:
            xf = _XF_HEADER
        elif color:
            color = color.upper().lstrip('#')
            if num_fmt == 'num':
                xf = _xf_for_color_num(color)
            elif num_fmt == 'pct':
                xf = _xf_for_color_pct(color)
            else:
                xf = _xf_for_color(color)
        else:
            if num_fmt == 'num':
                xf = _XF_BOLD_NUM if bold else _XF_NUM
            elif num_fmt == 'pct':
                xf = _XF_PCT
            elif align == 'left':
                xf = _XF_BOLD_LEFT if bold else _XF_LEFT
            else:
                xf = _XF_BOLD if bold else _XF_DEFAULT

        is_str = isinstance(value, str)
        val    = self._book._str_id(value) if is_str and value != '' else value

        if row not in self._rows:
            self._rows[row] = {}
        self._rows[row][col] = (val, xf, is_str)

    def set_col_width(self, col, width):
        self._col_widths[col] = width

    def set_row_height(self, row, height):
        self._row_heights[row] = height

    @staticmethod
    def _col_letter(n):
        s = ''
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def _to_xml(self):
        cols_xml = ''
        if self._col_widths:
            cols_xml = '<cols>' + ''.join(
                f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'
                for c, w in sorted(self._col_widths.items())) + '</cols>'

        rows_xml = ''
        for r in sorted(self._rows):
            ht = self._row_heights.get(r, '')
            ht_attr = f' ht="{ht}" customHeight="1"' if ht else ''
            cells = ''
            for c in sorted(self._rows[r]):
                val, xf, is_str = self._rows[r][c]
                ref = f'{self._col_letter(c)}{r}'
                if val is None or val == '':
                    # Still write cell if it has a non-default style (for color)
                    if xf > 0:
                        cells += f'<c r="{ref}" s="{xf}"/>'
                    continue
                if is_str:
                    cells += f'<c r="{ref}" t="s" s="{xf}"><v>{val}</v></c>'
                elif isinstance(val, float):
                    import math as _math
                    if _math.isnan(val) or _math.isinf(val):
                        continue  # skip NaN/inf — invalid in Excel XML
                    cells += f'<c r="{ref}" s="{xf}"><v>{val!r}</v></c>'
                elif isinstance(val, int):
                    cells += f'<c r="{ref}" s="{xf}"><v>{val}</v></c>'
                else:
                    cells += f'<c r="{ref}" s="{xf}"><v>{val}</v></c>'
            rows_xml += f'<row r="{r}"{ht_attr}>{cells}</row>'

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + cols_xml +
            '<sheetData>' + rows_xml + '</sheetData>'
            '</worksheet>')
