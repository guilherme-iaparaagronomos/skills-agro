"""As páginas do dossiê (A4 em pé): identificação, CAR, uso do solo, datas-marco,
PRODES/DETER, declarado × observado, relevo, figuras e fontes.

Regra de redação, igual em todas as páginas: o dossiê ESCREVE FATOS, cada um
com a fonte. Não usa "regular", "irregular", "apto", "atenção" nem recomenda
nada. Onde dois números de fontes diferentes aparecem lado a lado, mostra a
diferença e diz que as definições não são as mesmas.
"""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as Caminho  # noqa: E402

A4 = (8.27, 11.69)
plt.rcParams['figure.max_open_warning'] = 0  # o dossiê passa de 20 páginas; cada uma é fechada ao gravar
ESQ, DIR, BASE = 0.075, 0.925, 0.085
MARCA = 'OagronomIA'
ASSINATURA = 'comunidade agrônomo10X'
ROTULO_DOC = 'agrônomo10X · Dossiê de uso e ocupação do solo'
AVISO_RODAPE = 'Reúne fatos de bases públicas e de satélite. Não é laudo, parecer nem recomendação.'

# Tokens do design system da casa. "papel" é o modo claro, que o DS reserva para
# impressão e exports (é o do laudo de satélite e do relatório de visita);
# "escuro" é o terminal da marca. O verde é o único saturado do chrome; cores de
# terra e de dataviz ficam só em gráficos e mapas.
TEMAS = {
    'papel': dict(pagina='#FBFCF9', fg1='#121810', fg2='#3C4636', fg3='#6B7562', line='#D4DBCA',
                  line_forte='#B4BFA8', verde='#2E8B1E', mapa='#FFFFFF'),
    'escuro': dict(pagina='#0B100B', fg1='#F2F4EE', fg2='#B8BFB1', fg3='#7C8678', line='#2A3328',
                   line_forte='#3A4537', verde='#52C937', mapa='#131A13'),
}
T = dict(TEMAS['papel'])
# papel da fonte → família. As do DS entram quando estão instaladas ou numa pasta
# (--fontes); o pacote da skill é só texto e não carrega arquivo de fonte.
FONTES_DO_DS = {'titulo': ('Chakra Petch', 'DejaVu Sans'), 'rotulo': ('Chakra Petch', 'DejaVu Sans'),
                'corpo': ('Manrope', 'DejaVu Sans'), 'num': ('JetBrains Mono', 'DejaVu Sans Mono')}
F = {papel: reserva for papel, (_, reserva) in FONTES_DO_DS.items()}


def usar_tema(nome='papel', pasta_de_fontes=None):
    """Liga o tema e resolve as fontes. Devolve as famílias em uso."""
    from matplotlib import font_manager

    T.clear()
    T.update(TEMAS[nome])
    if pasta_de_fontes:
        for fonte in sorted(Path(pasta_de_fontes).glob('*.[ot]tf')):
            try:
                font_manager.fontManager.addfont(str(fonte))
            except Exception:  # noqa: BLE001 - arquivo de fonte ilegível não derruba o dossiê
                pass
    instaladas = sorted({f.name for f in font_manager.fontManager.ttflist})
    peso = {'titulo': 'semibold', 'rotulo': 'medium', 'corpo': 'medium', 'num': 'regular'}
    for papel, (preferida, reserva) in FONTES_DO_DS.items():
        # arquivo de peso avulso registra a família com o peso no nome ("Chakra Petch SemiBold")
        candidatas = [n for n in instaladas if n == preferida or n.startswith(preferida + ' ')]
        do_peso = [n for n in candidatas if peso[papel] in n.lower().replace(' ', '')]
        F[papel] = (do_peso or candidatas or [reserva])[0]
    matplotlib.rcParams.update({
        'font.family': F['corpo'], 'text.color': T['fg1'], 'axes.labelcolor': T['fg3'],
        'xtick.color': T['fg3'], 'ytick.color': T['fg3'], 'axes.edgecolor': T['line'],
        'figure.facecolor': T['pagina'], 'axes.facecolor': T['pagina'], 'savefig.facecolor': T['pagina'],
    })
    return dict(F)


usar_tema('papel')


def espacado(texto):
    """Caixa alta com as letras afastadas: o rótulo ("eyebrow") do design system."""
    return '\u2009'.join(str(texto).upper())


COR_SITUACAO = [('nativa', '#7bc977'), ('já existia', '#e2dccb'), ('2009', '#e8b13a'),
                ('em 2020', '#e07b39'), ('depois de 2020', '#c0392b'), ('água', '#bfd3e6')]
TIPOS = {'IRU': 'Imóvel rural (IRU)', 'AST': 'Assentamento (AST)',
         'PCT': 'Território de povos e comunidades tradicionais (PCT)'}
COR_TEMA = {'reserva_legal': '#1b7837', 'vegetacao_nativa': '#a6dba0', 'area_consolidada': '#f1e3c2',
            'app': '#4393c3', 'uso_restrito': '#b2abd2', 'embargo': '#d6604d', 'outros': '#cccccc'}


def br(v, casas=1):
    """Número em formato brasileiro: 1669.5 → '1.669,5'."""
    if v is None:
        return '—'
    texto = f'{float(v):,.{casas}f}'
    if float(texto.replace(',', '')) == 0:
        texto = texto.lstrip('-')  # -0,0 não existe
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.').replace('-', '−')


def cor_da_classe(nome):
    """Cor por grupo de classe do mapeamento (nativa, pasto, lavoura, silvicultura, água…)."""
    n = nome.lower()
    if any(t in n for t in ('florest', 'savân', 'mangue', 'restinga', 'apicum', 'árvore')):
        return '#1f8d49'
    if 'pastagem' in n or 'gramínea' in n:  # antes de "campo": "Gramíneas (pasto e campo)"
        return '#edde8e'
    if any(t in n for t in ('campo', 'alagad', 'pantan', 'afloramento', 'herbác', 'campestre')):
        return '#b8af4f'
    if 'solo exposto' in n:
        return '#c26a3d'
    if 'arbusto' in n:
        return '#8a7556'
    if 'mosaico' in n:
        return '#ffefc3'
    if 'silvicultura' in n:
        return '#7a5900'
    if any(t in n for t in ('água', 'agua', 'rio', 'lago', 'aquicultura', 'oceano')):
        return '#2532e4'
    if any(t in n for t in ('urban', 'mineração', 'praia', 'não vegetada', 'duna', 'construída')):
        return '#d4271e'
    return '#e974ed'  # lavouras: soja, cana, café, citrus, arroz, algodão…


