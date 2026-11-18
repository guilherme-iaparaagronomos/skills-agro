"""Desenha o relatório de visita em PDF, no padrão claro dos documentos da casa:
cabeçalho com a fazenda e as contagens, dados da visita, localização (mapa e
paradas), resumo, observações, registros por assunto com as fotos e, se
pedido, a transcrição dos áudios.

Só desenha: o conteúdo vem conferido de visita.py e o mapa, de mapa.py.

Teste embutido: python scripts/relatorio.py
"""

from datetime import datetime

from PIL import Image

import mapa as M
import visita as V
from pdfmini import A4, Pdf, largura, quebrar

T = dict(pagina='#F4F1EA', cartao='#EAE6DA', linha='#DCD7C7', linha_forte='#B5B1A1', tinta1='#0B100B', tinta2='#3C4636',
         tinta3='#5A6452', verde='#2F8B1F', verde_texto='#237514', branco='#FFFFFF')
W, H = A4
MARGEM = 36.0
LARG = W - 2 * MARGEM
RODAPE = 66.0
EYEBROW = 'AGRÔNOMO10X · RELATÓRIO DE VISITA TÉCNICA'
AVISO = ('As descrições das fotos foram escritas pela IA; o conteúdo técnico é de responsabilidade de quem fez a visita.')


class Doc:
    """O PDF com um cursor que desce a página e abre outra quando falta espaço."""

    def __init__(self, v):
        self.v = v
        self.pdf = Pdf(titulo=f'Relatório de visita técnica — {v["fazenda"]}')
        self.y = 0.0
        self.pagina(primeira=True)

    def pagina(self, primeira=False):
        self.pdf.nova_pagina(fundo=T['pagina'])
        if primeira:
            return
        self.pdf.texto(MARGEM, H - 44, EYEBROW, 'H', 7.2, T['verde_texto'], tracking=1.5)
        self.pdf.texto(W - MARGEM, H - 44, _curto(self.v['fazenda'], 'H', 9, 240), 'H', 9, T['tinta2'], alinh='dir')
        self.pdf.linha(MARGEM, H - 56, W - MARGEM, H - 56, T['linha'], 0.8)
        self.y = H - 80

    def precisa(self, altura):
        """Garante `altura` pontos livres; abre página nova se não couber. Devolve True se abriu."""
        if self.y - altura < RODAPE:
            self.pagina()
            return True
        return False

    def titulo_de_secao(self, texto, antes=20.0):
        self.precisa(antes + 30)
        self.y -= antes
        self.pdf.texto(MARGEM, self.y, texto.upper(), 'H', 8.4, T['tinta1'], tracking=1.7)
        self.y -= 14

    def paragrafo(self, texto, fonte='H', tam=9.8, cor=None, x=MARGEM, larg=LARG, entrelinha=1.45, depois=6.0):
        cor = cor or T['tinta1']
        for linha in quebrar(texto, fonte, tam, larg):
            self.precisa(tam * entrelinha)
            self.y -= tam * entrelinha
            self.pdf.texto(x, self.y + tam * 0.3, linha, fonte, tam, cor)
        self.y -= depois


def _curto(texto, fonte, tam, larg):
    texto = str(texto)
    if largura(texto, fonte, tam) <= larg:
        return texto
    while len(texto) > 1 and largura(texto + '…', fonte, tam) > larg:
        texto = texto[:-1]
    return texto.rstrip() + '…'


# ------------------------------------------------------------------ página 1
def _cabecalho(doc):
    v, pdf = doc.v, doc.pdf
    pdf.texto(MARGEM, H - 46, EYEBROW, 'H', 7.4, T['verde_texto'], tracking=1.6)
    contagens = [('FOTOS', str(v['n_fotos'])), ('ÁUDIOS', str(v['audios']))]
    if v['n_notas']:
        contagens.append(('NOTAS', str(v['n_notas'])))
    if v['paradas']:
        contagens.append(('PARADAS', str(len(v['paradas']))))
    if v['duracao_min']:
        contagens.append(('DURAÇÃO', V.duracao_txt(v['duracao_min'])))
    x = W - MARGEM
    for rotulo, valor in reversed(contagens):
        larg = max(largura(valor, 'HB', 19), largura(rotulo, 'H', 6.3, 1.3))
        pdf.texto(x, H - 46, rotulo, 'H', 6.3, T['tinta3'], alinh='dir', tracking=1.3)
        pdf.texto(x, H - 72, valor, 'HB', 19, T['tinta1'], alinh='dir')
        x -= larg + 20
    livre = x - MARGEM
    tam = 19.0
    while tam > 12.5 and largura(v['fazenda'], 'HBI', tam) > livre:
        tam -= 0.5
    pdf.texto(MARGEM, H - 72, _curto(v['fazenda'], 'HBI', tam, livre), 'HBI', tam, T['tinta1'])
    pdf.texto(MARGEM, H - 90, f'{v["cidade"]} / {v["estado"]} · {v["data"]:%d/%m/%Y}', 'H', 9.8, T['tinta3'])
    pdf.linha(MARGEM, H - 104, W - MARGEM, H - 104, T['linha'], 0.9)
    doc.y = H - 104


