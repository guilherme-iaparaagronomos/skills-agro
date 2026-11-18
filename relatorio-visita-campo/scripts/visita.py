"""Lê e confere o arquivo da visita (visita.json) que a IA monta com o que o
usuário mandou, e escreve a versão em texto do relatório.

O formato do arquivo está em references/relatorio.md. A conferência junta
TODOS os problemas em uma lista só, para a IA corrigir de uma vez ou perguntar
ao usuário o que falta.

Teste embutido: python scripts/visita.py
"""

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

OBRIGATORIOS = [('fazenda', 'o nome da fazenda ou da área'), ('cidade', 'a cidade'), ('estado', 'o estado'),
                ('data', 'a data da visita'), ('visitante', 'quem fez a visita')]
OPCIONAIS = ['proprietario', 'empresa', 'safra', 'cultura', 'talhoes', 'tipo']
TIPOS_DE_VISITA = ['Monitoramento de pragas', 'Monitoramento de doenças', 'Plantas daninhas', 'Nutrição e fertilidade',
                   'Plantio', 'Colheita', 'Vistoria geral']
ORIGENS = {'usuario': 'informada por quem visitou', 'foto': 'GPS da foto', 'area': 'centro da área'}
SEM_LOGO = ('false', 'sem logo', 'nenhuma', 'não', 'nao', 'não tem', 'nao tem')
TETO = {'curto': 120, 'titulo': 90, 'texto': 4000, 'resumo': 1200, 'observacao': 500}
_HORA = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')


class VisitaInvalida(Exception):
    """O arquivo da visita tem problema. `problemas` traz a lista inteira."""

    def __init__(self, problemas):
        self.problemas = list(problemas)
        super().__init__('; '.join(self.problemas))


def limpo(valor, teto):
    """Texto de quem visitou: sem caracteres de controle nem invisíveis, com teto de tamanho."""
    s = str(valor if valor is not None else '')
    s = ''.join(c for c in s if c in '\n' or (ord(c) >= 32 and unicodedata.category(c) not in ('Cf', 'Cc', 'Co', 'Cs')))
    s = re.sub(r'[ \t]+', ' ', s).strip()
    return s[:teto]


def ler_data(valor):
    s = str(valor or '').strip()
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, formato).date()
        except ValueError:
            continue
    return None


def _hora(valor, onde, problemas):
    if valor in (None, ''):
        return None
    s = str(valor).strip().replace('h', ':').replace('H', ':')
    m = _HORA.match(s)
    if not m:
        problemas.append(f'{onde}: hora "{valor}" fora do formato HH:MM')
        return None
    return f'{int(m.group(1)):02d}:{m.group(2)}'


def _minutos(hora):
    return int(hora[:2]) * 60 + int(hora[3:])


