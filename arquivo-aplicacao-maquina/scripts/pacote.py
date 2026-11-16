"""Grava o mapa de aplicação do jeito que o monitor espera e confere o que gravou.

O shapefile sai só com .shp, .shx e .dbf (sem .prj e sem .cpg), em graus
decimais, polígonos sem Z nem M, e o .dbf só com campos numéricos: ID e a
dose. Os três vão num zip com a árvore de pastas do controlador, para extrair
na raiz do pen drive.

Depois de gravar, o zip é relido e comparado com o que devia ter saído:
arquivos e pastas, número de polígonos, tipo do campo, doses, área e total de
produto.

Teste embutido: python scripts/pacote.py
"""

import datetime
import io
import struct
import zipfile

import controladores
import geom
import projecao
import shapefile

TOL_AREA = 1e-6          # diferença relativa de área aceita na releitura


def _br(v, casas):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def dbf_numerico(colunas, linhas):
    """colunas = [(nome, casas)], linhas = [[valores]]. Todos os campos saem do tipo N (número)."""
    textos = []
    for k, (_, casas) in enumerate(colunas):
        textos.append([f'{float(l[k]):.{casas}f}' if casas else str(int(round(float(l[k])))) for l in linhas])
    larguras = [max([len(t) for t in col] + [1]) for col in textos]
    if max(larguras) > 19:
        raise ValueError('número grande demais para um campo do .dbf (19 dígitos)')
    hoje = datetime.date.today()
    tam_reg = 1 + sum(larguras)
    saida = bytearray(struct.pack('<B3BIHH20x', 3, hoje.year - 1900, hoje.month, hoje.day, len(linhas), 32 + 32 * len(colunas) + 1, tam_reg))
    for (nome, casas), largura in zip(colunas, larguras):
        saida += struct.pack('<11sc4xBB14x', nome.encode('ascii'), b'N', largura, casas)
    saida += b'\x0d'
    for i in range(len(linhas)):
        saida += b' ' + b''.join(col[i].rjust(larg).encode('ascii') for col, larg in zip(textos, larguras))
    saida += b'\x1a'
    return bytes(saida)


def shapefile_de_maquina(poligonos, doses, campo, casas):
    """poligonos = geometrias (Polygon ou MultiPolygon) em graus; doses = números. Devolve {'shp', 'shx', 'dbf'}."""
    if len(poligonos) != len(doses) or not poligonos:
        raise ValueError('sem polígonos para gravar')
    brutos, _ = shapefile.gravar([{'geometry': g, 'properties': {}} for g in poligonos], [], '')
    dbf = dbf_numerico([('ID', 0), (campo, casas)], [[i + 1, d] for i, d in enumerate(doses)])
    return {'shp': brutos['shp'], 'shx': brutos['shx'], 'dbf': dbf}


def montar_zip(arquivos, chave, nome):
    """O zip para extrair na raiz do pen drive: só a árvore de pastas do controlador e os três arquivos."""
    pasta = controladores.CONTROLADORES[chave]['pasta']
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        partes, atual = [p for p in pasta.split('/') if p], ''
        for p in partes:
            atual += p + '/'
            z.writestr(zipfile.ZipInfo(atual), b'')
        for ext in ('shp', 'shx', 'dbf'):
            z.writestr(f'{atual}{nome}.{ext}', arquivos[ext])
    return buf.getvalue()


def _tipos_do_shp(dados):
    """O tipo de geometria do cabeçalho e o conjunto de tipos dos registros."""
    cab = struct.unpack('<i', dados[32:36])[0]
    tipos, pos = set(), 100
    while pos + 12 <= len(dados):
        _, tam = struct.unpack('>ii', dados[pos:pos + 8])
        tipos.add(struct.unpack('<i', dados[pos + 8:pos + 12])[0])
        pos += 8 + tam * 2
    return cab, tipos