def _dados(doc):
    pares = V.dados_da_visita(doc.v)
    if not pares:
        return
    pdf = doc.pdf
    doc.titulo_de_secao('Dados da visita')
    coluna = (LARG - 28) / 3.0
    linhas = [pares[i:i + 3] for i in range(0, len(pares), 3)]
    alturas = []
    for linha in linhas:
        maior = max(len(quebrar(valor, 'H', 10.2, coluna - 12)[:3]) for _, valor in linha)
        alturas.append(16 + maior * 13.5 + 8)
    total = sum(alturas) + 14
    doc.precisa(total)
    topo = doc.y
    pdf.ret(MARGEM, topo - total, LARG, total, raio=8, preencher=T['cartao'], contorno=T['linha'], espessura=0.8)
    y = topo - 10
    for linha, altura in zip(linhas, alturas):
        for k, (rotulo, valor) in enumerate(linha):
            x = MARGEM + 14 + k * coluna
            pdf.texto(x, y - 10, rotulo.upper(), 'H', 6.3, T['tinta3'], tracking=1.2)
            for i, parte in enumerate(quebrar(valor, 'H', 10.2, coluna - 12)[:3]):
                pdf.texto(x, y - 24 - i * 13.5, parte, 'H', 10.2, T['tinta1'])
        y -= altura
    doc.y = topo - total


def _cartao_do_mapa(doc, m, imagem, x, topo, larg, alt):
    """O cartão branco com a imagem, o contorno, as paradas, o norte e a escala."""
    pdf = doc.pdf
    pdf.ret(x, topo - alt, larg, alt, raio=8, preencher=T['branco'], contorno=T['linha_forte'], espessura=0.8)
    borda = 7.0
    ix, iy, iw, ih = x + borda, topo - alt + borda, larg - 2 * borda, alt - 2 * borda
    if imagem is not None:
        pdf.imagem(imagem, ix, iy, iw, ih, raio=5, qualidade=88)
    recorte = (ix, iy, iw, ih, 5)
    for anel in m['aneis']:
        pontos = [(ix + u * iw, iy + w * ih) for u, w in anel]
        if imagem is not None:
            pdf.poligono(pontos, contorno=T['tinta1'], espessura=2.0, recorte=recorte)
            pdf.poligono(pontos, contorno=T['branco'], espessura=1.0, recorte=recorte)
        else:
            pdf.poligono(pontos, preencher=T['cartao'], contorno=T['tinta2'], espessura=0.9, recorte=recorte)
    for n, u, w in m['paradas']:
        px, py = ix + u * iw, iy + w * ih
        pdf.circulo(px, py, 7.5, preencher=T['verde_texto'], contorno=T['branco'], espessura=1.3)
        pdf.texto(px, py - 2.6, str(n), 'HB', 7.4, T['branco'], alinh='centro')
    # norte
    nx, ny = ix + iw - 22, iy + ih - 34
    pdf.ret(nx, ny, 16, 28, raio=3, preencher=T['branco'], contorno=T['linha'], espessura=0.5)
    pdf.poligono([(nx + 8, ny + 24), (nx + 3.5, ny + 13), (nx + 12.5, ny + 13)], preencher=T['tinta1'])
    pdf.texto(nx + 8, ny + 3.5, 'N', 'HB', 6.5, T['tinta1'], alinh='centro')
    # escala
    barra = m['barra_m'] / m['largura_m'] * iw
    rotulo = f'{m["barra_m"] // 1000} km' if m['barra_m'] >= 1000 else f'{m["barra_m"]} m'
    caixa = barra + largura(rotulo, 'M', 6.8) + 18
    pdf.ret(ix + 6, iy + 6, caixa, 14, raio=3, preencher=T['branco'], contorno=T['linha'], espessura=0.5)
    pdf.linha(ix + 12, iy + 13, ix + 12 + barra, iy + 13, T['tinta1'], 1.1)
    for bx in (ix + 12, ix + 12 + barra):
        pdf.linha(bx, iy + 10.5, bx, iy + 15.5, T['tinta1'], 1.1)
    pdf.texto(ix + 12 + barra + 5, iy + 10.6, rotulo, 'M', 6.8, T['tinta1'])


