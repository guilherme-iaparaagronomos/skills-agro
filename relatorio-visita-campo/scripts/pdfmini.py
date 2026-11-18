"""Escritor mínimo de PDF, só com a biblioteca padrão e o Pillow.

Existe para o relatório de visita levar as fotos em JPEG: um relatório de 20
fotos fica perto de 4 MB, e não de 20 ou 30.

O que faz: páginas A4, texto nas fontes padrão do PDF (Helvetica e Courier,
com acentos do português), retângulos de canto redondo, linhas, círculos,
polígonos, imagens em JPEG com recorte arredondado e links.

Coordenadas em pontos (1/72 de polegada), com a origem no canto de BAIXO, à
esquerda da página.

Teste embutido: python scripts/pdfmini.py
"""

import io
import unicodedata
import zlib

A4 = (595.28, 841.89)
FONTES = {'H': 'Helvetica', 'HB': 'Helvetica-Bold', 'HI': 'Helvetica-Oblique', 'HBI': 'Helvetica-BoldOblique',
          'M': 'Courier', 'MB': 'Courier-Bold'}
# larguras dos caracteres 32 a 126, em milésimos do corpo (métricas públicas das 14 fontes padrão do PDF)
_H = [278, 278, 355, 556, 556, 889, 667, 222, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
      556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
      667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 222, 556, 556, 500, 556, 556, 278, 556,
      556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HB = [278, 333, 474, 556, 556, 889, 722, 278, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
       556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
       667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 278, 556, 611, 556, 611, 556, 333, 611,
       611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]
# (normal, negrito) dos sinais fora do ASCII que o relatório usa
_EXTRA = {'–': (556, 556), '—': (1000, 1000), '·': (278, 278), '°': (400, 400), '•': (350, 350), '“': (333, 500),
          '”': (333, 500), '‘': (222, 278), '’': (222, 278), 'ª': (370, 370), 'º': (365, 365), '§': (556, 556),
          '±': (584, 584), '×': (584, 584), '²': (333, 333), '³': (333, 333), '½': (834, 834), '…': (1000, 1000),
          '«': (556, 556), '»': (556, 556), 'µ': (556, 611), '¹': (333, 333), '¼': (834, 834), '¾': (834, 834), '÷': (584, 584)}
_TROCAS = {'−': '-', ' ': ' ', ' ': ' ', ' ': ' ', '→': '->', '←': '<-', '✓': 'x',
           '•': '•', '\t': ' '}


def limpar(texto):
    """Texto pronto para a fonte padrão: sem caracteres de controle, com o que a fonte não tem trocado por '?'."""
    s = str(texto if texto is not None else '')
    for de, para in _TROCAS.items():
        s = s.replace(de, para)
    s = ''.join(c for c in s if c == '\n' or (ord(c) >= 32 and unicodedata.category(c) not in ('Cf', 'Cc', 'Co', 'Cs')))
    return s.encode('cp1252', 'replace').decode('cp1252')


def largura_do_caractere(c, fonte):
    if fonte in ('M', 'MB'):
        return 600
    negrito = fonte in ('HB', 'HBI')
    tabela = _HB if negrito else _H
    o = ord(c)
    if 32 <= o <= 126:
        return tabela[o - 32]
    if c in _EXTRA:
        return _EXTRA[c][1 if negrito else 0]
    base = unicodedata.normalize('NFD', c)[0]       # letra acentuada tem a largura da letra
    if base != c and 32 <= ord(base) <= 126:
        return tabela[ord(base) - 32]
    return 556


def largura(texto, fonte='H', tam=10.0, tracking=0.0):
    s = limpar(texto)
    return sum(largura_do_caractere(c, fonte) for c in s) * tam / 1000.0 + tracking * len(s)


def quebrar(texto, fonte, tam, largura_max, tracking=0.0):
    """Quebra em linhas que cabem em `largura_max`. Parágrafos separados por quebra de linha; palavra maior que a linha é cortada."""
    linhas = []
    for paragrafo in limpar(texto).split('\n'):
        atual = ''
        for palavra in paragrafo.split():
            while largura(palavra, fonte, tam, tracking) > largura_max:        # endereço colado, por exemplo
                corte = len(palavra)
                while corte > 1 and largura(palavra[:corte], fonte, tam, tracking) > largura_max:
                    corte -= 1
                if atual:
                    linhas.append(atual)
                    atual = ''
                linhas.append(palavra[:corte])
                palavra = palavra[corte:]
            tentativa = palavra if not atual else atual + ' ' + palavra
            if largura(tentativa, fonte, tam, tracking) <= largura_max:
                atual = tentativa
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    while len(linhas) > 1 and not linhas[-1]:
        linhas.pop()
    return linhas


def _rgb(cor):
    cor = cor.lstrip('#')
    return '%.3f %.3f %.3f' % tuple(int(cor[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _n(v):
    return ('%.2f' % v).rstrip('0').rstrip('.') if '.' in '%.2f' % v else '%.2f' % v


def _caminho_ret(x, y, w, h, r):
    if r <= 0:
        return f'{_n(x)} {_n(y)} {_n(w)} {_n(h)} re'
    r = min(r, w / 2.0, h / 2.0)
    k = r * 0.5523
    p = [f'{_n(x + r)} {_n(y)} m', f'{_n(x + w - r)} {_n(y)} l',
         f'{_n(x + w - r + k)} {_n(y)} {_n(x + w)} {_n(y + r - k)} {_n(x + w)} {_n(y + r)} c',
         f'{_n(x + w)} {_n(y + h - r)} l',
         f'{_n(x + w)} {_n(y + h - r + k)} {_n(x + w - r + k)} {_n(y + h)} {_n(x + w - r)} {_n(y + h)} c',
         f'{_n(x + r)} {_n(y + h)} l',
         f'{_n(x + r - k)} {_n(y + h)} {_n(x)} {_n(y + h - r + k)} {_n(x)} {_n(y + h - r)} c',
         f'{_n(x)} {_n(y + r)} l',
         f'{_n(x)} {_n(y + r - k)} {_n(x + r - k)} {_n(y)} {_n(x + r)} {_n(y)} c', 'h']
    return ' '.join(p)


def _pintar(preencher, contorno, espessura):
    partes = []
    if preencher:
        partes.append(_rgb(preencher) + ' rg')
    if contorno:
        partes.append(_rgb(contorno) + ' RG')
        partes.append(_n(espessura) + ' w')
    op = 'B' if preencher and contorno else ('f' if preencher else 'S')
    return ' '.join(partes), op


class Pdf:
    def __init__(self, tamanho=A4, titulo=None):
        self.largura, self.altura = tamanho
        self.titulo = titulo
        self.paginas = []
        self._imagens = []          # (bytes em JPEG, largura, altura)
        self._atual = -1
        self._fontes = list(FONTES)

    # ---- páginas
    def nova_pagina(self, fundo=None):
        self.paginas.append({'ops': [], 'links': [], 'imagens': set()})
        self._atual = len(self.paginas) - 1
        if fundo:
            self.ret(0, 0, self.largura, self.altura, preencher=fundo)
        return len(self.paginas)

    def ir_para(self, numero):
        """Volta a desenhar na página `numero` (a primeira é 1): serve para o rodapé, que só se sabe no fim."""
        self._atual = numero - 1

    def _op(self, texto):
        self.paginas[self._atual]['ops'].append(texto)

    # ---- formas
    def ret(self, x, y, w, h, raio=0, preencher=None, contorno=None, espessura=1.0):
        cores, op = _pintar(preencher, contorno, espessura)
        self._op(f'q {cores} {_caminho_ret(x, y, w, h, raio)} {op} Q')

    def linha(self, x1, y1, x2, y2, cor='#000000', espessura=1.0):
        self._op(f'q {_rgb(cor)} RG {_n(espessura)} w {_n(x1)} {_n(y1)} m {_n(x2)} {_n(y2)} l S Q')

    def circulo(self, x, y, r, preencher=None, contorno=None, espessura=1.0):
        k = r * 0.5523
        caminho = (f'{_n(x + r)} {_n(y)} m {_n(x + r)} {_n(y + k)} {_n(x + k)} {_n(y + r)} {_n(x)} {_n(y + r)} c '
                   f'{_n(x - k)} {_n(y + r)} {_n(x - r)} {_n(y + k)} {_n(x - r)} {_n(y)} c '
                   f'{_n(x - r)} {_n(y - k)} {_n(x - k)} {_n(y - r)} {_n(x)} {_n(y - r)} c '
                   f'{_n(x + k)} {_n(y - r)} {_n(x + r)} {_n(y - k)} {_n(x + r)} {_n(y)} c h')
        cores, op = _pintar(preencher, contorno, espessura)
        self._op(f'q {cores} {caminho} {op} Q')

    def poligono(self, pontos, preencher=None, contorno=None, espessura=1.0, fechar=True, recorte=None):
        """`recorte` = (x, y, w, h, raio): desenha só o que cai dentro desse retângulo."""
        if len(pontos) < 2:
            return
        caminho = ' '.join(f'{_n(px)} {_n(py)} {"m" if i == 0 else "l"}' for i, (px, py) in enumerate(pontos))
        if fechar:
            caminho += ' h'
        cores, op = _pintar(preencher, contorno, espessura)
        corte = f'{_caminho_ret(*recorte)} W n ' if recorte else ''
        self._op(f'q {corte}{cores} {caminho} {op} Q')

    # ---- texto
    def texto(self, x, y, texto, fonte='H', tam=10.0, cor='#121810', alinh='esq', tracking=0.0, link=None):
        """Escreve uma linha com a linha de base em y. Devolve a largura escrita."""
        s = limpar(texto).replace('\n', ' ')
        w = largura(s, fonte, tam, tracking)
        if alinh == 'dir':
            x -= w
        elif alinh == 'centro':
            x -= w / 2.0
        cru = s.encode('cp1252', 'replace').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
        indice = self._fontes.index(fonte) + 1
        self._op(f'BT /F{indice} {_n(tam)} Tf {_rgb(cor)} rg {_n(tracking)} Tc {_n(x)} {_n(y)} Td ('
                 + cru.decode('latin-1') + ') Tj ET')
        if link:
            self.link(x, y - 0.25 * tam, w, tam * 1.1, link)
        return w

    def paragrafo(self, x, y, texto, largura_max, fonte='H', tam=10.0, cor='#121810', entrelinha=1.4, max_linhas=None):
        """Escreve o texto quebrado a partir da linha de base y, descendo. Devolve o y da última linha de base."""
        linhas = quebrar(texto, fonte, tam, largura_max)
        if max_linhas and len(linhas) > max_linhas:
            linhas = linhas[:max_linhas]
            linhas[-1] = linhas[-1].rstrip('. ') + '…'
        for i, linha in enumerate(linhas):
            self.texto(x, y - i * tam * entrelinha, linha, fonte, tam, cor)
        return y - (len(linhas) - 1) * tam * entrelinha

    def link(self, x, y, w, h, url):
        self.paginas[self._atual]['links'].append((x, y, x + w, y + h, limpar(url)))

    # ---- imagens
    def imagem(self, im, x, y, w, h, raio=0, qualidade=82):
        """Desenha uma imagem do Pillow no retângulo (x, y, w, h), esticada para ele, com canto redondo opcional."""
        if im.mode != 'RGB':
            im = im.convert('RGB')
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=qualidade, optimize=True)
        self._imagens.append((buf.getvalue(), im.size[0], im.size[1]))
        indice = len(self._imagens)
        self.paginas[self._atual]['imagens'].add(indice)
        corte = f'{_caminho_ret(x, y, w, h, raio)} W n ' if raio > 0 else ''
        self._op(f'q {corte}{_n(w)} 0 0 {_n(h)} {_n(x)} {_n(y)} cm /Im{indice} Do Q')

    # ---- gravação
    def salvar(self, caminho):
        if not self.paginas:
            self.nova_pagina()
        objetos = []                               # corpo de cada objeto, na ordem do número

        def novo(corpo):
            objetos.append(corpo if isinstance(corpo, bytes) else corpo.encode('latin-1'))
            return len(objetos)

        n_catalogo = novo('')                      # 1: preenchido no fim
        n_paginas = novo('')                       # 2: preenchido no fim
        n_fontes = [novo(f'<< /Type /Font /Subtype /Type1 /BaseFont /{FONTES[f]} /Encoding /WinAnsiEncoding >>')
                    for f in self._fontes]
        n_imagens = []
        for dados, w, h in self._imagens:
            cab = (f'<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB '
                   f'/BitsPerComponent 8 /Filter /DCTDecode /Length {len(dados)} >>\nstream\n').encode('latin-1')
            n_imagens.append(novo(cab + dados + b'\nendstream'))
        recursos_fontes = ' '.join(f'/F{i + 1} {n} 0 R' for i, n in enumerate(n_fontes))
        n_das_paginas = []
        for pagina in self.paginas:
            fluxo = zlib.compress('\n'.join(pagina['ops']).encode('latin-1'), 9)
            n_conteudo = novo(f'<< /Length {len(fluxo)} /Filter /FlateDecode >>\nstream\n'.encode('latin-1') + fluxo + b'\nendstream')
            xobj = ' '.join(f'/Im{i} {n_imagens[i - 1]} 0 R' for i in sorted(pagina['imagens']))
            anots = ''
            if pagina['links']:
                itens = []
                for x1, y1, x2, y2, url in pagina['links']:
                    alvo = url.encode('cp1252', 'replace').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)').decode('latin-1')
                    itens.append(f'<< /Type /Annot /Subtype /Link /Rect [{_n(x1)} {_n(y1)} {_n(x2)} {_n(y2)}] /Border [0 0 0] '
                                 f'/A << /S /URI /URI ({alvo}) >> >>')
                anots = ' /Annots [' + ' '.join(itens) + ']'
            n_das_paginas.append(novo(
                f'<< /Type /Page /Parent {n_paginas} 0 R /MediaBox [0 0 {_n(self.largura)} {_n(self.altura)}] '
                f'/Resources << /Font << {recursos_fontes} >> /XObject << {xobj} >> >> /Contents {n_conteudo} 0 R{anots} >>'))
        titulo = ''
        if self.titulo:
            titulo = ' /Title <' + ('﻿' + limpar(self.titulo)).encode('utf-16-be').hex().upper() + '>'
        n_info = novo(f'<< /Producer (agronomo10X){titulo} >>')
        objetos[n_catalogo - 1] = f'<< /Type /Catalog /Pages {n_paginas} 0 R >>'.encode('latin-1')
        objetos[n_paginas - 1] = (f'<< /Type /Pages /Count {len(n_das_paginas)} /Kids ['
                                  + ' '.join(f'{n} 0 R' for n in n_das_paginas) + '] >>').encode('latin-1')
        saida = io.BytesIO()
        saida.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        posicoes = []
        for i, corpo in enumerate(objetos, 1):
            posicoes.append(saida.tell())
            saida.write(f'{i} 0 obj\n'.encode('latin-1') + corpo + b'\nendobj\n')
        inicio_xref = saida.tell()
        saida.write(f'xref\n0 {len(objetos) + 1}\n'.encode('latin-1'))
        saida.write(b'0000000000 65535 f \n')
        for p in posicoes:
            saida.write(f'{p:010d} 00000 n \n'.encode('latin-1'))
        saida.write(f'trailer\n<< /Size {len(objetos) + 1} /Root {n_catalogo} 0 R /Info {n_info} 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n'
                    .encode('latin-1'))
        with open(caminho, 'wb') as f:
            f.write(saida.getvalue())
        return len(self.paginas)


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import os
    import tempfile

    from PIL import Image
    assert limpar('Aplicação​ − 5°C → ok\x07') == 'Aplicação - 5°C -> ok'
    assert limpar('日本') == '??'
    assert largura('Hello', 'H', 10) == (722 + 556 + 222 + 222 + 556) / 100.0
    assert largura('ação', 'H', 10) == largura('acao', 'H', 10) and largura('abc', 'M', 10) == 18.0
    assert largura('AB', 'H', 10, tracking=2) == (667 + 667) / 100.0 + 4
    linhas = quebrar('uma frase curta para quebrar em linhas de largura pequena', 'H', 10, 80)
    assert len(linhas) >= 3 and all(largura(l, 'H', 10) <= 80 for l in linhas)
    assert quebrar('a\n\nb', 'H', 10, 100) == ['a', '', 'b']
    assert all(largura(l, 'H', 10) <= 60 for l in quebrar('https://exemplo.com/um/endereco/muito/comprido/sem/espaco', 'H', 10, 60))
    pdf = Pdf(titulo='Relatório de teste')
    pdf.nova_pagina(fundo='#F4F1EA')
    pdf.ret(40, 700, 200, 80, raio=8, preencher='#EAE6DA', contorno='#DCD7C7')
    pdf.texto(50, 750, 'Aplicação (teste) \\ fim', 'HBI', 14, '#121810')
    pdf.texto(555, 750, 'à direita', 'M', 9, alinh='dir', link='https://exemplo.com/?q=-22.5,-50.9')
    pdf.circulo(100, 600, 9, preencher='#2F8B1F', contorno='#FFFFFF')
    pdf.poligono([(200, 560), (260, 640), (320, 560)], contorno='#121810', recorte=(200, 560, 100, 60, 4))
    pdf.imagem(Image.new('RGB', (64, 48), (90, 140, 60)), 40, 400, 200, 150, raio=8)
    y = pdf.paragrafo(40, 380, 'Um parágrafo comprido o bastante para quebrar em mais de uma linha dentro da largura dada.', 180)
    assert y < 380
    pdf.nova_pagina()
    pdf.texto(40, 800, 'Página 2')
    pdf.ir_para(1)
    pdf.texto(40, 30, 'rodapé posto depois', 'H', 7)
    pdf.ir_para(2)
    with tempfile.TemporaryDirectory() as pasta:
        caminho = os.path.join(pasta, 't.pdf')
        assert pdf.salvar(caminho) == 2
        dados = open(caminho, 'rb').read()
        assert dados.startswith(b'%PDF-1.4') and dados.rstrip().endswith(b'%%EOF')
        inicio = int(dados.rsplit(b'startxref', 1)[1].split()[0])
        assert dados[inicio:inicio + 4] == b'xref', 'a tabela de objetos tem de começar onde o fim do arquivo aponta'
        for linha in dados[inicio:].split(b'\n')[2:]:               # cada posição aponta para o começo de um objeto
            if linha.endswith(b' n '):
                p = int(linha[:10])
                assert b' 0 obj' in dados[p:p + 14], linha
        try:
            import fitz
        except ImportError:
            fitz = None
        if fitz:
            doc = fitz.open(caminho)
            assert doc.page_count == 2 and not doc.is_repaired
            texto = doc[0].get_text()
            assert 'Aplicação (teste) \\ fim' in texto and 'à direita' in texto and 'rodapé posto depois' in texto, texto
            assert [l['uri'] for l in doc[0].get_links()] == ['https://exemplo.com/?q=-22.5,-50.9']
            assert len(doc[0].get_images()) == 1 and doc.metadata['title'] == 'Relatório de teste'
            doc.close()
    print('pdfmini.py: autoteste ok (larguras, quebra de linha, 2 páginas, imagem, link'
          + (', relido por outro leitor de PDF)' if fitz else ')'))


if __name__ == '__main__':
    _autoteste()
