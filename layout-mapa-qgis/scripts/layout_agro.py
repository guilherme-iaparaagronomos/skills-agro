"""layout_agro — layout de mapa agronômico no QGIS, num modelo só.

Roda DENTRO do QGIS (PyQGIS 3.28 ou mais novo). A IA grava este arquivo numa
pasta ao lado do projeto do usuário, importa e chama:

    import layout_agro as la
    la.classificar_raster(camada, [150, 350, 600])            # se a camada ainda não está em classes
    la.montar_layout('Argila 0-20', camada, titulo='Mapa de Fertilidade do Solo',
                     fazenda='Fazenda Exemplo', proprietario='Fulano de Tal',
                     campos=[('Safra', '25/26'), ('Atributo', 'Argila'), ('Profundidade', '0-20 cm')],
                     perimetro=talhoes, unidade='g/kg')
    la.exportar('Argila 0-20', 'C:/saida/argila.pdf')

Uma página por talhão: os mesmos argumentos mais atlas_camada=talhoes e
atlas_campo='nome_do_campo'.

O modelo: moldura; faixa de cima com a logo (se houver) e os campos Fazenda e
Proprietário; coluna da direita com o título, os dados do mapa, a legenda com
"faixa | ha (%)" por classe, a escala, o norte, a data e mínimo, máximo e
média. O mapa ocupa o resto da página.
"""

import datetime
import math