def _localizacao(doc, m):
    v, pdf = doc.v, doc.pdf
    doc.titulo_de_secao('Localização da visita')
    if m is None:
        doc.paragrafo('Nenhuma localização foi informada nesta visita.', cor=T['tinta3'])
        return
    quadros = [(rot, im) for rot, im in (('COR NATURAL (RGB)', m['cor']), ('NDVI', m['ndvi'])) if im is not None]
    if not quadros:
        quadros = [('ÁREA E PARADAS', None)]
    if len(quadros) == 2:
        larg = (LARG - 12) / 2.0
    else:
        larg = min(LARG, 330.0 if m['proporcao'] < 1.3 else 400.0)
    alt = min(larg / m['proporcao'], 300.0)
    larg_real = alt * m['proporcao'] if alt < larg / m['proporcao'] else larg
    doc.precisa(alt + 46)
    topo = doc.y
    for k, (rotulo, imagem) in enumerate(quadros):
        x = MARGEM + k * ((LARG - 12) / 2.0 + 12 if len(quadros) == 2 else 0)
        _cartao_do_mapa(doc, m, imagem, x, topo, larg_real, alt)
        pdf.texto(x, topo - alt - 13, rotulo, 'H', 6.3, T['tinta3'], tracking=1.3)
        if rotulo == 'NDVI' and m['limites_ndvi']:
            passo = (larg_real - 44) / 5.0
            for i, (cor, (a, b)) in enumerate(zip(M.CORES_NDVI, m['limites_ndvi'])):
                lx = x + 44 + i * passo
                pdf.ret(lx, topo - alt - 14, passo - 3, 6, raio=1.5, preencher=cor, contorno=T['linha_forte'], espessura=0.3)
                pdf.texto(lx + (passo - 3) / 2, topo - alt - 24, f'{a:.2f}–{b:.2f}'.replace('.', ','), 'M', 5.6, T['tinta3'], alinh='centro')
    doc.y = topo - alt - (30 if any(r == 'NDVI' for r, _ in quadros) else 20)
    if v['satelite']:
        doc.paragrafo(V.credito_da_imagem(v['satelite']), tam=7.2, cor=T['tinta3'], depois=2)
    fora = dict(m['fora'])
    if v['paradas']:
        _paradas(doc, fora)
    if m['cor'] is None and m['ndvi'] is None and not v['satelite']:
        doc.paragrafo('O mapa mostra só o desenho da área e as paradas: nenhuma imagem de satélite foi incluída.', tam=7.2,
                      cor=T['tinta3'], depois=2)


def _paradas(doc, fora):
    v, pdf = doc.v, doc.pdf
    coluna = LARG / 3.0
    doc.y -= 8
    def linhas_de(p):
        fora_txt = f'fora do mapa, a {M.distancia_txt(fora[p["n"]])}' if p['n'] in fora else None
        return [t for t in (' · '.join(x for x in (p['nome'], p['hora']) if x), p['origem'], fora_txt) if t]

    for i in range(0, len(v['paradas']), 3):
        trio = v['paradas'][i:i + 3]
        altura = 30 + 10 * max(len(linhas_de(p)) for p in trio)
        doc.precisa(altura)
        topo = doc.y
        for k, p in enumerate(trio):
            x = MARGEM + k * coluna
            pdf.circulo(x + 7.5, topo - 8, 7.5, preencher=T['verde_texto'])
            pdf.texto(x + 7.5, topo - 10.6, str(p['n']), 'HB', 7.4, T['branco'], alinh='centro')
            pdf.texto(x + 21, topo - 11, V.coordenada_txt(p['lat'], p['lon']), 'MB', 8.6, T['tinta1'])
            y = topo - 21.5
            for linha in linhas_de(p):
                pdf.texto(x + 21, y, _curto(linha, 'H', 7.2, coluna - 26), 'H', 7.2, T['tinta3'])
                y -= 10
            w = pdf.texto(x + 21, y, 'abrir no mapa', 'H', 7.2, T['verde_texto'], link=V.link_do_mapa(p['lat'], p['lon']))
            pdf.linha(x + 21, y - 1.2, x + 21 + w, y - 1.2, T['verde_texto'], 0.4)
        doc.y = topo - altura