class Folha:
    """Uma página A4 com cursor vertical: cada bloco é escrito e empurra o cursor.
    O chrome segue o laudo da casa: rótulo verde em caixa alta, fio fino, título de
    seção em caixa alta, números em fonte mono e rodapé com a marca."""

    def __init__(self, doc, capa=False):
        self.doc = doc
        self.fig = plt.figure(figsize=A4, facecolor=T['pagina'])
        self.fig.text(ESQ, 0.964, espacado(ROTULO_DOC), fontsize=6.4, color=T['verde'], va='center',
                      family=F['rotulo'], fontweight='bold')
        if capa:
            self.y = 0.945
        else:
            self.fig.text(DIR, 0.964, doc.get('nome') or '', fontsize=7.5, color=T['fg3'], va='center', ha='right')
            self.fio(0.950)
            self.y = 0.934

    @staticmethod
    def _alt(tam, linhas=1, entre=1.5):
        return tam * entre * linhas / (A4[1] * 72)

    def fio(self, y, forte=False):
        self.fig.add_artist(plt.Line2D([ESQ, DIR], [y, y], color=T['line_forte' if forte else 'line'], linewidth=0.8))

    def espaco(self, h=0.012):
        self.y -= h

    def capa(self, titulo, subtitulo, kpis):
        """Cabeçalho da primeira página: nome do imóvel em display itálico e os números à direita."""
        x = DIR
        for rotulo, valor, unidade in reversed(kpis):
            self.fig.text(x, self.y, espacado(rotulo), fontsize=5.8, color=T['fg3'], va='top', ha='right',
                          family=F['rotulo'])
            self.fig.text(x, self.y - 0.016, valor, fontsize=17, color=T['fg1'], va='top', ha='right',
                          family=F['num'], fontweight='bold')
            self.fig.text(x, self.y - 0.043, unidade, fontsize=7, color=T['fg3'], va='top', ha='right',
                          family=F['num'])
            x -= 0.165
        # o título usa só a largura que sobra à esquerda dos números
        livre = ((x + 0.025 if kpis else DIR) - ESQ) * A4[0] * 72
        titulo = titulo or ''
        if len(titulo) <= int(livre / (19 * 0.62)):
            linhas, tam = [titulo], 19
        else:
            linhas, tam = (textwrap.wrap(titulo, max(12, int(livre / (15 * 0.62))))[:2] or ['']), 15
        self.fig.text(ESQ, self.y - 0.004, '\n'.join(linhas), fontsize=tam, color=T['fg1'], va='top',
                      family=F['titulo'], fontstyle='italic', fontweight='bold', linespacing=1.12)
        # o subtítulo desce para baixo do título E dos números: ele pode ser longo (o número do CAR)
        y_sub = min(self.y - 0.004 - self._alt(tam, len(linhas), 1.25), self.y - 0.058 if kpis else 1) - 0.006
        if subtitulo:
            self.fig.text(ESQ, y_sub, subtitulo, fontsize=9.5, color=T['fg2'], va='top')
        self.y = y_sub - self._alt(9.5, 1, 1.6)
        self.fio(self.y)
        self.y -= 0.014

    def secao(self, texto):
        self.y -= 0.010
        self.fig.text(ESQ, self.y, espacado(texto), fontsize=8.4, fontweight='bold', color=T['fg1'], va='top',
                      family=F['rotulo'])
        self.y -= self._alt(8.4, 1, 1.75)
        self.fio(self.y)
        self.y -= 0.010

    def texto(self, texto, tam=9, cor=None, negrito=False, recuo=0.0):
        colunas = int((DIR - ESQ - recuo) * A4[0] * 72 / (tam * 0.565))
        linhas = textwrap.wrap(texto, colunas) or ['']
        self.fig.text(ESQ + recuo, self.y, '\n'.join(linhas), fontsize=tam, color=cor or T['fg1'], va='top',
                      linespacing=1.45, fontweight='bold' if negrito else 'normal')
        self.y -= self._alt(tam, len(linhas), 1.47) + 0.004

    def nota(self, texto):
        self.texto(texto, tam=7.8, cor=T['fg3'])

    def pares(self, linhas, x_valor=0.34):
        for rotulo, valor in linhas:
            if valor in (None, ''):
                continue
            self.fig.text(ESQ, self.y, rotulo, fontsize=9, color=T['fg3'], va='top')
            colunas = int((DIR - x_valor) * A4[0] * 72 / (9 * 0.565))
            partes = textwrap.wrap(str(valor), colunas) or ['']
            self.fig.text(x_valor, self.y, '\n'.join(partes), fontsize=9, color=T['fg1'], va='top', linespacing=1.45)
            self.y -= self._alt(9, len(partes), 1.47) + 0.0035

    def tabela(self, colunas, linhas, tam=8.6, negrito_ultima=False):
        """colunas: [(título, x, 'left'|'right')] · linhas: listas de texto.
        Coluna alinhada à direita é número: sai em fonte mono, como manda o DS."""
        for titulo, x, alinh in colunas:
            self.fig.text(x, self.y, espacado(titulo), fontsize=5.6, color=T['fg3'], va='top', ha=alinh,
                          family=F['rotulo'])
        self.y -= self._alt(tam, 1, 1.5)
        self.fio(self.y)
        self.y -= 0.006
        for i, linha in enumerate(linhas):
            peso = 'bold' if negrito_ultima and i == len(linhas) - 1 else 'normal'
            for (_, x, alinh), celula in zip(colunas, linha):
                numero = alinh == 'right'
                self.fig.text(x, self.y, celula, fontsize=tam - (0.5 if numero else 0), color=T['fg1'], va='top',
                              ha=alinh, fontweight=peso, family=F['num' if numero else 'corpo'])
            self.y -= self._alt(tam, 1, 1.62)
        self.y -= 0.006

    def eixo(self, altura, esq=ESQ, direita=DIR):
        ax = self.fig.add_axes([esq, self.y - altura, direita - esq, altura])
        ax.set_facecolor(T['pagina'])
        self.y -= altura + 0.012
        return ax

    def sobra(self):
        return self.y - BASE

    def fechar(self, n, total):
        self.fio(0.060)
        data = self.doc.get('data') or ''
        self.fig.text(ESQ, 0.046, f'{ASSINATURA} · gerado em {data}', fontsize=7, color=T['fg3'], va='center')
        self.fig.text(ESQ, 0.032, AVISO_RODAPE, fontsize=6.4, color=T['fg3'], va='center')
        self.fig.text(DIR, 0.040, MARCA, fontsize=10.5, color=T['fg1'], va='center', ha='right',
                      family=F['titulo'], fontstyle='italic', fontweight='bold')
        self.fig.text(DIR - 0.145, 0.040, f'{n}/{total}', fontsize=7.5, color=T['fg3'], va='center', ha='right',
                      family=F['num'])
        return self.fig