def conferir(dados_zip, chave, nome, campo, casas, doses, areas_ha):
    """Relê o zip e compara. Devolve (tudo certo?, linhas do relato)."""
    linhas, ok = [], True

    def checa(cond, texto):
        nonlocal ok
        ok = ok and bool(cond)
        linhas.append(('certo: ' if cond else 'ERRADO: ') + texto)

    esperado = controladores.caminho_no_pen_drive(chave, nome)[:-4]
    with zipfile.ZipFile(io.BytesIO(dados_zip)) as z:
        membros = [n for n in z.namelist() if not n.endswith('/')]
        conteudo = {n: z.read(n) for n in membros}
    checa(sorted(membros) == sorted(f'{esperado}.{e}' for e in ('shp', 'shx', 'dbf')),
          f'o zip tem só {esperado}.shp, .shx e .dbf (achados: {", ".join(sorted(membros))})')
    if not ok:
        return False, linhas
    shp, dbf = conteudo[f'{esperado}.shp'], conteudo[f'{esperado}.dbf']
    cab, tipos = _tipos_do_shp(shp)
    checa(cab == 5 and tipos <= {5}, f'geometria: polígono simples, sem Z nem M (tipo {cab} no cabeçalho; registros {sorted(tipos)})')
    campos, registros, _ = shapefile.ler_dbf(dbf)
    checa([(c[0], c[1]) for c in campos] == [('ID', 'N'), (campo, 'N')],
          'campos do .dbf: ' + ', '.join(f'{c[0]} (tipo {c[1]}, {c[3]} casa(s))' for c in campos) + '; todos numéricos')
    lido = shapefile.ler({'shp': shp, 'dbf': dbf})
    feicoes = lido['feicoes']
    checa(len(feicoes) == len(doses), f'{len(feicoes)} polígono(s) relidos (esperado: {len(doses)})')
    if len(feicoes) != len(doses):
        return False, linhas
    xs = [p[0] for f in feicoes for s in geom.partes(f['geometry']) for p in s]
    ys = [p[1] for f in feicoes for s in geom.partes(f['geometry']) for p in s]
    checa(max(abs(x) for x in xs) <= 180 and max(abs(y) for y in ys) <= 90, 'coordenadas em graus decimais (longitude e latitude)')
    lidas = [f['properties'].get(campo) for f in feicoes]
    checa(all(isinstance(v, (int, float)) and abs(v - d) < 0.5 * 10 ** -casas + 1e-12 for v, d in zip(lidas, doses)),
          f'a dose de cada polígono é a que devia ser ({len(doses)} conferidas)')
    areas, _, _ = geom.medir(feicoes, projecao.geo('WGS 84'))
    area_lida, area_esperada = sum(areas), sum(areas_ha)
    checa(abs(area_lida - area_esperada) <= max(1e-6, area_esperada * TOL_AREA),
          f'área relida {_br(area_lida, 4)} ha (esperada: {_br(area_esperada, 4)} ha)')
    total_lido = sum(v * a for v, a in zip(lidas, areas))
    total_esperado = sum(d * a for d, a in zip(doses, areas_ha))
    checa(abs(total_lido - total_esperado) <= max(1e-6, abs(total_esperado) * 1e-5),
          f'dose × área relida {_br(total_lido, 3)} (esperada: {_br(total_esperado, 3)})')
    return ok, linhas


if __name__ == '__main__':
    quad = lambda x, y, t=0.002: [(x, y), (x + t, y), (x + t, y + t), (x, y + t), (x, y)]  # noqa: E731
    pols = [{'type': 'Polygon', 'coordinates': [quad(-51.0, -23.0)]},
            {'type': 'MultiPolygon', 'coordinates': [[quad(-50.998, -23.0)], [quad(-50.99, -23.0, 0.001)]]},
            {'type': 'Polygon', 'coordinates': [quad(-51.0, -22.998), quad(-50.9995, -22.9975, 0.0005)]}]
    doses = [120.0, 180.5, 0.0]
    areas, _, _ = geom.medir([{'geometry': g, 'properties': {}} for g in pols], projecao.geo('WGS 84'))
    arqs = shapefile_de_maquina(pols, doses, 'DOSE', 1)
    assert set(arqs) == {'shp', 'shx', 'dbf'}
    campos, regs, _ = shapefile.ler_dbf(arqs['dbf'])
    assert campos == [('ID', 'N', 1, 0), ('DOSE', 'N', 5, 1)] and [r['DOSE'] for r in regs] == doses and [r['ID'] for r in regs] == [1, 2, 3]
    for chave, c in controladores.CONTROLADORES.items():
        z = montar_zip(arqs, chave, 'ADUBO01')
        nomes = zipfile.ZipFile(io.BytesIO(z)).namelist()
        raiz = (c['pasta'] + '/') if c['pasta'] else ''
        assert f'{raiz}ADUBO01.shp' in nomes and not any(n.endswith(('.prj', '.cpg')) for n in nomes), (chave, nomes)
        ok, linhas = conferir(z, chave, 'ADUBO01', 'DOSE', 1, doses, areas)
        assert ok, (chave, linhas)
    z = montar_zip(arqs, 'raven', 'N1')
    assert zipfile.ZipFile(io.BytesIO(z)).namelist() == ['ePro/', 'ePro/WorkOrders/', 'ePro/WorkOrders/rxMaps/', 'ePro/WorkOrders/rxMaps/N1.shp',
                                                         'ePro/WorkOrders/rxMaps/N1.shx', 'ePro/WorkOrders/rxMaps/N1.dbf']
    # o conferidor pega dose trocada, polígono a menos e arquivo a mais
    assert not conferir(z, 'raven', 'N1', 'DOSE', 1, [120.0, 181.5, 0.0], areas)[0]
    assert not conferir(z, 'raven', 'N1', 'DOSE', 1, doses[:2], areas[:2])[0]
    assert not conferir(z, 'stara', 'N1', 'DOSE', 1, doses, areas)[0]
    buf = io.BytesIO(z)
    with zipfile.ZipFile(buf, 'a') as extra:
        extra.writestr('ePro/WorkOrders/rxMaps/N1.prj', b'x')
    assert not conferir(buf.getvalue(), 'raven', 'N1', 'DOSE', 1, doses, areas)[0]
    try:
        shapefile_de_maquina([], [], 'DOSE', 0)
    except ValueError:
        pass
    else:
        raise AssertionError('devia recusar o arquivo vazio')
    print('pacote OK: .dbf só com números, zip com a árvore de cada um dos 10 controladores, sem .prj nem .cpg, releitura que pega 4 erros')