def _resumo(doc):
    v, pdf = doc.v, doc.pdf
    doc.titulo_de_secao('Resumo')
    doc.paragrafo(v['resumo'], tam=10, cor=T['tinta1'])
    if v['observacoes']:
        doc.titulo_de_secao('Observações', antes=12)
        for obs in v['observacoes']:
            linhas = quebrar(obs, 'H', 10, LARG - 16)
            doc.precisa(len(linhas) * 14.5 + 4)
            pdf.ret(MARGEM, doc.y - 11.5, 4.5, 4.5, preencher=T['verde'])
            for linha in linhas:
                doc.y -= 14.5
                pdf.texto(MARGEM + 15, doc.y + 3, linha, 'H', 10, T['tinta1'])
            doc.y -= 4


# ------------------------------------------------------------------ registros
def _cartao_da_foto(doc, foto, parada, x, topo, larg, desenhar=True):
    """Desenha a foto e a legenda a partir de `topo`; devolve a altura usada."""
    pdf = doc.pdf
    alt_img = larg * 0.75
    legenda = quebrar(foto['descricao'], 'H', 8.4, larg)[:5] if foto['descricao'] else []
    meta = ' · '.join(x for x in (foto['hora'], f'Parada {parada}' if parada is not None else None, foto['arquivo'].split('/')[-1]) if x)
    altura = alt_img + 8 + len(legenda) * 11.6 + 12
    if not desenhar:
        return altura
    pdf.ret(x, topo - alt_img, larg, alt_img, raio=8, preencher=T['cartao'], contorno=T['linha'], espessura=0.6)
    im = foto['imagem']
    escala = min(larg / im.size[0], alt_img / im.size[1])
    iw, ih = im.size[0] * escala, im.size[1] * escala
    if max(im.size) > 1000:
        im = im.copy()
        im.thumbnail((1000, 1000), Image.LANCZOS)
    cheia = abs(iw - larg) < 1.5 and abs(ih - alt_img) < 1.5
    pdf.imagem(im, x + (larg - iw) / 2, topo - alt_img + (alt_img - ih) / 2, iw, ih, raio=8 if cheia else 0, qualidade=80)
    y = topo - alt_img - 12
    for linha in legenda:
        pdf.texto(x, y, linha, 'H', 8.4, T['tinta1'])
        y -= 11.6
    pdf.texto(x, y - 0.5, _curto(meta, 'M', 6.6, larg), 'M', 6.6, T['tinta3'])
    return altura


def _registros(doc):
    v, pdf = doc.v, doc.pdf
    if doc.y < H - 300:
        doc.pagina()
        doc.y += 20
    doc.titulo_de_secao('Registros da visita', antes=10)
    larg_foto = (LARG - 12) / 2.0
    for g in v['grupos']:
        doc.precisa(70)
        doc.y -= 12
        cab = V.cabecalho_da_parada(v, g)
        if cab:
            pdf.texto(MARGEM, doc.y, cab.upper(), 'H', 6.8, T['verde_texto'], tracking=1.3)
            doc.y -= 6
        for linha in quebrar(g['titulo'], 'HBI', 13, LARG):
            doc.y -= 15
            pdf.texto(MARGEM, doc.y, linha, 'HBI', 13, T['tinta1'])
        doc.y -= 4
        if g['texto']:
            doc.paragrafo(g['texto'], tam=9.6, cor=T['tinta2'])
        for nota in g['notas']:
            linhas = quebrar(nota['texto'], 'H', 9.4, LARG - 14)
            alt = 12 + len(linhas) * 13.2 + 2
            doc.precisa(alt + 6)
            topo = doc.y - 4
            pdf.ret(MARGEM, topo - alt, 2.4, alt, preencher=T['verde'])
            pdf.texto(MARGEM + 12, topo - 8.5, 'NOTA' + (f' · {nota["hora"]}' if nota['hora'] else ''), 'H', 6.3, T['tinta3'], tracking=1.2)
            for i, linha in enumerate(linhas):
                pdf.texto(MARGEM + 12, topo - 21 - i * 13.2, linha, 'H', 9.4, T['tinta1'])
            doc.y = topo - alt - 6
        for i in range(0, len(g['fotos']), 2):
            par = g['fotos'][i:i + 2]
            alt = max(_cartao_da_foto(doc, f, g['parada'], 0, 0, larg_foto, desenhar=False) for f in par)
            doc.precisa(alt + 10)
            topo = doc.y - 8
            for k, f in enumerate(par):
                _cartao_da_foto(doc, f, g['parada'], MARGEM + k * (larg_foto + 12), topo, larg_foto)
            doc.y = topo - alt
        doc.y -= 6