try:
    from qgis.core import (
        QgsBasicNumericFormat, QgsCategorizedSymbolRenderer, QgsColorRampShader, QgsCoordinateReferenceSystem,
        QgsCoordinateTransform, QgsDistanceArea, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsLayoutExporter,
        QgsLayoutItemLabel, QgsLayoutItemMap, QgsLayoutItemMapGrid, QgsLayoutItemPicture,
        QgsLayoutItemScaleBar, QgsLayoutItemShape, QgsLayoutObject, QgsLayoutPoint, QgsLayoutSize,
        QgsMapLayerStyle, QgsPalettedRasterRenderer, QgsPrintLayout, QgsProject, QgsProperty, QgsRasterLayer,
        QgsRasterShader, QgsRuleBasedRenderer, QgsScaleBarSettings, QgsSingleBandPseudoColorRenderer, QgsSingleSymbolRenderer, QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor, QFont
    DENTRO_DO_QGIS = True
except ImportError:  # fora do QGIS só as funções de texto e o teste embutido funcionam
    DENTRO_DO_QGIS = False

MM = QgsUnitTypes.LayoutMillimeters if DENTRO_DO_QGIS else None
PAGINAS = {'A4': (297.0, 210.0), 'A3': (420.0, 297.0)}
FONTE = 'Arial'
# vermelho → amarelo → verde, para classes em que mais é melhor
PALETA = ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']


def br(valor, casas=2):
    """1669.5 → '1.669,50'"""
    texto = f'{float(valor):,.{casas}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def cores_para(n, invertida=False):
    """n cores espalhadas pela paleta (invertida: mais é pior, como alumínio)."""
    if n <= 1:
        return [PALETA[-1]]
    cores = [PALETA[round(i * (len(PALETA) - 1) / (n - 1))] for i in range(n)]
    return cores[::-1] if invertida else cores


# --------------------------------------------------------------------- classes
def classificar_raster(camada, limites, cores=None, rotulos=None, invertida=False, casas=None):
    """Põe o raster em CLASSES (cor discreta). `limites` são os tetos de cada classe,
    menos o da última: [150, 350, 600] dá ≤150, 150–350, 350–600 e >600."""
    limites = sorted(float(v) for v in limites)
    n = len(limites) + 1
    cores = cores or cores_para(n, invertida)
    if casas is None:
        casas = 0 if all(float(v).is_integer() for v in limites) else 2
    if not rotulos:
        rotulos = ([f'≤ {br(limites[0], casas)}'] + [f'{br(a, casas)} - {br(b, casas)}' for a, b in zip(limites, limites[1:])]
                   + [f'> {br(limites[-1], casas)}'])
    itens = [QgsColorRampShader.ColorRampItem(teto, QColor(cor), rotulo)
             for teto, cor, rotulo in zip(limites + [float('inf')], cores, rotulos)]
    funcao = QgsColorRampShader()
    funcao.setColorRampType(QgsColorRampShader.Discrete)
    funcao.setColorRampItemList(itens)
    sombreador = QgsRasterShader()
    sombreador.setRasterShaderFunction(funcao)
    camada.setRenderer(QgsSingleBandPseudoColorRenderer(camada.dataProvider(), 1, sombreador))
    camada.triggerRepaint()
    return rotulos


def _matriz(camada, teto=30_000_000):
    """Valores do raster como matriz, área de cada pixel em m² e o valor sem dado."""
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(camada.source())
    if ds is None:
        raise ValueError(f'não consegui abrir o raster {camada.name()} para contar os pixels')
    banda = ds.GetRasterBand(1)
    nx, ny = ds.RasterXSize, ds.RasterYSize
    passo = max(1, math.ceil(math.sqrt(nx * ny / teto)))  # raster enorme: lê reduzido
    dados = banda.ReadAsArray(buf_xsize=nx // passo, buf_ysize=ny // passo).astype('float64')
    gt = ds.GetGeoTransform()
    dx, dy = abs(gt[1]) * passo, abs(gt[5]) * passo
    if camada.crs().isGeographic():  # graus → metros na latitude do centro
        lat = math.radians(gt[3] + gt[5] * ny / 2)
        dx, dy = dx * 111320.0 * math.cos(lat), dy * 110574.0
    vazio = banda.GetNoDataValue()
    valido = np.isfinite(dados)
    if vazio is not None:
        valido &= dados != vazio
    return dados, valido, dx * dy


def areas_por_classe(camada):
    """Classes do estilo da camada com a área de cada uma.
    Devolve ([{'rotulo', 'cor', 'ha', 'pct'}], estatísticas {'min', 'max', 'media'} ou None)."""
    import numpy as np

    classes, estat = [], None
    if isinstance(camada, QgsRasterLayer):
        dados, valido, m2 = _matriz(camada)
        valores = dados[valido]
        if valores.size:
            estat = {'min': float(valores.min()), 'max': float(valores.max()), 'media': float(valores.mean())}
        estilo = camada.renderer()
        if isinstance(estilo, QgsSingleBandPseudoColorRenderer) and estilo.shader():
            funcao = estilo.shader().rasterShaderFunction()
            itens = sorted(funcao.colorRampItemList(), key=lambda i: i.value)
            if funcao.colorRampType() != QgsColorRampShader.Discrete:
                raise ValueError('o raster está em cor contínua: classifique antes com classificar_raster()')
            tetos = [i.value for i in itens[:-1]]
            indice = np.digitize(valores, tetos, right=True)
            for n, item in enumerate(itens):
                classes.append({'rotulo': item.label or str(item.value), 'cor': item.color.name(),
                                'ha': float((indice == n).sum()) * m2 / 10000})
        elif isinstance(estilo, QgsPalettedRasterRenderer):
            for c in estilo.classes():
                classes.append({'rotulo': c.label or str(c.value), 'cor': c.color.name(),
                                'ha': float((valores == c.value).sum()) * m2 / 10000})
        else:
            raise ValueError('estilo de raster sem classes: classifique antes com classificar_raster()')
    elif isinstance(camada, QgsVectorLayer):
        medidor = QgsDistanceArea()
        medidor.setSourceCrs(camada.crs(), QgsProject.instance().transformContext())
        medidor.setEllipsoid(QgsProject.instance().ellipsoid() or 'GRS80')
        estilo = camada.renderer()
        if isinstance(estilo, QgsCategorizedSymbolRenderer):
            campo, grupos = estilo.classAttribute(), estilo.categories()
            soma = {str(g.value()): 0.0 for g in grupos}
            for f in camada.getFeatures():
                chave = str(f[campo])
                if chave in soma:
                    soma[chave] += medidor.measureArea(f.geometry())
            classes = [{'rotulo': g.label() or str(g.value()), 'cor': g.symbol().color().name(),
                        'ha': soma[str(g.value())] / 10000} for g in grupos]
        elif isinstance(estilo, QgsGraduatedSymbolRenderer):
            campo, faixas = estilo.classAttribute(), estilo.ranges()
            soma, vistos = [0.0] * len(faixas), []
            for f in camada.getFeatures():
                try:
                    v = float(f[campo])
                except (TypeError, ValueError):
                    continue
                vistos.append(v)
                for n, faixa in enumerate(faixas):
                    if faixa.lowerValue() <= v <= faixa.upperValue():
                        soma[n] += medidor.measureArea(f.geometry())
                        break
            classes = [{'rotulo': fx.label(), 'cor': fx.symbol().color().name(), 'ha': s / 10000}
                       for fx, s in zip(faixas, soma)]
            if vistos:
                estat = {'min': min(vistos), 'max': max(vistos), 'media': sum(vistos) / len(vistos)}
        else:
            raise ValueError('a camada vetorial precisa de estilo categorizado ou graduado para ter legenda de classes')
    total = sum(c['ha'] for c in classes) or 1.0
    for c in classes:
        c['pct'] = 100 * c['ha'] / total
    return classes, estat


# ----------------------------------------------------------------- peças do layout
def _ponto(x, y):
    return QgsLayoutPoint(x, y, MM)


def _tamanho(w, h):
    return QgsLayoutSize(w, h, MM)


def _caixa(layout, x, y, w, h, cor='255,255,255,255', traco=0.3, contorno='0,0,0,255'):
    forma = QgsLayoutItemShape(layout)
    forma.setShapeType(QgsLayoutItemShape.Rectangle)
    forma.setSymbol(QgsFillSymbol.createSimple({'color': cor, 'outline_color': contorno,
                                                 'outline_width': str(traco), 'outline_style': 'solid'}))
    layout.addLayoutItem(forma)
    forma.attemptMove(_ponto(x, y))
    forma.attemptResize(_tamanho(w, h))
    return forma


def _texto(layout, texto, x, y, w, h, tam=9, negrito=False, alinh='esq', cor='#000000'):
    item = QgsLayoutItemLabel(layout)
    item.setText(str(texto))
    fonte = QFont(FONTE)
    fonte.setPointSizeF(tam)
    fonte.setBold(negrito)
    try:  # QGIS 3.30+
        formato = item.textFormat()
        formato.setFont(fonte)
        formato.setSize(tam)
        formato.setColor(QColor(cor))
        item.setTextFormat(formato)
    except AttributeError:
        item.setFont(fonte)
        item.setFontColor(QColor(cor))
    item.setHAlign({'esq': Qt.AlignLeft, 'centro': Qt.AlignHCenter, 'dir': Qt.AlignRight}[alinh])
    item.setVAlign(Qt.AlignVCenter)
    layout.addLayoutItem(item)
    item.attemptMove(_ponto(x, y))
    item.attemptResize(_tamanho(w, h))
    return item


def _crs_em_metros(camada):
    """CRS do mapa: o da camada se já for em metros; senão, a zona UTM SIRGAS 2000 do centro."""
    crs = camada.crs()
    if not crs.isGeographic():
        return crs
    centro = camada.extent().center()
    zona = int(math.floor((centro.x() + 180) / 6) + 1)
    return QgsCoordinateReferenceSystem(f'EPSG:{(31960 if centro.y() < 0 else 31954) + zona}')


def _linha(cor, largura):
    return QgsFillSymbol.createSimple({'color': '0,0,0,0', 'style': 'no', 'outline_color': cor,
                                       'outline_width': str(largura), 'outline_style': 'solid'})


def _so_contorno(camada, espessura=0.3, destaque=False):
    """Estilo "só o contorno, sem preenchimento" para desenhar os talhões por cima do mapa.
    É montado numa CÓPIA: a camada do usuário não é tocada. Com destaque (atlas), o talhão da
    página sai com o contorno grosso e os vizinhos com o contorno fino e cinza."""
    copia = camada.clone()
    if destaque:
        raiz = QgsRuleBasedRenderer.Rule(None)
        da_pagina = QgsRuleBasedRenderer.Rule(_linha('0,0,0,255', espessura * 2.6))
        da_pagina.setFilterExpression('@atlas_featureid = $id')
        vizinhos = QgsRuleBasedRenderer.Rule(_linha('120,120,120,255', espessura * 0.8))
        vizinhos.setIsElse(True)
        raiz.appendChild(da_pagina)
        raiz.appendChild(vizinhos)
        copia.setRenderer(QgsRuleBasedRenderer(raiz))
    else:
        copia.setRenderer(QgsSingleSymbolRenderer(_linha('0,0,0,255', espessura)))
    estilo = QgsMapLayerStyle()
    estilo.readFromLayer(copia)
    return estilo.xmlData()


def _passo_redondo(valor):
    base = 10 ** math.floor(math.log10(valor))
    return next((base * m for m in (5, 2, 1) if base * m <= valor), base)


PASSOS_DA_ESCALA = (8, 6, 5, 4, 3, 2.5, 2, 1.5, 1)


def _passo_da_escala(valor):
    """Maior passo redondo (1, 1,5, 2, 2,5, 3, 4, 5, 6 ou 8 vezes uma potência de 10) que não passa do valor."""
    base = 10 ** math.floor(math.log10(valor))
    return next((base * m for m in PASSOS_DA_ESCALA if base * m <= valor), base)


def montar_layout(nome, camada, titulo='Mapa', fazenda='', proprietario='', campos=None, perimetro=None,
                  logo=None, unidade='', pagina='A4', camadas_extra=None, grade=False, casas=2,
                  ocultar_vazias=False, legenda_titulo='Legenda', substituir=True, contorno_perimetro=True,
                  atlas_camada=None, atlas_campo=None, atlas_rotulo='Talhão', atlas_margem=0.10):
    """Cria o layout no projeto aberto e devolve um resumo (classes, áreas, estatísticas).

    camada      a camada do mapa, já em classes (raster classificado ou vetor categorizado/graduado)
    campos      [('Safra', '25/26'), ('Atributo', 'Argila'), …] — entram na coluna da direita
    perimetro   camada de polígonos dos talhões: define o enquadramento e é desenhada por cima,
                só com o contorno (contorno_perimetro=False usa o estilo que a camada já tem)
    logo        caminho da imagem da logo DO CLIENTE; sem ela, o espaço some
    atlas_camada, atlas_campo
                uma página por feição dessa camada (os talhões), com o nome lido de atlas_campo.
                O mapa enquadra cada talhão; a legenda segue com as áreas do mapa inteiro.
    """
    projeto = QgsProject.instance()
    gerente = projeto.layoutManager()
    antigo = gerente.layoutByName(nome)
    if antigo is not None:
        if not substituir:
            raise ValueError(f'já existe um layout chamado "{nome}"')
        gerente.removeLayout(antigo)
    classes, estat = areas_por_classe(camada)
    if ocultar_vazias:
        classes = [c for c in classes if c['ha'] > 0]
    area_total = sum(c['ha'] for c in classes)

    largura, altura = PAGINAS[pagina.upper()]
    k = largura / 297.0  # tudo escala com a página
    layout = QgsPrintLayout(projeto)
    layout.initializeDefaults()
    layout.setName(nome)
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(largura, altura, MM))

    m, topo, col = 6 * k, 17 * k, 78 * k        # margem, faixa de cima, coluna da direita
    xc = largura - m - col                      # onde começa a coluna
    _caixa(layout, m, m, largura - 2 * m, altura - 2 * m, traco=0.5 * k)

    # ---- faixa de cima: logo + Fazenda / Proprietário
    x_campos = m
    if logo:
        larg_logo = 52 * k
        _caixa(layout, m, m, larg_logo, topo)
        figura = QgsLayoutItemPicture(layout)
        figura.setPicturePath(str(logo))
        figura.setResizeMode(QgsLayoutItemPicture.Zoom)
        layout.addLayoutItem(figura)
        figura.attemptMove(_ponto(m + 1.5 * k, m + 1.5 * k))
        figura.attemptResize(_tamanho(larg_logo - 3 * k, topo - 3 * k))
        x_campos = m + larg_logo
    larg_campos = xc - x_campos
    for n, (rotulo, valor) in enumerate((('Fazenda:', fazenda), ('Proprietário:', proprietario))):
        y = m + n * topo / 2
        _caixa(layout, x_campos, y, larg_campos, topo / 2)
        _texto(layout, rotulo, x_campos + 2 * k, y, 30 * k, topo / 2, tam=10 * k, negrito=True)
        _texto(layout, valor or '', x_campos + 32 * k, y, larg_campos - 34 * k, topo / 2, tam=10 * k)

    # ---- o mapa
    crs = _crs_em_metros(camada)
    mapa = QgsLayoutItemMap(layout)
    mapa.setId('mapa')
    mapa.setCrs(crs)
    visiveis = ([perimetro] if perimetro else []) + list(camadas_extra or []) + [camada]
    mapa.setLayers(visiveis)
    mapa.setKeepLayerSet(True)
    mapa.setKeepLayerStyles(True)  # o layout guarda o estilo de agora: a legenda escrita não desmente o mapa
    if perimetro and contorno_perimetro:
        estilos = dict(mapa.layerStyleOverrides())
        da_pagina = atlas_camada is not None and atlas_camada.id() == perimetro.id()
        estilos[perimetro.id()] = _so_contorno(perimetro, 0.3 * k, destaque=da_pagina)
        mapa.setLayerStyleOverrides(estilos)
    layout.addLayoutItem(mapa)
    mx, my = m, m + topo
    mw, mh = xc - m, altura - 2 * m - topo
    mapa.attemptMove(_ponto(mx, my))
    mapa.attemptResize(_tamanho(mw, mh))
    base = perimetro or camada
    quadro = QgsCoordinateTransform(base.crs(), crs, projeto).transformBoundingBox(base.extent())
    quadro.scale(1.08)
    mapa.zoomToExtent(quadro)
    mapa.setFrameEnabled(True)
    mapa.setFrameStrokeWidth(layout.convertFromLayoutUnits(0.3, MM))
    mapa.setBackgroundColor(QColor(255, 255, 255))
    if grade:
        linhas = QgsLayoutItemMapGrid('coordenadas', mapa)
        passo = _passo_redondo(max(mapa.extent().width(), mapa.extent().height()) / 4)
        linhas.setIntervalX(passo)
        linhas.setIntervalY(passo)
        linhas.setStyle(QgsLayoutItemMapGrid.FrameAnnotationsOnly)
        linhas.setAnnotationEnabled(True)
        linhas.setAnnotationPrecision(0)
        linhas.setAnnotationFont(QFont(FONTE, max(5, int(6 * k))))
        linhas.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical, QgsLayoutItemMapGrid.Left)
        linhas.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical, QgsLayoutItemMapGrid.Right)
        mapa.grids().addGrid(linhas)

    # ---- coluna da direita: título e dados
    y = m
    _caixa(layout, xc, y, col, topo)
    _texto(layout, titulo, xc + 1 * k, y, col - 2 * k, topo, tam=12.5 * k, negrito=True, alinh='centro')
    y += topo
    dados = list(campos or []) + [('Área Total', f'{br(area_total, casas)} ha')]
    if atlas_camada is not None:
        # em cada página: o nome e a área do talhão; as áreas da legenda seguem sendo as do mapa inteiro
        # o número sai em pt-BR mesmo num QGIS em outro idioma (o try cobre o QGIS antigo, sem o 3º argumento)
        hectares = ("area(transform(@atlas_geometry, layer_property(@atlas_layerid, 'crs'), '" + crs.authid()
                    + "')) / 10000")
        area_do_talhao = ('[% coalesce(try(format_number(' + hectares + ", 2, 'pt_BR')), format_number("
                          + hectares + ', 2)) %] ha')
        dados = ([(atlas_rotulo, '[% @atlas_pagename %]'), (f'Área do {atlas_rotulo.lower()}', area_do_talhao)]
                 + list(campos or []) + [('Área do mapa', f'{br(area_total, casas)} ha')])
    alt_linha = 7.2 * k
    alt_dados = alt_linha * len(dados) + 3 * k
    _caixa(layout, xc, y, col, alt_dados)
    for n, (rotulo, valor) in enumerate(dados):
        yy = y + 1.5 * k + n * alt_linha
        _texto(layout, f'{rotulo}:', xc + 2.5 * k, yy, 34 * k, alt_linha, tam=10 * k, negrito=True)
        _texto(layout, valor, xc + 2.5 * k + _largura(f'{rotulo}:', 10 * k), yy, col - 5 * k, alt_linha, tam=9.5 * k)
    y += alt_dados

    # ---- rodapé da coluna: mínimo, máximo, média, norte e data (altura fixa)
    alt_rodape = 30 * k
    alt_escala = 16 * k
    y_rodape = altura - m - alt_rodape
    y_escala = y_rodape - alt_escala

    # ---- legenda
    alt_legenda = y_escala - y
    _caixa(layout, xc, y, col, alt_legenda)
    _texto(layout, legenda_titulo, xc, y + 1 * k, col, 8 * k, tam=12 * k, negrito=True, alinh='centro')
    cabeca = 'CLASSE' + (f' ({unidade})' if unidade else '') + (' · áreas do mapa inteiro' if atlas_camada is not None else '')
    _texto(layout, cabeca, xc + 3 * k, y + 9 * k, col - 6 * k, 5 * k, tam=8 * k)
    livre = alt_legenda - 16 * k
    passo = min(6.0 * k, livre / max(len(classes), 1))
    tam_classe = max(5.0, min(8.5 * k, passo * 1.45))
    for n, c in enumerate(classes):
        yy = y + 15 * k + n * passo
        r, g, b = QColor(c['cor']).red(), QColor(c['cor']).green(), QColor(c['cor']).blue()
        _caixa(layout, xc + 3.5 * k, yy + passo * 0.14, 8 * k, passo * 0.72, cor=f'{r},{g},{b},255', traco=0.15)
        _texto(layout, f"{c['rotulo']} | {br(c['ha'], casas)} ha ({br(c['pct'], 1)}%)", xc + 13.5 * k, yy,
               col - 15 * k, passo, tam=tam_classe)

    # ---- escala
    _caixa(layout, xc, y_escala, col, alt_escala)
    barra = QgsLayoutItemScaleBar(layout)
    barra.setLinkedMap(mapa)
    barra.setStyle('Line Ticks Up')
    largura_util = col - 24 * k                       # mm que a barra inteira pode ocupar na coluna
    por_mm = largura_util / 4 / 1000                  # metros de terreno por segmento = escala × por_mm
    passo = _passo_da_escala(mapa.scale() * por_mm)   # passo redondo que cabe em 4 segmentos
    # no atlas cada página tem a sua escala: metros servem a qualquer talhão
    quilometros = passo >= 1000 and atlas_camada is None
    barra.setUnits(QgsUnitTypes.DistanceKilometers if quilometros else QgsUnitTypes.DistanceMeters)
    barra.setUnitLabel('km' if quilometros else 'Metros')
    barra.setNumberOfSegments(4)
    barra.setNumberOfSegmentsLeft(0)
    barra.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
    barra.setUnitsPerSegment(passo / 1000 if quilometros else passo)
    # números da escala iguais em qualquer idioma do QGIS: sem separador de milhar, vírgula decimal
    numeros = QgsBasicNumericFormat()
    numeros.setShowThousandsSeparator(False)
    numeros.setShowTrailingZeros(False)
    if hasattr(numeros, 'setDecimalSeparator'):
        numeros.setDecimalSeparator(',')
    barra.setNumericFormat(numeros)
    if atlas_camada is not None and hasattr(QgsLayoutObject, 'ScalebarSegmentWidth'):
        # a mesma conta do passo redondo, refeita pelo QGIS na escala de cada página
        faixas = ' '.join(f'WHEN @m >= {m} THEN {m}' for m in PASSOS_DA_ESCALA[:-1])
        conta = ("with_variable('alvo', map_get(item_variables('mapa'), 'map_scale') * " + repr(por_mm)
                 + ", with_variable('base', 10 ^ floor(log10(@alvo)), with_variable('m', @alvo / @base, "
                 + '@base * CASE ' + faixas + ' ELSE 1 END)))')
        barra.dataDefinedProperties().setProperty(QgsLayoutObject.ScalebarSegmentWidth,
                                                  QgsProperty.fromExpression(conta))
    elif atlas_camada is not None:
        # QGIS antigo: ele mesmo ajusta o passo à largura (os limites são da barra INTEIRA)
        barra.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
        barra.setMinimumBarWidth(34 * k)
        barra.setMaximumBarWidth(largura_util)
    barra.setFont(QFont(FONTE, max(5, int(7 * k))))
    layout.addLayoutItem(barra)
    barra.attemptMove(_ponto(xc + 4 * k, y_escala + 3 * k))

    # ---- norte, data e estatísticas
    larg_norte = 30 * k
    _caixa(layout, xc, y_rodape, larg_norte, alt_rodape)
    norte = QgsLayoutItemPicture(layout)
    norte.setPicturePath(':/images/north_arrows/layout_default_north_arrow.svg')
    norte.setLinkedMap(mapa)
    layout.addLayoutItem(norte)
    norte.attemptMove(_ponto(xc + larg_norte / 2 - 5 * k, y_rodape + 2 * k))
    norte.attemptResize(_tamanho(10 * k, 15 * k))
    agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    _texto(layout, 'Mapa atualizado em:', xc, y_rodape + 18.5 * k, larg_norte, 5 * k, tam=6 * k, alinh='centro')
    _texto(layout, agora, xc, y_rodape + 23 * k, larg_norte, 5 * k, tam=6 * k, alinh='centro')
    _caixa(layout, xc + larg_norte, y_rodape, col - larg_norte, alt_rodape)
    if estat:
        for n, (rotulo, chave) in enumerate((('Mínimo', 'min'), ('Máximo', 'max'), ('Média', 'media'))):
            yy = y_rodape + 2 * k + n * 8.6 * k
            _texto(layout, f'{rotulo}:', xc + larg_norte + 3 * k, yy, 24 * k, 8 * k, tam=10.5 * k, negrito=True)
            _texto(layout, br(estat[chave], casas), xc + larg_norte + 26 * k, yy, col - larg_norte - 28 * k, 8 * k,
                   tam=10.5 * k)

    paginas = None
    if atlas_camada is not None:
        if not atlas_campo:
            raise ValueError('atlas: informe atlas_campo, o atributo com o nome de cada talhão')
        atlas = layout.atlas()
        atlas.setCoverageLayer(atlas_camada)
        atlas.setPageNameExpression(f'"{atlas_campo}"')
        atlas.setSortFeatures(True)
        atlas.setSortExpression(f'"{atlas_campo}"')
        atlas.setEnabled(True)
        mapa.setAtlasDriven(True)
        mapa.setAtlasScalingMode(QgsLayoutItemMap.Auto)
        mapa.setAtlasMargin(atlas_margem)
        atlas.updateFeatures()  # sem isto a contagem vem zerada
        paginas = atlas.count()

    gerente.addLayout(layout)
    return {'layout': nome, 'pagina': pagina.upper(), 'crs_do_mapa': crs.authid(), 'escala': round(mapa.scale()),
            'atlas_paginas': paginas,
            'area_total_ha': round(area_total, 2), 'estatisticas': estat,
            'classes': [{'rotulo': c['rotulo'], 'ha': round(c['ha'], 2), 'pct': round(c['pct'], 1)} for c in classes]}