def carregar(caminho, hoje=None):
    """Lê o visita.json e devolve a visita conferida. Levanta VisitaInvalida com todos os problemas."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise VisitaInvalida([f'não achei o arquivo {caminho}'])
    try:
        bruto = json.loads(caminho.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as e:
        raise VisitaInvalida([f'{caminho.name} não é um JSON válido (linha {e.lineno}: {e.msg})'])
    if not isinstance(bruto, dict):
        raise VisitaInvalida([f'{caminho.name}: o arquivo tem de ser um objeto com os dados da visita'])
    return conferir(bruto, caminho.parent, hoje)


def conferir(bruto, pasta='.', hoje=None):
    pasta = Path(pasta)
    hoje = hoje or date.today()
    problemas, avisos = [], []
    v = {'pasta': pasta}
    for campo, nome in OBRIGATORIOS:
        v[campo] = limpo(bruto.get(campo), TETO['curto'])
        if not v[campo]:
            problemas.append(f'falta {nome} ("{campo}"): pergunte ao usuário')
    for campo in OPCIONAIS:
        v[campo] = limpo(bruto.get(campo), TETO['curto']) or None
    if v['data']:
        d = ler_data(v['data'])
        if d is None:
            problemas.append(f'data da visita "{v["data"]}" não foi entendida: use AAAA-MM-DD ou dd/mm/aaaa')
        elif d > hoje:
            problemas.append(f'a data da visita ({d:%d/%m/%Y}) está no futuro: confirme com o usuário')
        v['data'] = d
    v['resumo'] = limpo(bruto.get('resumo'), TETO['resumo'])
    if not v['resumo']:
        problemas.append('falta o resumo da visita ("resumo")')
    obs = bruto.get('observacoes') or []
    if not isinstance(obs, list):
        problemas.append('"observacoes" tem de ser uma lista de frases')
        obs = []
    v['observacoes'] = [x for x in (limpo(o, TETO['observacao']) for o in obs[:10]) if x]

    # ---- logo da empresa de quem fez a visita: ou o arquivo, ou a resposta de que não há
    import fotos as F
    v['logo'] = None
    logo = bruto.get('logo')
    if logo is False or str(logo).strip().lower() in SEM_LOGO:
        pass
    elif logo in (None, ''):
        problemas.append('falta a logo da empresa de quem fez a visita ("logo"): peça o arquivo ao usuário (PNG ou JPEG). '
                         'Se ele disser que não tem ou não quer, grave "logo": false')
    else:
        try:
            v['logo'] = F.ler_logo(pasta / str(logo))
        except F.FotoInvalida as e:
            problemas.append(f'logo: {e}')

    # ---- paradas (os pontos da visita)
    v['paradas'], numeros = [], set()
    for i, p in enumerate(bruto.get('paradas') or [], 1):
        onde = f'parada {i}'
        if not isinstance(p, dict):
            problemas.append(f'{onde}: tem de ser um objeto com lat e lon')
            continue
        n = p.get('n', i)
        try:
            lat, lon = float(p.get('lat')), float(p.get('lon'))
        except (TypeError, ValueError):
            problemas.append(f'{onde}: latitude e longitude têm de ser números em graus decimais (ex.: -22.685, -50.985)')
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            problemas.append(f'{onde}: coordenada fora do globo ({lat}, {lon}); latitude e longitude podem estar trocadas')
            continue
        if n in numeros:
            problemas.append(f'{onde}: o número {n} está repetido')
            continue
        numeros.add(n)
        origem = str(p.get('origem') or 'usuario')
        v['paradas'].append({'n': n, 'lat': lat, 'lon': lon, 'hora': _hora(p.get('hora'), onde, problemas),
                             'nome': limpo(p.get('nome'), 60) or None,
                             'origem': ORIGENS.get(origem, limpo(origem, 60))})

    # ---- grupos (os assuntos), com as notas e as fotos de cada um
    v['grupos'], usadas, horas = [], {}, []
    grupos = bruto.get('grupos') or []
    if not isinstance(grupos, list) or not grupos:
        problemas.append('falta pelo menos um assunto em "grupos" (título, texto, fotos e notas do que foi visto)')
        grupos = []
    for i, g in enumerate(grupos, 1):
        onde = f'assunto {i}'
        if not isinstance(g, dict):
            problemas.append(f'{onde}: tem de ser um objeto com título, texto, notas e fotos')
            continue
        grupo = {'titulo': limpo(g.get('titulo'), TETO['titulo']), 'texto': limpo(g.get('texto'), TETO['texto']),
                 'parada': g.get('parada'), 'hora': _hora(g.get('hora'), onde, problemas), 'notas': [], 'fotos': []}
        if not grupo['titulo']:
            problemas.append(f'{onde}: falta o título')
        if grupo['parada'] is not None and grupo['parada'] not in numeros:
            problemas.append(f'{onde} ("{grupo["titulo"]}"): cita a parada {grupo["parada"]}, que não está em "paradas"')
        for k, nota in enumerate(g.get('notas') or [], 1):
            if isinstance(nota, str):
                nota = {'texto': nota}
            texto = limpo(nota.get('texto'), TETO['texto'])
            if texto:
                grupo['notas'].append({'texto': texto, 'hora': _hora(nota.get('hora'), f'{onde}, nota {k}', problemas)})
        for k, foto in enumerate(g.get('fotos') or [], 1):
            if isinstance(foto, str):
                foto = {'arquivo': foto}
            nome = str(foto.get('arquivo') or '').strip()
            ondef = f'{onde}, foto {k}'
            if not nome:
                problemas.append(f'{ondef}: falta o nome do arquivo')
                continue
            arq = (pasta / nome).resolve()
            if arq in usadas:
                problemas.append(f'{ondef}: {nome} já está no {usadas[arq]}. Cada foto entra em um assunto só')
                continue
            try:
                lida = F.ler(arq)
            except F.FotoInvalida as e:
                problemas.append(f'{ondef}: {e}')
                continue
            usadas[arq] = onde
            hora = _hora(foto.get('hora'), ondef, problemas)
            if hora is None and lida['quando'] is not None:
                hora = f'{lida["quando"]:%H:%M}'            # a hora gravada pela câmera
            descricao = limpo(foto.get('descricao'), 700)
            if not descricao:
                avisos.append(f'{ondef} ({nome}): sem descrição; a foto sai só com a hora')
            grupo['fotos'].append({'arquivo': nome, 'caminho': arq, 'imagem': lida['imagem'], 'descricao': descricao,
                                   'hora': hora, 'legenda': limpo(foto.get('legenda'), 300) or None,
                                   'lat': lida['lat'], 'lon': lida['lon']})
        if not (grupo['texto'] or grupo['notas'] or grupo['fotos']):
            problemas.append(f'{onde} ("{grupo["titulo"]}"): está vazio (sem texto, nota nem foto)')
        horas += [x['hora'] for x in grupo['fotos'] + grupo['notas'] if x['hora']] + ([grupo['hora']] if grupo['hora'] else [])
        v['grupos'].append(grupo)

    # ---- transcrições dos áudios
    v['transcricoes'] = []
    for k, t in enumerate(bruto.get('transcricoes') or [], 1):
        if isinstance(t, str):
            t = {'texto': t}
        texto = limpo(t.get('texto'), 12000)
        if texto:
            v['transcricoes'].append({'texto': texto, 'hora': _hora(t.get('hora'), f'transcrição {k}', problemas),
                                      'origem': limpo(t.get('origem'), 80) or None})
    v['incluir_transcricoes'] = bool(bruto.get('incluir_transcricoes')) and bool(v['transcricoes'])
    try:
        v['audios'] = max(0, int(bruto.get('audios', len(v['transcricoes']))))
    except (TypeError, ValueError):
        v['audios'] = len(v['transcricoes'])
        problemas.append('"audios" tem de ser o número de áudios recebidos')

    # ---- localização: perímetro e imagem de satélite (opcionais)
    v['perimetro'] = None
    if bruto.get('perimetro'):
        arq = pasta / str(bruto['perimetro'])
        if arq.is_file():
            v['perimetro'] = arq
        else:
            problemas.append(f'o arquivo do perímetro ({bruto["perimetro"]}) não foi encontrado')
    v['satelite'] = None
    sat = bruto.get('satelite')
    if sat:
        if not isinstance(sat, dict):
            problemas.append('"satelite" tem de ser um objeto com o arquivo da imagem e a data')
        else:
            s = {'rgb': None, 'ndvi': None, 'data': ler_data(sat.get('data')), 'credito': limpo(sat.get('credito'), 300) or None}
            try:
                s['sem_nuvem_pct'] = None if sat.get('sem_nuvem_pct') in (None, '') else float(sat['sem_nuvem_pct'])
            except (TypeError, ValueError):
                s['sem_nuvem_pct'] = None
            for chave in ('rgb', 'ndvi'):
                if sat.get(chave):
                    arq = pasta / str(sat[chave])
                    if arq.is_file():
                        s[chave] = arq
                    else:
                        problemas.append(f'imagem de satélite: o arquivo {sat[chave]} não foi encontrado (baixe pelo link da ferramenta)')
            if not s['rgb'] and not s['ndvi']:
                problemas.append('"satelite" não traz nenhum arquivo de imagem ("rgb" ou "ndvi")')
            if s['data'] is None:
                problemas.append('imagem de satélite: falta a data da cena ("data"), a que a ferramenta informou')
            v['satelite'] = s

    # ---- duração e contagens
    inicio, fim = _hora(bruto.get('inicio'), 'início da visita', problemas), _hora(bruto.get('fim'), 'fim da visita', problemas)
    horas += [p['hora'] for p in v['paradas'] if p['hora']]
    if not (inicio and fim) and len(set(horas)) >= 2:
        inicio, fim = min(horas), max(horas)
    v['duracao_min'] = (_minutos(fim) - _minutos(inicio)) if inicio and fim and _minutos(fim) > _minutos(inicio) else None
    v['n_fotos'] = sum(len(g['fotos']) for g in v['grupos'])
    v['n_notas'] = sum(len(g['notas']) for g in v['grupos'])
    if not v['paradas'] and not v['perimetro'] and not v['satelite']:
        avisos.append('nenhuma localização foi informada: o relatório sai sem mapa. Se o usuário tiver o ponto, o perímetro ou '
                      'a fazenda salva, pergunte')
    com_gps = [f for g in v['grupos'] for f in g['fotos'] if f['lat'] is not None]
    if com_gps and not v['paradas']:
        avisos.append(f'{len(com_gps)} foto(s) têm GPS gravado e nenhuma parada foi informada: as coordenadas podem virar paradas '
                      '(veja com --fotos)')
    v['avisos'] = avisos
    if problemas:
        raise VisitaInvalida(problemas)
    return v


# ------------------------------------------------------------------ texto
def duracao_txt(minutos):
    if not minutos:
        return None
    h, m = divmod(int(minutos), 60)
    return f'{h} h {m:02d}' if h else f'{m} min'


def coordenada_txt(lat, lon):
    return f'{lat:.5f}; {lon:.5f}'.replace('.', ',')


def link_do_mapa(lat, lon):
    return f'https://www.google.com/maps?q={lat:.6f},{lon:.6f}'


def dados_da_visita(v):
    """[(rótulo, valor)] do cartão "Dados da visita", só os preenchidos."""
    pares = [('Visita realizada por', v['visitante']), ('Tipo de visita', v['tipo']), ('Proprietário(a)', v['proprietario']),
             ('Safra', v['safra']), ('Cultura', v['cultura']), ('Talhões', v['talhoes']), ('Empresa', v['empresa'])]
    return [(r, x) for r, x in pares if x]


def cabecalho_da_parada(v, grupo):
    p = next((x for x in v['paradas'] if x['n'] == grupo['parada']), None)
    partes = []
    if p:
        partes.append(f'Parada {p["n"]}' + (f' ({p["nome"]})' if p['nome'] else ''))
    hora = grupo['hora'] or (p['hora'] if p else None)
    if hora:
        partes.append(hora)
    if p:
        partes.append(coordenada_txt(p['lat'], p['lon']))
    return ' · '.join(partes)


def texto_md(v):
    """O relatório em Markdown, com as mesmas seções do PDF."""
    linhas = [f'# Relatório de visita técnica — {v["fazenda"]}', '',
              f'{v["cidade"]} / {v["estado"]} · {v["data"]:%d/%m/%Y}', '', '## Dados da visita', '']
    linhas += [f'- {r}: {x}' for r, x in dados_da_visita(v)]
    contagem = [f'{v["n_fotos"]} foto(s)', f'{v["audios"]} áudio(s)', f'{v["n_notas"]} nota(s)', f'{len(v["paradas"])} parada(s)']
    if v['duracao_min']:
        contagem.append(f'duração de {duracao_txt(v["duracao_min"])}')
    linhas += [f'- Registros: {", ".join(contagem)}', '', '## Localização da visita', '']
    if v['paradas']:
        for p in v['paradas']:
            nome = f' ({p["nome"]})' if p['nome'] else ''
            hora = f' às {p["hora"]}' if p['hora'] else ''
            linhas.append(f'- Parada {p["n"]}{nome}: {coordenada_txt(p["lat"], p["lon"])} · {p["origem"]}{hora} · '
                          f'[abrir no mapa]({link_do_mapa(p["lat"], p["lon"])})')
    else:
        linhas.append('Nenhuma localização foi informada nesta visita.')
    if v['satelite']:
        s = v['satelite']
        linhas += ['', credito_da_imagem(s)]
    linhas += ['', '## Resumo', '', v['resumo'], '']
    if v['observacoes']:
        linhas += ['## Observações', ''] + [f'- {o}' for o in v['observacoes']] + ['']
    linhas += ['## Registros da visita', '']
    for g in v['grupos']:
        cab = cabecalho_da_parada(v, g)
        linhas.append(f'### {g["titulo"]}')
        if cab:
            linhas += ['', f'_{cab}_']
        if g['texto']:
            linhas += ['', g['texto']]
        for n in g['notas']:
            linhas += ['', '> Nota' + (f' · {n["hora"]}' if n['hora'] else '') + f': {n["texto"]}']
        for f in g['fotos']:
            hora = f' ({f["hora"]})' if f['hora'] else ''
            linhas += ['', f'- Foto `{f["arquivo"]}`{hora}: {f["descricao"] or "sem descrição"}']
        linhas.append('')
    if v['incluir_transcricoes']:
        linhas += ['## Transcrição dos áudios', '']
        for t in v['transcricoes']:
            linhas += [(f'**{t["hora"]}** — ' if t['hora'] else '') + t['texto'], '']
    linhas += ['---', '', 'As descrições das fotos foram escritas pela IA a partir das imagens e do que quem visitou informou; '
               'o conteúdo técnico é de responsabilidade de quem fez a visita.']
    return '\n'.join(linhas) + '\n'


def credito_da_imagem(s):
    if s['credito']:
        return s['credito']
    nuvem = ''
    if s['sem_nuvem_pct'] is not None:
        pct = f'{s["sem_nuvem_pct"]:.1f}'.rstrip('0').rstrip('.').replace('.', ',')
        nuvem = f' · {pct}% da área sem nuvem'
    return (f'Imagem Sentinel-2 de {s["data"]:%d/%m/%Y}{nuvem} · Copernicus Sentinel-2 L2A · contém dados modificados do '
            f'Copernicus Sentinel ({s["data"].year})')


# ------------------------------------------------------------------ teste embutido
def _autoteste():
    import tempfile

    from PIL import Image
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        for nome in ('f1.jpg', 'f2.jpg'):
            Image.new('RGB', (400, 300), (90, 140, 60)).save(pasta / nome)
        base = {
            'fazenda': 'Fazenda Exemplo', 'cidade': 'Cidade Exemplo', 'estado': 'MT', 'data': '17/11/2025', 'visitante': 'Fulano de Tal',
            'cultura': 'Soja', 'logo': False, 'resumo': 'Lavoura em V4.', 'observacoes': ['Quem visitou indicou reavaliar em sete dias.'],
            'paradas': [{'n': 1, 'lat': -22.68545, 'lon': -50.9854, 'hora': '10:11', 'nome': 'Pivô 1'}],
            'grupos': [{'titulo': 'Pivô 1: estande', 'texto': 'Estande uniforme.', 'parada': 1,
                        'notas': [{'hora': '10:12', 'texto': 'Chuva de 40 mm no sábado, segundo o produtor.'}],
                        'fotos': [{'arquivo': 'f1.jpg', 'descricao': 'Linhas de soja.', 'hora': '10:04'}, 'f2.jpg']}],
            'transcricoes': [{'hora': '10:05', 'texto': 'Aqui no pivô um a soja está em V4.'}], 'incluir_transcricoes': True,
        }
        v = conferir(base, pasta, hoje=date(2025, 11, 20))
        assert v['data'] == date(2025, 11, 17) and v['n_fotos'] == 2 and v['n_notas'] == 1 and v['audios'] == 1
        assert v['duracao_min'] == 8 and duracao_txt(96) == '1 h 36' and duracao_txt(8) == '8 min'
        assert v['paradas'][0]['origem'] == 'informada por quem visitou'
        assert any('sem descrição' in a for a in v['avisos'])
        md = texto_md(v)
        assert '# Relatório de visita técnica — Fazenda Exemplo' in md and 'Parada 1 (Pivô 1): -22,68545; -50,98540' in md
        assert '## Transcrição dos áudios' in md and 'maps?q=-22.685450,-50.985400' in md
        assert cabecalho_da_parada(v, v['grupos'][0]) == 'Parada 1 (Pivô 1) · 10:11 · -22,68545; -50,98540'

        ruim = dict(base, fazenda='', logo='', data='31/02/2025', resumo='', paradas=[{'lat': -95, 'lon': -50}, {'lat': 'x', 'lon': 1}],
                    grupos=[{'titulo': '', 'parada': 7, 'fotos': ['f1.jpg', 'f1.jpg', 'nao-existe.jpg']}, {'titulo': 'Vazio'}],
                    satelite={'rgb': 'falta.tif'}, perimetro='falta.geojson', inicio='25:00')
        try:
            conferir(ruim, pasta, hoje=date(2025, 11, 20))
        except VisitaInvalida as e:
            texto = ' | '.join(e.problemas)
            for trecho in ('falta o nome da fazenda', 'não foi entendida', 'falta o resumo', 'fora do globo', 'têm de ser números',
                           'falta o título', 'cita a parada 7', 'já está no assunto 1', 'não encontrado', 'está vazio',
                           'falta.tif', 'falta a data da cena', 'perímetro', 'fora do formato HH:MM', 'falta a logo'):
                assert trecho in texto, (trecho, texto)
            assert len(e.problemas) >= 14
        else:
            raise AssertionError('devia recusar')
        try:
            conferir(dict(base, data='2030-01-01'), pasta, hoje=date(2025, 11, 20))
        except VisitaInvalida as e:
            assert 'está no futuro' in e.problemas[0]
        else:
            raise AssertionError('devia recusar a data no futuro')
        sem_local = conferir(dict(base, paradas=[], grupos=[{'titulo': 'Geral', 'texto': 'Sem ponto.'}]), pasta, hoje=date(2025, 11, 20))
        assert any('nenhuma localização' in a for a in sem_local['avisos'])
        assert 'Nenhuma localização foi informada' in texto_md(sem_local)
        # a logo: o arquivo, ou a resposta de que não há; sem nenhum dos dois, o script manda pedir
        Image.new('RGB', (300, 90), (35, 117, 20)).save(pasta / 'logo.png')
        com_logo = conferir(dict(base, logo='logo.png'), pasta, hoje=date(2025, 11, 20))
        assert com_logo['logo'].size == (300, 90) and v['logo'] is None
        assert conferir(dict(base, logo='sem logo'), pasta, hoje=date(2025, 11, 20))['logo'] is None
        for valor, trecho in (('nao-existe.png', 'logo: nao-existe.png'), (None, 'falta a logo')):
            try:
                conferir(dict(base, logo=valor), pasta, hoje=date(2025, 11, 20))
            except VisitaInvalida as e:
                assert trecho in e.problemas[0], e.problemas
            else:
                raise AssertionError('devia cobrar a logo')
        assert limpo('a​\x07  b\n', 50) == 'a b'
    print('visita.py: autoteste ok (visita conferida, logo, texto do relatório, 16 problemas apontados de uma vez)')


if __name__ == '__main__':
    _autoteste()