# ------------------------------------------------------------------ desenhos
def _limpar(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_color(T['line'])


def _escala_e_norte(ax):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    largura, altura = x1 - x0, y1 - y0
    alvo = largura / 4
    base = 10 ** int(np.floor(np.log10(alvo)))
    comprimento = next((base * m for m in (5, 2, 1) if base * m <= alvo), base)
    bx, by = x0 + largura * 0.04, y0 + altura * 0.05
    ax.plot([bx, bx + comprimento], [by, by], color=T['fg1'], linewidth=2.5, solid_capstyle='butt')
    rotulo = f'{comprimento / 1000:g} km'.replace('.', ',') if comprimento >= 1000 else f'{comprimento:g} m'
    ax.annotate(rotulo, (bx + comprimento / 2, by), xytext=(0, 4), textcoords='offset points',
                ha='center', fontsize=7, color=T['fg1'])
    ax.annotate('N', xy=(0.955, 0.94), xycoords='axes fraction', ha='center', fontsize=9, fontweight='bold')
    ax.annotate('', xy=(0.955, 0.93), xycoords='axes fraction', xytext=(0.955, 0.85),
                textcoords='axes fraction', arrowprops={'arrowstyle': '-|>', 'color': T['fg1'], 'linewidth': 1.1})


def desenhar_perimetro(ax, aneis, temas=None):
    """Contorno do imóvel (metros) e, se houver, os polígonos declarados no CAR."""
    for grupo, poligonos in (temas or []):
        for aneis_do_poligono in poligonos:
            caminho = Caminho.make_compound_path(*[Caminho(np.asarray(a)) for a in aneis_do_poligono if len(a) > 2])
            ax.add_patch(PathPatch(caminho, facecolor=COR_TEMA.get(grupo, '#cccccc'), edgecolor='none', alpha=0.9))
    for anel in aneis:
        xs = [p[0] for p in anel] + [anel[0][0]]
        ys = [p[1] for p in anel] + [anel[0][1]]
        ax.plot(xs, ys, color=T['fg1'], linewidth=1.0)
    todos_x = [p[0] for a in aneis for p in a]
    todos_y = [p[1] for a in aneis for p in a]
    mx, my = (max(todos_x) - min(todos_x)) * 0.06, (max(todos_y) - min(todos_y)) * 0.06
    ax.set_xlim(min(todos_x) - mx, max(todos_x) + mx)
    ax.set_ylim(min(todos_y) - my, max(todos_y) + my)
    ax.set_aspect('equal')
    ax.set_anchor('C')
    ax.set_facecolor(T['mapa'])
    _limpar(ax)
    _escala_e_norte(ax)


def barras_horizontais(ax, itens, unidade='ha'):
    """itens: [(rótulo, valor, pct|None, cor)] — a maior em cima, com o número ao lado."""
    itens = list(itens)[::-1]
    maior = max(v for _, v, _, _ in itens) or 1.0
    ax.barh(range(len(itens)), [v for _, v, _, _ in itens], color=[c for *_, c in itens],
            edgecolor=T['line_forte'], linewidth=0.4, height=0.68)
    for i, (rotulo, valor, pct, _) in enumerate(itens):
        texto = f'{br(valor)} {unidade}' + (f'  ({br(pct, 0)} %)' if pct is not None else '')
        ax.text(valor + maior * 0.012, i, texto, va='center', fontsize=8, color=T['fg1'])
    ax.set_yticks(range(len(itens)))
    ax.set_yticklabels([r for r, *_ in itens], fontsize=8.3, color=T['fg1'])
    ax.set_xlim(0, maior * 1.30)
    ax.set_xticks([])
    ax.tick_params(length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)


# -------------------------------------------------------------------- páginas
def pagina_identificacao(doc, d, aneis, zona_txt):
    f = Folha(doc, capa=True)
    car = d.get('car') or {}
    uso = d.get('uso') or {}
    kpis = []
    if uso.get('area_ha'):
        kpis.append(('Área', br(uso['area_ha']), 'ha'))
    if uso.get('hoje'):
        kpis.append((f"Nativa em {uso['hoje']['ano']}", br(uso['hoje']['nativa_pct'], 0), '% do perímetro'))
    if uso.get('aberto_desde'):
        kpis.append(('Aberto após 2008', br(uso['aberto_desde'][2008]), 'ha'))
    municipio = doc.get('municipio') or (f"{car.get('municipio')}/{car.get('uf')}" if car.get('municipio') else None)
    f.capa(doc.get('nome'), ' · '.join(t for t in (municipio, f"CAR {car['car']}" if car.get('car') else None) if t), kpis)
    areas = [b['area_ha'] for b in (d.get('uso'), d.get('prodes'), d.get('relevo')) if b and b.get('area_ha')]
    f.secao('Identificação')
    f.pares([
        ('Imóvel', doc.get('nome')),
        ('Município', doc.get('municipio') or (f"{car.get('municipio')}/{car.get('uf')}" if car.get('municipio') else None)),
        ('Número do CAR', car.get('car')),
        ('Área do perímetro analisado', f'{br(areas[0])} ha' if areas else None),
        ('Área declarada no CAR', f"{br(car['area_declarada_ha'], 2)} ha" if car.get('area_declarada_ha') else None),
        ('Coordenada de referência', f"{car['latitude']}  {car['longitude']}" if car.get('latitude') else doc.get('centro')),
        ('Origem do perímetro', doc.get('origem_perimetro')),
        ('Imagem de satélite mais recente', doc.get('imagem')),
        ('Solicitante', doc.get('solicitante')),
        ('Responsável técnico', doc.get('responsavel')),
        ('Data do dossiê', doc.get('data')),
    ])
    f.secao('Perímetro analisado')
    ax = f.eixo(0.30)
    desenhar_perimetro(ax, aneis)
    f.nota(f'Contorno do perímetro usado em todas as consultas. {zona_txt}')
    f.secao('Como ler este documento')
    f.texto('Este dossiê reúne, num só lugar, o que bases públicas e mapeamentos por satélite registram sobre '
            'o perímetro acima. Cada número vem acompanhado da fonte e do ano a que se refere.')
    f.texto('O documento mostra os dados; não os avalia. Não é laudo, parecer, análise de conformidade nem '
            'recomendação, e não conclui se o imóvel atende a qualquer norma. A interpretação cabe ao '
            'responsável técnico, que conhece a área e pode conferir em campo.')
    f.texto('Mapeamentos por satélite têm erro de classificação e pixel de 30 m: mancha pequena pode não '
            'existir no terreno, e a borda do imóvel mistura o que está fora dele.')
    return f


def pagina_car(doc, car, aneis, temas_geo):
    f = Folha(doc)
    f.secao('Cadastro Ambiental Rural (CAR) — o que está declarado')
    f.texto('Dados públicos do SICAR, como constam na data da consulta. São declarações do proprietário ou '
            'possuidor; a análise delas cabe ao órgão ambiental.')
    status = car.get('status') or {}
    situacao = status.get('codigo') or None
    if situacao and status.get('texto'):
        situacao = f"{status['texto']} (código {status['codigo']})"
    retificacao = car.get('ultima_retificacao')
    if retificacao and car.get('numero_retificacao') is not None:
        retificacao += f" (retificação nº {car['numero_retificacao']})"
    f.pares([
        ('Número', car.get('car')),
        ('Situação do cadastro', situacao),
        ('Condição da análise', car.get('situacao_analise')),
        ('Tipo de imóvel', TIPOS.get(car.get('tipo_imovel'), car.get('tipo_imovel'))),
        ('Data de inscrição', car.get('data_cadastro')),
        ('Última retificação', retificacao),
        ('Módulos fiscais', br(car['modulos_fiscais'], 2) if car.get('modulos_fiscais') is not None else None),
        ('Área declarada', f"{br(car['area_declarada_ha'], 2)} ha" if car.get('area_declarada_ha') else None),
        ('Consulta feita em', _data_br(car.get('consultado_em'))),
    ])
    sobre = [(k, v) for k, v in (car.get('sobreposicoes') or {}).items() if v is not None]
    if sobre:
        f.secao('Sobreposições informadas pelo SICAR')
        f.tabela([('Com', ESQ, 'left'), ('Valor informado', 0.55, 'right')],
                 [[k, br(v, 2)] for k, v in sobre])
        f.nota('Valor como o serviço público do SICAR devolve para o imóvel; o serviço não documenta a unidade.')
    temas = [t for t in car.get('temas', []) if 'area_ha' in t]
    total = car.get('area_declarada_ha') or 0
    f.secao('Áreas declaradas no cadastro')
    if temas:
        f.tabela([('Tema', ESQ, 'left'), ('Polígonos', 0.63, 'right'), ('Área (ha)', 0.78, 'right'),
                  ('% do imóvel', DIR, 'right')],
                 [[t['rotulo'], str(t['feicoes']), br(t['area_ha'], 2),
                   br(100 * t['area_ha'] / total, 1) if total else '—'] for t in temas])
        nota = 'Os temas podem se sobrepor (a reserva legal costuma estar sobre a vegetação nativa; as APPs, sobre as duas): não some as linhas.'
        if not car.get('app_consultada'):
            nota += ' As camadas de APP não foram consultadas.'
        elif not any(t['grupo'] == 'app' for t in temas):
            nota += ' Nenhuma camada de APP trouxe polígono para este imóvel.'
        f.nota(nota)
    else:
        f.texto('O serviço não devolveu polígonos de reserva legal, vegetação nativa, área consolidada ou APP para este imóvel.')
    sem_resposta = [t['rotulo'] for t in car.get('temas', []) if 'erro' in t]
    if sem_resposta:
        f.nota('Sem resposta do serviço na consulta de: ' + '; '.join(sem_resposta) + '.')
    if temas_geo and f.sobra() > 0.24:
        ax = f.eixo(min(0.34, f.sobra() - 0.05))
        desenhar_perimetro(ax, aneis, temas_geo)
        grupos = []
        for grupo, _ in temas_geo:
            if grupo not in grupos:
                grupos.append(grupo)
        nomes = {'reserva_legal': 'Reserva legal', 'vegetacao_nativa': 'Vegetação nativa',
                 'area_consolidada': 'Área consolidada', 'app': 'APP', 'uso_restrito': 'Uso restrito',
                 'embargo': 'Área embargada', 'outros': 'Outros temas'}
        ax.legend(handles=[Rectangle((0, 0), 1, 1, facecolor=COR_TEMA.get(g, '#ccc'), edgecolor=T['line_forte'],
                                     linewidth=0.4) for g in grupos],
                  labels=[nomes.get(g, g) for g in grupos], loc='lower left', bbox_to_anchor=(1.02, 0.0),
                  fontsize=7.5, frameon=False)
        f.nota('Polígonos declarados no CAR. A reserva legal e as APPs são desenhadas por cima da vegetação nativa e da área consolidada.')
    return f


def pagina_uso(doc, uso):
    f = Folha(doc)
    f.secao('Uso e cobertura do solo — mapeamento anual')
    f.texto(f'Pelo mapeamento do {uso["fonte"]}: mapas anuais de 30 m, de {uso.get("ano_inicial", "1985")} a '
            f'{uso.get("ano_final", "")}. Cada mapa representa o ano inteiro.')
    hoje = uso.get('hoje')
    if hoje:
        f.texto(f'Mapa de {hoje["ano"]}', negrito=True)
        classes = hoje['classes'][:12]
        ax = f.eixo(0.022 * len(classes) + 0.012, esq=ESQ + 0.21)
        barras_horizontais(ax, [(n, ha, pct, cor_da_classe(n)) for n, ha, pct in classes])
        f.texto(f'Vegetação nativa no mapa de {hoje["ano"]}: {br(hoje["nativa_ha"])} ha '
                f'({br(hoje["nativa_pct"], 0)} % do perímetro).')
    marcos = uso.get('marcos') or []
    if marcos:
        f.secao('Nas datas-marco')
        anos = [(m['ano'], m) for m in marcos]
        if hoje and hoje['ano'] not in [a for a, _ in anos]:
            anos.append((hoje['ano'], {'classes': hoje['classes'], 'nativa_ha': hoje['nativa_ha']}))
        maiores = {}
        for _, m in anos:
            for nome, ha, _ in m['classes']:
                maiores[nome] = max(maiores.get(nome, 0), ha)
        nomes = sorted(maiores, key=lambda n: -maiores[n])[:11]
        xs = np.linspace(0.47, DIR, len(anos))
        colunas = [('Classe (ha)', ESQ, 'left')] + [(str(a), x, 'right') for (a, _), x in zip(anos, xs)]
        linhas = []
        for nome in nomes:
            linha = [nome]
            for _, m in anos:
                ha = next((h for n, h, _ in m['classes'] if n == nome), None)
                linha.append(br(ha) if ha is not None else '—')
            linhas.append(linha)
        linhas.append(['Vegetação nativa (total)'] + [br(m['nativa_ha']) for _, m in anos])
        f.tabela(colunas, linhas, negrito_ultima=True)
        legenda = ' · '.join(f'{m["ano"]}: {m["rotulo"]}' for m in marcos if m.get('rotulo'))
        f.nota(legenda + '.')
        f.nota('Cada data-marco lista as cinco maiores classes daquele ano; "—" indica classe fora das cinco '
               'maiores ou ausente. O mapa é do ano inteiro, não do dia do marco.')
    return f


def pagina_marcos(doc, uso):
    f = Folha(doc)
    f.secao('Situação de cada área frente às datas-marco')
    f.texto('"Aberto" = era vegetação nativa no mapa daquele ano e está em uso no último mapa. Cada pixel entra '
            f'numa faixa só. Fonte: {uso["fonte"]}.')
    situacao = uso.get('situacao') or []
    total = sum(ha for _, ha in situacao) or 1.0
    if situacao:
        ax = f.eixo(0.035)
        inicio = 0.0
        for nome, ha in situacao:
            cor = next((c for chave, c in COR_SITUACAO if chave in nome.lower()), '#cccccc')
            ax.barh(0, ha, left=inicio, color=cor, edgecolor=T['line_forte'], linewidth=0.4, height=0.8)
            inicio += ha
        ax.set_xlim(0, total)
        ax.axis('off')
        f.tabela([('Faixa', ESQ + 0.03, 'left'), ('Área (ha)', 0.74, 'right'), ('% do perímetro', DIR, 'right')],
                 [[nome, br(ha), br(100 * ha / total, 1)] for nome, ha in situacao])
        y = f.y + 0.006 + f._alt(8.6, len(situacao), 1.62)
        for i, (nome, _) in enumerate(situacao):
            cor = next((c for chave, c in COR_SITUACAO if chave in nome.lower()), '#cccccc')
            f.fig.add_artist(Rectangle((ESQ, y - f._alt(8.6, i, 1.62) - 0.0115), 0.018, 0.0105,
                                       transform=f.fig.transFigure, facecolor=cor, edgecolor=T['line_forte'],
                                       linewidth=0.4))
    aberto = uso.get('aberto_desde')
    if aberto:
        f.secao('Área aberta depois de cada marco')
        f.tabela([('Marco', ESQ, 'left'), ('Aberto depois (ha)', DIR, 'right')],
                 [['2008 — Código Florestal (22/07/2008)', br(aberto[2008])],
                  ['2019 — crédito rural (31/07/2019)', br(aberto[2019])],
                  ['2020 — regulamento europeu EUDR (31/12/2020)', br(aberto[2020])]])
    por_ano = uso.get('abertura_por_ano') or []
    if por_ano:
        f.secao('Ano em que cada área foi aberta')
        ax = f.eixo(0.21, esq=ESQ + 0.045)
        anos = [a for a, _ in por_ano]
        cores = ['#9ca3af' if a <= 2008 else '#e8b13a' if a <= 2019 else '#e07b39' if a == 2020 else '#c0392b'
                 for a in anos]
        ax.bar(anos, [h for _, h in por_ano], color=cores, edgecolor=T['line_forte'], linewidth=0.3, width=0.8)
        for marco in (2008, 2019, 2020):
            ax.axvline(marco + 0.5, color=T['line_forte'], linewidth=0.7, linestyle='--')
        ax.set_ylabel('ha', fontsize=8, color=T['fg3'])
        ax.tick_params(labelsize=7.5, colors=T['fg3'], length=2)
        for lado in ('top', 'right'):
            ax.spines[lado].set_visible(False)
        for lado in ('left', 'bottom'):
            ax.spines[lado].set_color(T['line'])
        f.espaco(0.016)
        f.nota('Área hoje em uso que era vegetação nativa no mapa do ano anterior. As linhas tracejadas '
               'separam 2008, 2019 e 2020. Cinza: até 2008; amarelo: 2009 a 2019; laranja: 2020; vermelho: '
               'depois de 2020.')
    f.nota('Mancha pequena (poucos pixels de 30 m) pode ser erro de classificação; a confirmação é a imagem do '
           'ano e a visita ao local. Este mapeamento não é a base oficial do crédito rural: essa é o PRODES, '
           'do INPE, na página seguinte.')
    return f


def pagina_cobertura(doc, cb):
    f = Folha(doc)
    f.secao('Cobertura do solo recente — classificação de 10 m')
    periodo = f' Período de {cb["periodo"][0]} a {cb["periodo"][1]}.' if cb.get('periodo') else ''
    imagens = (f' {cb["dias_com_imagem"]} dias com imagem; a última em {cb["ultima_imagem"]}.'
               if cb.get('dias_com_imagem') else '')
    f.texto(f'Pelo Dynamic World: classificação automática de cada imagem Sentinel-2, com pixel de 10 m.{periodo}'
            f'{imagens} A classe de cada pixel é a mais provável na média das imagens do período.')
    classes = cb.get('classes') or []
    if classes:
        ax = f.eixo(0.022 * len(classes) + 0.012, esq=ESQ + 0.21)
        barras_horizontais(ax, [(c['nome'], c['ha'], c['pct'], cor_da_classe(c['nome'])) for c in classes])
        f.tabela([('Classe', ESQ, 'left'), ('ha', 0.42, 'right'), ('%', 0.48, 'right'),
                  ('Prob. média', 0.60, 'right'), ('2ª classe mais provável', 0.64, 'left')],
                 [[c['nome'], br(c['ha']), br(c['pct'], 0), f"{br(c['probabilidade'], 0)} %",
                   f"{c['segunda']} ({br(c['segunda_pct'], 0)} %)" if c.get('segunda') else '—'] for c in classes],
                 tam=8.2)
    if cb.get('faixas'):
        f.secao('Probabilidade da classe escolhida')
        f.tabela([('Faixa de probabilidade', ESQ, 'left'), ('ha', 0.78, 'right'), ('% do perímetro', DIR, 'right')],
                 [[nome[0].upper() + nome[1:], br(ha), br(pct, 0)] for nome, ha, pct in cb['faixas']])
        if cb.get('probabilidade_media') is not None:
            f.nota(f'Probabilidade média da classe escolhida no perímetro: {br(cb["probabilidade_media"], 0)} %. '
                   'Probabilidade menor não quer dizer classe errada: mata e água costumam ficar perto de 70 %; '
                   'lavoura anual, pasto e arbusto, entre 30 e 50 %.')
    f.nota('As classes são genéricas: "Lavoura" não diz qual cultura e "Gramíneas" junta pasto e campo nativo. A '
           'classificação não separa vegetação nativa de plantada e não mede desmatamento; o histórico e as '
           'datas-marco estão nas páginas do mapeamento anual, e a supressão, na do PRODES.')
    f.nota(f'Fonte: {cb["fonte"]}.')
    return f


def pagina_prodes(doc, pr):
    f = Folha(doc)
    f.secao('Supressão de vegetação nativa — PRODES e DETER (INPE)')
    bioma = f' Bioma: {pr["biomas"]}.' if pr.get('biomas') else ''
    f.texto('Pelos dados públicos do INPE: polígonos de supressão do PRODES, por ano, de 2008 em diante, '
            f'recortados no perímetro, e alertas do DETER.{bioma} O ano do PRODES é o da temporada de imagens, '
            'não o dia da supressão.')
    rotulos = (('depois_2019', 'Depois de 31/07/2019 (PRODES 2020 em diante)'),
               ('ano_2019', 'PRODES 2019 (imagens de antes e de depois de 31/07/2019)'),
               ('de_2008_a_2018', 'PRODES de 2008 a 2018'))
    linhas = []
    for chave, rotulo in rotulos:
        x = pr['faixas'].get(chave)
        if x:
            linhas.append([rotulo, str(x['n']), br(x['ha']), f"{x['n_acima']} · {br(x['ha_acima'])} ha",
                           f"{x['n_abaixo']} · {br(x['ha_abaixo'])} ha"])
    f.tabela([('Período', ESQ, 'left'), ('Polígonos', 0.56, 'right'), ('ha no perímetro', 0.675, 'right'),
              ('Acima do mín.', 0.80, 'right'), ('Abaixo do mín.', DIR, 'right')], linhas, tam=8.2)
    f.nota('"Mínimo" é o da nota do MMA usada no crédito rural, medido no polígono inteiro: mais de 6,25 ha na '
           'Amazônia; mais de 5 ha no Cerrado e no Pantanal; mais de 2 ha na Mata Atlântica, na Caatinga e no '
           'Pampa.')
    if pr.get('poligonos'):
        f.texto('Polígonos (mais recentes primeiro)', negrito=True)
        f.tabela([('Ano', ESQ, 'left'), ('Imagem', 0.23, 'left'), ('ha no perímetro', 0.50, 'right'),
                  ('ha do polígono', 0.66, 'right'), ('Frente ao mínimo', DIR, 'right')],
                 [[str(p['ano']), p['imagem'] or '—', br(p['ha_na_area']), br(p['ha_do_poligono']),
                   ('abaixo' if p['abaixo_do_minimo'] else 'acima') + f" de {br(p['minimo_ha'], 2)} ha"]
                  for p in pr['poligonos'][:20]], tam=8.2)
        if pr.get('poligonos_fora_da_lista'):
            f.nota(f"Há mais {pr['poligonos_fora_da_lista']} polígono(s) além dos listados.")
    else:
        f.texto('Nenhum polígono do PRODES de 2008 em diante toca o perímetro.')
    deter = pr.get('deter')
    if deter:
        f.secao('Alertas do DETER')
        if deter['n']:
            f.texto(f"Desde {deter['desde']}: {deter['n']} alerta(s), {br(deter['ha'])} ha no perímetro. Depois da "
                    f"última imagem do PRODES: {deter['n_depois']} alerta(s), {br(deter['ha_depois'])} ha. Os "
                    'alertas são avisos rápidos, não consolidados; os anteriores à última imagem podem já '
                    'estar no PRODES.')
            if deter['alertas']:
                f.tabela([('Data', ESQ, 'left'), ('Classe', 0.23, 'left'), ('ha no perímetro', 0.72, 'right'),
                          ('Depois do PRODES', DIR, 'right')],
                         [[a['data'], a['classe'], br(a['ha']), 'sim' if a['depois_do_prodes'] else 'não']
                          for a in deter['alertas']], tam=8.2)
        else:
            f.texto(f"Desde {deter['desde']}: nenhum alerta no perímetro. O DETER cobre a Amazônia, o Cerrado e "
                    'o Pantanal.')
    if pr.get('ate_onde'):
        f.secao('Até onde vai o dado')
        f.texto(pr['ate_onde'] + '.', tam=8.5)
    if pr.get('ano_civil'):
        f.nota('Na Mata Atlântica, na Caatinga e no Pampa as imagens do PRODES se espalham pelo ano civil: o ano '
               'do polígono não coincide com o corte de 31/07.')
    if pr.get('arquivos_faltando'):
        f.nota(f"Os dados de {pr['arquivos_faltando']} arquivo(s) do INPE não estavam carregados nesta consulta.")
    f.nota(f"Fonte: {pr['fonte']}" + (f", licença {pr['licenca']}." if pr.get('licenca') else '.'))
    return f


def linhas_da_comparacao(car, uso):
    """Pares 'declarado no CAR' × 'observado no mapeamento', com a diferença."""
    def soma(grupo):
        itens = [t['area_ha'] for t in car.get('temas', []) if t.get('grupo') == grupo and 'area_ha' in t]
        return sum(itens) if itens else None

    linhas = []
    area_car = car.get('area_declarada_ha')
    if area_car and uso.get('area_ha'):
        linhas.append(('Área do imóvel', 'declarada no CAR', area_car, 'perímetro analisado', uso['area_ha']))
    nativa = soma('vegetacao_nativa')
    if nativa is not None and uso.get('hoje'):
        linhas.append(('Vegetação nativa', 'remanescente declarado no CAR', nativa,
                       f'mapeamento de {uso["hoje"]["ano"]}', uso['hoje']['nativa_ha']))
    consolidada = soma('area_consolidada')
    existia = next((ha for n, ha in uso.get('situacao', []) if 'já existia em 2008' in n), None)
    if consolidada is not None and existia is not None:
        linhas.append(('Uso anterior a 2008', 'área consolidada declarada no CAR', consolidada,
                       'uso que já existia no mapa de 2008', existia))
    return linhas


def pagina_comparacao(doc, car, uso):
    linhas = linhas_da_comparacao(car, uso)
    f = Folha(doc)
    f.secao('Declarado no CAR e observado no mapeamento')
    f.texto('Os dois lados medem coisas parecidas com definições diferentes. O CAR é a declaração do '
            'proprietário, desenhada sobre imagem; o mapeamento classifica pixels de 30 m, ano a ano. A '
            'diferença abaixo é só a subtração dos dois números.')
    for tema, rot_a, a, rot_b, b in linhas:
        f.texto(tema, negrito=True)
        f.tabela([('', ESQ, 'left'), ('ha', DIR, 'right')],
                 [[rot_a[0].upper() + rot_a[1:], br(a, 2)], [rot_b[0].upper() + rot_b[1:], br(b, 1)],
                  ['Diferença (segundo menos o primeiro)', br(b - a, 1)]], negrito_ultima=True)
    reserva = [t for t in car.get('temas', []) if t.get('grupo') == 'reserva_legal' and 'area_ha' in t]
    if reserva:
        total = car.get('area_declarada_ha') or 0
        f.texto('Reserva legal declarada', negrito=True)
        f.tabela([('Situação', ESQ, 'left'), ('ha', 0.78, 'right'), ('% do imóvel', DIR, 'right')],
                 [[t['rotulo'], br(t['area_ha'], 2), br(100 * t['area_ha'] / total, 1) if total else '—']
                  for t in reserva])
        f.nota('Percentual sobre a área declarada do imóvel. O mapeamento por satélite não distingue reserva '
               'legal de outra vegetação nativa.')
    f.nota(f"Fontes: SICAR (consulta de {_data_br(car.get('consultado_em'))}) e {uso['fonte']}.")
    return f


def pagina_relevo(doc, rv):
    f = Folha(doc)
    f.secao('Relevo')
    f.texto(f'Pelo modelo de terreno de 30 m ({rv["fonte"]}), que representa o chão, sem a vegetação.')
    alt, dec = rv.get('altitude'), rv.get('declive')
    f.pares([
        ('Altitude', f"de {br(alt['min'], 0)} a {br(alt['max'], 0)} m (média {br(alt['media'], 0)} m)" if alt else None),
        ('Desnível', f"{br(alt['desnivel'], 0)} m" if alt else None),
        ('Declive médio', f"{br(dec['medio'])} %" if dec else None),
        ('Declive máximo', f"{br(dec['maximo'])} %" if dec else None),
        (f"{dec['percentil']} % da área abaixo de" if dec else '', f"{br(dec['abaixo_de'])} % de declive" if dec else None),
        ('Encosta acima de 45°', rv.get('encosta_45')),
    ])
    if rv.get('classes'):
        f.secao('Classes de relevo (Embrapa)')
        tons = ['#ffffcc', '#d9f0a3', '#addd8e', '#f4a582', '#d6604d', '#7f0000']
        ax = f.eixo(0.024 * len(rv['classes']) + 0.012, esq=ESQ + 0.24)
        barras_horizontais(ax, [(f'{n} ({faixa})', ha, pct, tons[min(i, 5)])
                                for i, (n, faixa, pct, ha) in enumerate(rv['classes'])])
    if rv.get('mecanizacao'):
        f.secao('Faixas de declive usuais para mecanização')
        f.tabela([('Faixa', ESQ, 'left'), ('% da área', DIR, 'right')],
                 [[f'{n[0].upper() + n[1:]} ({faixa})', br(p)] for n, faixa, p in rv['mecanizacao']])
        f.nota('Faixas de referência técnica usual, não regra: o limite real depende da máquina e da operação.')
    f.nota('O modelo de 30 m mostra a forma geral do relevo. Não vê terraço, curva de nível nem obra recente e '
           'não substitui levantamento topográfico.')
    return f


def _corta(texto, n):
    texto = str(texto if texto not in (None, '') else '—')
    return texto if len(texto) <= n else texto[:n - 1].rstrip() + '…'


def paginas_restricoes(doc, rs):
    """Unidades de conservação, terras indígenas e termos de embargo: o que sobrepõe o perímetro e o
    que fica perto, por base pública. Devolve uma lista de folhas (a lista de itens pode pedir outra)."""
    folhas = []

    def nova(titulo):
        f = Folha(doc)
        f.secao(titulo)
        folhas.append(f)
        return f

    def cabe(f, altura, titulo):
        return f if f.sobra() >= altura else nova(titulo)

    uc, ti, em = rs['uc'], rs['ti'], rs['embargo']
    f = nova('Restrições: unidades de conservação, terras indígenas e embargos')
    f.texto('O que o perímetro sobrepõe e o que fica perto dele em três bases públicas: unidades de conservação '
            '(Cadastro Nacional de Unidades de Conservação, do Ministério do Meio Ambiente), terras indígenas (FUNAI) e '
            'termos de embargo (IBAMA e ICMBio). Os termos de embargo aparecem pelo número, sem nome e sem documento de '
            'pessoa; o número permite a consulta no órgão.')

    def linha(nome, g):
        if not g['lida']:
            return [nome, 'base não lida', '—', '—', '—', '—']
        return [nome, _corta(g['data'], 40), str(g['n']), br(g['ha']), br(g['pct']), str(g['n_perto'])]

    f.tabela([('Base pública', ESQ, 'left'), ('Data da base', 0.37, 'left'), ('Itens', 0.74, 'right'), ('ha', 0.81, 'right'),
              ('%', 0.86, 'right'), ('Perto', DIR, 'right')],
             [linha('Unidades de conservação (CNUC, MMA)', uc), linha('Terras indígenas (FUNAI)', ti),
              linha('Termos de embargo (IBAMA e ICMBio)', em)], tam=8.2)
    f.nota('Itens = quantas unidades, terras ou termos tocam o perímetro; ha e % = a parte do perímetro coberta (o que '
           'se sobrepõe dentro da mesma base é contado uma vez). Perto = até 10 km da divisa para unidade de conservação '
           'e terra indígena e até 1 km para termo de embargo.'
           + (f' Termos de embargo que tocam o perímetro: {em["n_contorno"]} com contorno e {em["n_ponto"]} marcado(s) '
              'por ponto.' if em['lida'] and em['n'] else ''))

    def lista(titulo, itens, nome_de, detalhe_de):
        nonlocal f
        if not itens:
            return
        f = cabe(f, 0.12, 'Restrições (continuação)')
        f.secao(titulo)
        for item in itens:
            f = cabe(f, 0.075, 'Restrições (continuação)')
            f.texto(_corta(nome_de(item), 95), tam=8.8, negrito=True)
            f.texto(detalhe_de(item), tam=8.3, cor=T['fg2'], recuo=0.012)

    lista('Unidades de conservação que sobrepõem o perímetro', uc['itens'], lambda u: u['nome'],
          lambda u: ' · '.join(p for p in (
              u['categoria'], u['grupo'], f'esfera {u["esfera"]}', f'criada em {u["criada_em"]}' if u['criada_em'] else '',
              f'plano de manejo: {u["plano_manejo"]}', f'{br(u["ha"])} ha no perímetro ({br(u["pct"])} %)',
              f'a unidade inteira tem {br(u["ha_total"], 0)} ha' if u['ha_total'] else '') if p))
    lista('Terras indígenas que sobrepõem o perímetro', ti['itens'], lambda t: t['nome'],
          lambda t: ' · '.join(p for p in (
              f'etnia {t["etnia"]}' if t['etnia'] else '', f'fase na FUNAI: {t["fase"]}', t['modalidade'] or '',
              f'{br(t["ha"])} ha no perímetro ({br(t["pct"])} %)',
              f'a terra inteira tem {br(t["ha_total"], 0)} ha' if t['ha_total'] else '') if p))
    lista('Termos de embargo que tocam o perímetro', em['itens'],
          lambda e: f'{e["orgao"]} · termo {e["termo"]}' + (f' · {e["data"]}' if e['data'] else ''),
          lambda e: ' · '.join(p for p in (
              f'tipo na base: {e["tipo"]}',
              f'contorno com {br(e["ha_na_area"])} ha no perímetro ({br(e["pct"])} %)' if e['origem'] == 'contorno'
              else 'marcado por ponto (o órgão registrou a coordenada, não o contorno)',
              f'área declarada no termo: {br(e["ha_no_termo"])} ha' if e['ha_no_termo'] else '', e['local'] or '') if p))

    perto = ([['Unidade de conservação', f'{u["nome"]} ({u["categoria"]})', br(u['km'], 2)] for u in uc['perto']]
             + [['Terra indígena', f'{t["nome"]} (fase: {t["fase"]})', br(t['km'], 2)] for t in ti['perto']]
             + [['Termo de embargo', f'{e["orgao"]} {e["termo"]}' + (' (ponto)' if e['origem'] == 'ponto' else ''),
                 br(e['distancia_km'], 2) if e['distancia_km'] is not None else '—'] for e in em['perto']])
    if perto:
        f = cabe(f, 0.07 + 0.0165 * len(perto), 'Restrições (continuação)')
        f.secao('O que fica perto do perímetro')
        f.tabela([('Tipo', ESQ, 'left'), ('Nome ou número', 0.28, 'left'), ('Distância (km)', DIR, 'right')],
                 [[tipo, _corta(nome, 72), km] for tipo, nome, km in perto], tam=8.2)
        listados = {'uc': (uc['n_perto'], len(uc['perto'])), 'ti': (ti['n_perto'], len(ti['perto'])),
                    'em': (em['n_perto'], len(em['perto']))}
        faltam = sum(max(0, total - mostrados) for total, mostrados in listados.values())
        if faltam:
            f.nota(f'Há mais {faltam} item(ns) perto do perímetro além dos listados.')

    f = cabe(f, 0.13, 'Restrições (continuação)')
    if em['lida'] and em['sem_localizacao']:
        f.nota(f'A base do IBAMA traz {br(em["sem_localizacao"], 0)} termo(s) sem localização, que não entram neste '
               'cruzamento.')
    nao_lidas = ([nome for nome, g in (('unidades de conservação', uc), ('terras indígenas', ti), ('embargos', em))
                  if not g['lida']] + ([f'embargos do {em["base_que_faltou"]}'] if em.get('base_que_faltou') else []))
    if nao_lidas:
        f.nota('Base(s) não lida(s) nesta consulta: ' + ', '.join(nao_lidas) + '. O documento não informa nada sobre '
               'ela(s).')
    f.nota('Esta seção é a leitura das bases públicas na data de cada uma; não equivale a certidão e não substitui a '
           'consulta ao órgão.' + (f' Ficam de fora: {rs["nao_cobre"]}.' if rs.get('nao_cobre') else ''))
    f.nota(f'Fonte: {rs["fonte"]} — bases públicas.')
    return folhas


def pagina_solo(doc, so):
    f = Folha(doc)
    f.secao('Solo: textura e carbono (estimativa)')
    f.texto('Estimativas do SoilGrids 2.0, mapa mundial de solos do ISRIC feito por modelo, com pixel de 250 m. São '
            'valores modelados, não medições no local. O ISRIC informa que o mapa não foi feito para a escala de '
            'fazenda, e os valores tendem ao meio da faixa: solo muito arenoso ou muito argiloso costuma aparecer como '
            'textura média.')
    s, sub, est = so.get('superficie'), so.get('subsolo'), so.get('estoque')
    f.pares([
        ('Argila de 0–30 cm', f"{br(s['argila'])} %" if s else None),
        ('Areia de 0–30 cm', f"{br(s['areia'])} %" if s else None),
        ('Silte de 0–30 cm', f"{br(s['silte'])} %" if s else None),
        ('Textura de 0–30 cm', f"{s['textura']} (grupamento textural da Embrapa)" if s else None),
        ('Carbono de 0–30 cm', f"{br(s['carbono_g_kg'])} g/kg · {br(s['materia_organica'])} % de matéria orgânica "
                               '(carbono × 1,724)' if s else None),
        ('Argila de 30–100 cm', f"{br(sub['argila'])} % · textura {sub['textura']}" if sub else None),
        ('Estoque de carbono, 0–30 cm', f"{br(est['t_ha'])} t/ha · {br(est['total_t'], 0)} t nos "
                                        f"{br(est['area_com_dado_ha'])} ha com dado" if est else None),
        ('Pixels de 250 m', str(so['pixels']) if so.get('pixels') is not None else None),
    ], x_valor=0.36)
    if so.get('camadas'):
        f.secao('Por profundidade (média do perímetro)')
        f.tabela([('Camada', ESQ, 'left'), ('Textura', 0.21, 'left'), ('Argila %', 0.50, 'right'), ('Areia %', 0.60, 'right'),
                  ('Silte %', 0.70, 'right'), ('C g/kg', 0.81, 'right'), ('M.O. %', DIR, 'right')],
                 [[c['camada'], c['textura'], br(c['argila']), br(c['areia']), br(c['silte']), br(c['carbono_g_kg']),
                   br(c['materia_organica'])] for c in so['camadas']])
        f.nota('C = carbono orgânico; M.O. = matéria orgânica (carbono × 1,724, conversão convencional).')
    v = so.get('variacao')
    if v:
        f.nota(f'Dentro do perímetro, a argila de 0–30 cm vai de {br(v["argila"][0])} % a {br(v["argila"][1])} % e o '
               f'estoque de carbono, de {br(v["estoque"][0])} a {br(v["estoque"][1])} t/ha (valores dos pixels de 250 m).')
    fx = so.get('faixa_do_modelo')
    if fx and (fx.get('argila') or fx.get('estoque')):
        partes = ([f'argila de 0–30 cm entre {br(fx["argila"][0])} % e {br(fx["argila"][1])} %'] if fx.get('argila') else []) + \
                 ([f'estoque entre {br(fx["estoque"][0])} e {br(fx["estoque"][1])} t/ha'] if fx.get('estoque') else [])
        f.nota('Faixa de 90 % informada pelo próprio modelo, em cada pixel: ' + '; '.join(partes) + '.')
    if so.get('poucos_pixels'):
        f.nota('O perímetro tem menos de 4 pixels deste mapa: os valores são, na prática, os de um ou dois pixels de '
               '250 m.')
    if so.get('cobertura_pct') is not None:
        f.nota(f'O mapa tem dado em {br(so["cobertura_pct"])} % do perímetro; água e área urbana ficam sem valor.')
    f.nota('Esta seção traz estimativas de um mapa mundial de 250 m; não substitui análise de solo. O estoque de '
           'carbono é a estimativa do mapa para 0–30 cm e não equivale a crédito de carbono.')
    f.nota(f'Fonte: {so["fonte"]}, licença {so["licenca"]}; versão 2.0, pixel de 250 m.')
    return f


def pagina_figura(doc, legenda, caminho, fonte):
    f = Folha(doc)
    f.secao(legenda)
    try:
        imagem = plt.imread(str(caminho))
    except Exception as e:  # noqa: BLE001 - figura ilegível não derruba o dossiê
        f.texto(f'A imagem não pôde ser lida ({type(e).__name__}).')
        return f, False
    if imagem.ndim == 3 and imagem.shape[2] > 4:
        imagem = imagem[:, :, :3]
    if imagem.dtype.kind == 'f' and np.nanmax(imagem) > 1:
        imagem = np.clip(imagem / np.nanmax(imagem), 0, 1)
    if imagem.dtype == np.uint16:
        imagem = (imagem / 256).astype(np.uint8)
    altura = min(0.74, f.sobra() - 0.06, (DIR - ESQ) * A4[0] / A4[1] * imagem.shape[0] / imagem.shape[1])
    ax = f.eixo(altura)
    ax.imshow(imagem)
    ax.set_anchor('N')
    ax.axis('off')
    if fonte:
        f.nota(f'Fonte: {fonte}.')
    return f, True


def pagina_fontes(doc, fontes, avisos):
    f = Folha(doc)
    f.secao('Fontes e datas')
    for titulo, detalhe in fontes:
        f.texto(titulo, negrito=True)
        f.texto(detalhe, tam=8.7, recuo=0.012)
    f.secao('Limites deste documento')
    for linha in (
        'Os dados foram reunidos como as fontes os entregam, para o perímetro informado, na data indicada. '
        'Fontes públicas mudam: uma nova consulta pode trazer números diferentes.',
        'Mapeamentos por satélite de 30 m têm erro de classificação. Áreas pequenas e bordas são as mais '
        'sujeitas a erro. Nada aqui substitui a vistoria.',
        'O CAR é autodeclaratório. Constar no cadastro não equivale a análise ou aprovação pelo órgão ambiental.',
        'O dossiê não avalia conformidade ambiental, fundiária ou de crédito e não recomenda conduta. A '
        'conclusão é do responsável técnico.',
    ):
        f.texto('• ' + linha, tam=8.7)
    if avisos:
        f.secao('Observações da montagem')
        for a in avisos:
            f.texto('• ' + a, tam=8.5, cor=T['fg3'])
    return f


def _data_br(iso):
    if not iso:
        return None
    partes = str(iso)[:10].split('-')
    return '/'.join(reversed(partes)) if len(partes) == 3 else str(iso)


if __name__ == '__main__':
    import os
    import tempfile

    assert br(1669.5) == '1.669,5' and br(0.3, 2) == '0,30' and br(None) == '—' and br(40, 0) == '40'
    assert br(-0.01) == '0,0' and br(-37.5) == '−37,5'
    assert cor_da_classe('Formação Florestal') == '#1f8d49' and cor_da_classe('Soja') == '#e974ed'
    assert cor_da_classe('Árvores') == '#1f8d49' and cor_da_classe('Gramíneas (pasto e campo)') == '#edde8e'
    assert cor_da_classe('Solo exposto') == '#c26a3d' and cor_da_classe('Lavoura') == '#e974ed'
    assert _data_br('2026-11-12') == '12/11/2026'
    doc = {'nome': 'Fazenda Exemplo', 'data': '12/11/2026'}
    assert usar_tema('escuro')['num'] and T['pagina'] == '#0B100B' and T['verde'] == '#52C937'
    assert usar_tema('papel')['corpo'] and T['pagina'] == '#FBFCF9' and T['verde'] == '#2E8B1E'
    assert espacado('ab') == 'A\u2009B'
    quadrado = [[(0, 0), (1000, 0), (1000, 800), (0, 800)]]
    uso = {'area_ha': 80, 'fonte': 'MapBiomas Coleção 11', 'ano_inicial': 1985, 'ano_final': 2025,
           'hoje': {'ano': 2025, 'classes': [('Pastagem', 50, 62), ('Formação Florestal', 30, 38)],
                    'nativa_ha': 30, 'nativa_pct': 38},
           'marcos': [{'ano': 2008, 'rotulo': 'Código Florestal', 'nativa_ha': 33, 'nativa_pct': 41,
                       'classes': [('Pastagem', 47, 59), ('Formação Florestal', 33, 41)]}],
           'situacao': [('Vegetação nativa', 30), ('Uso que já existia em 2008', 47), ('Aberto depois de 2020', 3)],
           'aberto_desde': {2008: 3, 2019: 3, 2020: 3}, 'abertura_por_ano': [(2005, 4), (2022, 3)]}
    car = {'car': 'SP-0000000-X', 'area_declarada_ha': 80.2, 'consultado_em': '2026-11-12',
           'temas': [{'rotulo': 'Remanescente de vegetação nativa', 'grupo': 'vegetacao_nativa', 'feicoes': 2, 'area_ha': 28.0},
                     {'rotulo': 'Área consolidada', 'grupo': 'area_consolidada', 'feicoes': 1, 'area_ha': 50.0},
                     {'rotulo': 'Reserva legal proposta', 'grupo': 'reserva_legal', 'feicoes': 1, 'area_ha': 16.0}]}
    comparacao = linhas_da_comparacao(car, uso)
    assert [c[0] for c in comparacao] == ['Área do imóvel', 'Vegetação nativa', 'Uso anterior a 2008']
    assert comparacao[1][2] == 28.0 and comparacao[1][4] == 30 and comparacao[2][4] == 47
    folhas = [pagina_identificacao(doc, {'uso': uso, 'car': car}, quadrado, 'SIRGAS 2000 / UTM 22S.'),
              pagina_car(doc, car, quadrado, [('vegetacao_nativa', [[[(100, 100), (400, 100), (400, 500), (100, 500)]]])]),
              pagina_uso(doc, uso), pagina_marcos(doc, uso), pagina_comparacao(doc, car, uso),
              pagina_cobertura(doc, {'fonte': 'Dynamic World V1', 'periodo': ('13/11/2025', '12/11/2026'),
                                     'dias_com_imagem': 88, 'ultima_imagem': '09/11/2026', 'probabilidade_media': 55,
                                     'classes': [{'nome': 'Árvores', 'ha': 48, 'pct': 60, 'probabilidade': 68,
                                                  'segunda': 'Lavoura', 'segunda_pct': 5}],
                                     'faixas': [('50 % ou mais', 48.0, 60.0)]}),
              pagina_fontes(doc, [('Uso do solo', 'MapBiomas Coleção 11.')], ['observação de teste'])]
    with tempfile.TemporaryDirectory() as pasta:
        arq = os.path.join(pasta, 'p.png')
        folhas[0].fechar(1, len(folhas)).savefig(arq, dpi=60)
        assert os.path.getsize(arq) > 15000
    for folha in folhas:
        plt.close(folha.fig)
    print(f'paginas OK: {len(folhas)} páginas montadas; comparação declarado × observado conferida')