def _largura(texto, tam):
    """Largura aproximada (mm) de um texto em negrito, para pôr o valor logo depois do rótulo."""
    return len(texto) * tam * 0.21 + 2


def exportar(nome, caminho, dpi=200):
    """Exporta o layout para .pdf ou .png (pela extensão do caminho)."""
    layout = QgsProject.instance().layoutManager().layoutByName(nome)
    if layout is None:
        raise ValueError(f'não existe layout chamado "{nome}"')
    saida = QgsLayoutExporter(layout)
    if str(caminho).lower().endswith('.pdf'):
        opcoes = QgsLayoutExporter.PdfExportSettings()
        opcoes.dpi = dpi
        codigo = saida.exportToPdf(str(caminho), opcoes)
    else:
        opcoes = QgsLayoutExporter.ImageExportSettings()
        opcoes.dpi = dpi
        codigo = saida.exportToImage(str(caminho), opcoes)
    if codigo != QgsLayoutExporter.Success:
        raise RuntimeError(f'a exportação falhou (código {codigo})')
    return str(caminho)


def exportar_atlas(nome, caminho_pdf, dpi=150):
    """Exporta todas as páginas do atlas num PDF só. Para muitos talhões, prefira a tool
    export_atlas do conector: ela não tem o limite de tempo do execute_code."""
    layout = QgsProject.instance().layoutManager().layoutByName(nome)
    if layout is None or not layout.atlas().enabled():
        raise ValueError(f'o layout "{nome}" não tem atlas ligado: monte de novo com atlas_camada e atlas_campo')
    opcoes = QgsLayoutExporter.PdfExportSettings()
    opcoes.dpi = dpi
    codigo, erro = QgsLayoutExporter.exportToPdf(layout.atlas(), str(caminho_pdf), opcoes)
    if codigo != QgsLayoutExporter.Success:
        raise RuntimeError(f'a exportação do atlas falhou: {erro or codigo}')
    return str(caminho_pdf)