def _transcricoes(doc):
    v, pdf = doc.v, doc.pdf
    if not v['incluir_transcricoes']:
        return
    doc.titulo_de_secao('Transcrição dos áudios')
    for t in v['transcricoes']:
        doc.precisa(30)
        rotulo = ' · '.join(x for x in (t['hora'], t['origem']) if x)
        if rotulo:
            doc.y -= 11
            pdf.texto(MARGEM, doc.y, rotulo.upper(), 'H', 6.5, T['verde_texto'], tracking=1.2)
        doc.paragrafo(t['texto'], tam=9.2, cor=T['tinta2'], depois=8)


def _rodapes(doc, quando):
    pdf = doc.pdf
    total = len(pdf.paginas)
    for n in range(1, total + 1):
        pdf.ir_para(n)
        pdf.linha(MARGEM, 56, W - MARGEM, 56, T['linha'], 0.8)
        pdf.texto(MARGEM, 44, AVISO, 'H', 6.6, T['tinta3'])
        pdf.texto(MARGEM, 34, f'Relatório organizado com a skill de relatório de visita · comunidade agrônomo10X · gerado em {quando:%d/%m/%Y %H:%M}',
                  'H', 6.6, T['tinta3'])
        w = pdf.texto(W - MARGEM, 37, 'OagronomIA', 'HBI', 9.5, T['tinta1'], alinh='dir')
        pdf.texto(W - MARGEM - w - 12, 37.5, f'{n}/{total}', 'M', 7.6, T['tinta2'], alinh='dir')


def gerar(v, caminho_pdf, quando=None):
    """Grava o PDF da visita `v` (já conferida). Devolve o número de páginas."""
    m = M.preparar(v)
    doc = Doc(v)
    _cabecalho(doc)
    _dados(doc)
    _localizacao(doc, m)
    _resumo(doc)
    _registros(doc)
    _transcricoes(doc)
    _rodapes(doc, quando or datetime.now())
    return doc.pdf.salvar(str(caminho_pdf))


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile
    from pathlib import Path

    import sintetico
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        v = V.carregar(sintetico.gravar(pasta))
        paginas = gerar(v, pasta / 'relatorio.pdf', datetime(2025, 11, 17, 18, 43))
        tamanho = (pasta / 'relatorio.pdf').stat().st_size
        assert 2 <= paginas <= 5 and 60_000 < tamanho < 3_000_000, (paginas, tamanho)
        sem = dict(v, satelite=None, perimetro=None, paradas=[], incluir_transcricoes=False,
                   grupos=[dict(g, parada=None) for g in v['grupos']])
        assert gerar(sem, pasta / 'sem-local.pdf') >= 2
        try:
            import fitz
        except ImportError:
            fitz = None
        if fitz:
            doc = fitz.open(str(pasta / 'relatorio.pdf'))
            assert not doc.is_repaired and doc.page_count == paginas
            texto = '\n'.join(p.get_text() for p in doc).replace(' ', '')     # título espaçado sai letra a letra
            links = [l['uri'] for p in doc for l in p.get_links()]
            imagens = sum(len(p.get_images()) for p in doc)
            doc.close()
            for trecho in ('Fazenda Exemplo (dados inventados)', 'DADOS DA VISITA', 'LOCALIZAÇÃO DA VISITA', 'RESUMO', 'OBSERVAÇÕES',
                           'REGISTROS DA VISITA', 'TRANSCRIÇÃO DOS ÁUDIOS', 'Pivô 1: estande e falhas', 'abrir no mapa', f'1/{paginas}',
                           'Imagem INVENTADA', 'NOTA · 09:25', 'foto-04.png'):
                assert trecho.replace(' ', '') in texto, trecho
            assert len(links) == 3 and links[0].startswith('https://www.google.com/maps?q=-22.70752')
            assert imagens == 7, imagens                               # 2 mapas e 5 fotos
            doc = fitz.open(str(pasta / 'sem-local.pdf'))
            texto = '\n'.join(p.get_text() for p in doc).replace(' ', '')
            doc.close()
            assert 'Nenhumalocalizaçãofoiinformada' in texto and 'TRANSCRIÇÃO' not in texto
    print(f'relatorio.py: autoteste ok (PDF de {paginas} páginas e {tamanho // 1024} KB, com mapa, fotos, links e transcrição'
          + ('; relido por outro leitor de PDF)' if fitz else ')'))


if __name__ == '__main__':
    _autoteste()