# a última definição do arquivo: só é verdadeira se o módulo chegou INTEIRO ao QGIS (cópia cortada
# não chega até aqui; cópia com uma função a menos dá falso)
_PARTES = ('PALETA', 'br', 'cores_para', 'classificar_raster', '_matriz', 'areas_por_classe', '_ponto', '_tamanho',
           '_caixa', '_texto', '_crs_em_metros', '_linha', '_so_contorno', '_passo_redondo', 'PASSOS_DA_ESCALA',
           '_passo_da_escala', 'montar_layout', '_largura', 'exportar', 'exportar_atlas')
FIM_DO_ARQUIVO = all(parte in globals() for parte in _PARTES)


if __name__ == '__main__':
    # exemplo embutido: o que dá para conferir sem o QGIS (o layout em si só roda dentro dele)
    assert br(1669.5) == '1.669,50' and br(0.2, 1) == '0,2' and br(5050.67) == '5.050,67'
    assert cores_para(1) == [PALETA[-1]] and len(cores_para(5)) == 5
    assert cores_para(5)[0] == PALETA[0] and cores_para(5)[-1] == PALETA[-1]
    assert cores_para(4, invertida=True) == cores_para(4)[::-1]
    assert [_passo_redondo(v) for v in (1.2, 3.7, 9, 480, 1250)] == [1, 2, 5, 200, 1000]
    assert abs(_largura('Safra:', 10) - 14.6) < 0.01
    # o arquivo viaja para o QGIS dentro de uma string bruta de aspas triplas simples: não pode
    # conter essas aspas nem barra invertida
    fonte = open(__file__, encoding='utf-8').read()
    assert chr(39) * 3 not in fonte and chr(92) not in fonte, 'aspas triplas simples ou barra invertida no módulo'
    assert sum(1 for linha in fonte.splitlines() if linha.startswith('FIM_DO_ARQUIVO')) == 1
    # toda função do arquivo tem de estar na lista que confere a cópia
    definidas = [linha[4:].split('(')[0] for linha in fonte.splitlines() if linha.startswith('def ')]
    assert FIM_DO_ARQUIVO and sorted(definidas + ['PALETA', 'PASSOS_DA_ESCALA']) == sorted(_PARTES), 'atualize _PARTES'
    assert [_passo_da_escala(v) for v in (1.2, 180, 470, 999, 7300)] == [1, 150, 400, 800, 6000]
    # a cópia que a IA manda ao QGIS é conferida por esta assinatura, que o SKILL.md traz escrita
    import hashlib
    import os
    assinatura = hashlib.md5(''.join(fonte.split()).encode('utf-8')).hexdigest()[:12]
    skill = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'SKILL.md')
    if os.path.exists(skill):
        assert assinatura in open(skill, encoding='utf-8').read(), 'atualize a assinatura no SKILL.md: ' + assinatura
    print('layout_agro OK (funções de texto, cores e escala)' +
          ('' if DENTRO_DO_QGIS else ' — o layout só é montado dentro do QGIS, pela ClaudIA QGIS'))
