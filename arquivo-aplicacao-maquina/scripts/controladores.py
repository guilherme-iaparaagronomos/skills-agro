"""Os controladores que a skill atende: a pasta do pen drive em que cada um
espera o mapa de aplicação e o que se sabe do caminho no monitor.

De onde vem cada informação está escrito em cada item:
- `material`: o material de campo do fundador da comunidade agrônomo10X
  (12/11/2026), que traz a pasta por controlador e as regras do arquivo;
- `oficial`: o que foi lido num manual ou numa página de ajuda do fabricante,
  com o documento. Só entra o que está escrito lá.
O que não foi achado em documento do fabricante fica dito como "não confirmado".

Teste embutido: python scripts/controladores.py
"""

MATERIAL = 'material de campo do fundador da comunidade agrônomo10X (12/11/2026)'
NAO_CONFIRMADO = 'não confirmado em documento do fabricante; confira no manual do seu monitor'

CONTROLADORES = {
    'trimble-cfx750': {
        'nome': 'Trimble CFX 750', 'pasta': 'AgGPS/Prescriptions', 'fonte_pasta': MATERIAL,
        'oficial': [],
        'menu': None,
    },
    'trimble-gfx750': {
        'nome': 'Trimble GFX 750', 'pasta': 'AgDATA/Prescriptions', 'fonte_pasta': MATERIAL,
        'oficial': [],
        'menu': None,
    },
    'stara': {
        'nome': 'Stara', 'pasta': 'Dados/Mapas', 'fonte_pasta': MATERIAL,
        'oficial': ['a taxa variável segue arquivos shapefile importados por pen drive ou pela telemetria da marca '
                    '(prospecto do Topper 5500, Stara)'],
        'menu': None,
    },
    'raven': {
        'nome': 'Raven', 'pasta': 'ePro/WorkOrders/rxMaps', 'fonte_pasta': MATERIAL,
        'oficial': ['o mapa tem de ser shapefile de polígonos, no datum WGS 84; os arquivos são o .shp, o .shx e o .dbf '
                    '(manual do console Viper Pro, Raven)',
                    'o mapa deve ter o menor número de zonas possível, e a menor zona não deve ser mais estreita que a '
                    'largura da barra (manual do console Viper Pro, Raven)',
                    'o manual do Viper Pro fala em copiar os arquivos para a pasta RxMaps do pen drive; a pasta desta '
                    'skill é a do material de campo: se o seu console não achar o mapa, confira o caminho no manual dele'],
        'menu': 'no console, o menu de mapas de prescrição (Rx Map)',
    },
    'john-deere': {
        'nome': 'John Deere', 'pasta': 'Rx', 'fonte_pasta': MATERIAL + '; confirmada na ajuda do monitor',
        'oficial': ['para importar prescrições, os shapefiles têm de estar numa pasta chamada Rx na raiz do pen drive '
                    '(ajuda dos monitores 4640 e G5, John Deere, tela Gerenciador de Arquivos, Importar)',
                    'dose zero no mapa desliga as seções quando o controle de seções está ligado (ajuda dos monitores, '
                    'tela Mapas de Prescrição)'],
        'menu': 'Gerenciador de Arquivos, Importar do pen drive; depois escolha a prescrição na Configuração de Trabalho',
    },
    'new-holland': {
        'nome': 'New Holland (IntelliView IV e Pro 700)', 'pasta': 'Shapefile', 'fonte_pasta': MATERIAL,
        'oficial': [],
        'menu': None,
    },
    'hexagon': {
        'nome': 'Hexagon', 'pasta': '', 'fonte_pasta': MATERIAL,
        'oficial': ['a importação é pelo menu Arquivos, Importar do USB, opção Mapa de recomendação (manual do usuário '
                    'dos displays Ti5 e Ti7, versão V3R009, Hexagon)',
                    'na taxa variável o operador escolhe no display o mapa e o ATRIBUTO do mapa que traz a dose (mesmo manual)',
                    'no controle de fertilização há uma dose de fora do mapa, em kg/ha, a configurar no display; no atuador '
                    'linear, fora dos limites do mapa nada é aplicado (mesmo manual)'],
        'menu': 'Menu de configuração, Arquivos, Importar do USB, Mapa de recomendação; depois, no controle, Taxa variável, '
                'o mapa e o atributo da dose',
    },
    'arvus': {'nome': 'Arvus', 'pasta': '', 'fonte_pasta': MATERIAL, 'oficial': [], 'menu': None},
    'agres': {'nome': 'Agres', 'pasta': '', 'fonte_pasta': MATERIAL, 'oficial': [], 'menu': None},
    'jacto': {'nome': 'Jacto', 'pasta': '', 'fonte_pasta': MATERIAL, 'oficial': [], 'menu': None},
}

# formato próprio: a skill não gera
RECUSADOS = {
    'verion': ('Verion',
               'o controlador Verion usa formato próprio (uma pasta com o nome do talhão ou do produto e os arquivos '
               'product1.bmp, product1.dat e product1.map), não shapefile. Não achei documentação pública desse formato, '
               'então não há como gerar o arquivo e conferir se a máquina vai ler a dose certa. Use o programa do '
               'fabricante ou peça o conversor à assistência. Se o usuário quiser só o shapefile conferido para levar a esse '
               'programa, gere com um controlador que grava na raiz do pen drive (hexagon, arvus, agres ou jacto) e diga que '
               'aquele arquivo ainda não é o da Verion'),
}

REGRAS_DO_PEN_DRIVE = [
    'pen drive formatado em FAT32 e, em geral, com menos de 4 GB',
    'só os três arquivos do mapa: .shp, .shx e .dbf (sem .prj, .cpg, .qpj ou outros)',
    'os três com o mesmo nome, curto, sem espaço, acento ou símbolo',
]


def achar(texto):
    """Devolve a chave do controlador a partir do que o usuário escreveu, ou None."""
    t = ''.join(c for c in str(texto).lower() if c.isalnum())
    apelidos = {
        'trimble-cfx750': ('trimblecfx750', 'cfx750', 'cfx'), 'trimble-gfx750': ('trimblegfx750', 'gfx750', 'gfx'),
        'stara': ('stara', 'topper'), 'raven': ('raven', 'viper'), 'john-deere': ('johndeere', 'deere', 'jd', 'greenstar'),
        'new-holland': ('newholland', 'nh', 'intelliview', 'intelliviewiv', 'pro700'), 'hexagon': ('hexagon', 'ti5', 'ti7'),
        'arvus': ('arvus',), 'agres': ('agres',), 'jacto': ('jacto',), 'verion': ('verion',),
    }
    for chave, nomes in apelidos.items():
        if t == ''.join(c for c in chave if c.isalnum()) or t in nomes:
            return chave
    return None


def lista():
    return [f'{chave} ({c["nome"]})' for chave, c in CONTROLADORES.items()]


def caminho_no_pen_drive(chave, nome):
    """O caminho do .shp dentro do pen drive, com barras normais."""
    pasta = CONTROLADORES[chave]['pasta']
    return f'{pasta}/{nome}.shp' if pasta else f'{nome}.shp'


def passo_a_passo(chave, nome, campo, unidade):
    """As linhas do passo a passo para o operador."""
    c = CONTROLADORES[chave]
    pasta = c['pasta']
    onde = f'dentro da pasta {pasta}/' if pasta else 'soltos na raiz, sem pasta'
    linhas = [
        f'# Passo a passo: {c["nome"]}', '',
        '1. Use um pen drive formatado em FAT32 (em geral, com menos de 4 GB).',
        '2. Extraia o zip na RAIZ do pen drive, mantendo as pastas. Não extraia dentro de outra pasta.',
        f'3. Confira no pen drive: os arquivos {nome}.shp, {nome}.shx e {nome}.dbf têm de estar {onde}.',
        '4. Não acrescente outros arquivos do mapa (.prj, .cpg, .qpj): este pacote leva só os três de propósito.',
    ]
    if c['menu']:
        linhas.append(f'5. No monitor: {c["menu"]}.')
    else:
        linhas.append('5. No monitor: importe o mapa pelo menu de taxa variável ou de mapas de prescrição. O caminho exato '
                      'do menu deste controlador não foi confirmado em manual: siga o do seu monitor.')
    linhas += [
        f'6. Quando o monitor pedir a coluna (ou o atributo) da dose, escolha {campo}. A unidade do arquivo é {unidade}: '
        'ajuste a unidade no monitor para a mesma.',
        '7. Antes de aplicar, confira no monitor a dose de dois ou três polígonos contra a tabela conferencia.csv.',
        '', f'Pasta do pen drive: {c["fonte_pasta"]}.',
    ]
    for o in c['oficial']:
        linhas.append(f'Do fabricante: {o}.')
    if not c['oficial']:
        linhas.append('Limite de polígonos, unidade esperada e caminho do menu deste controlador: ' + NAO_CONFIRMADO + '.')
    else:
        linhas.append('Limite de polígonos e tamanho máximo do arquivo: ' + NAO_CONFIRMADO + '.')
    return linhas


if __name__ == '__main__':
    assert len(CONTROLADORES) == 10 and achar('John Deere') == 'john-deere' and achar('CFX 750') == 'trimble-cfx750'
    assert achar('gfx-750') == 'trimble-gfx750' and achar('Verion') == 'verion' and achar('Pro 700') == 'new-holland'
    assert achar('outra marca') is None
    assert caminho_no_pen_drive('stara', 'ADUBO01') == 'Dados/Mapas/ADUBO01.shp'
    assert caminho_no_pen_drive('jacto', 'ADUBO01') == 'ADUBO01.shp'
    assert caminho_no_pen_drive('raven', 'N1') == 'ePro/WorkOrders/rxMaps/N1.shp'
    for chave in CONTROLADORES:
        texto = '\n'.join(passo_a_passo(chave, 'ADUBO01', 'DOSE', 'kg/ha'))
        assert 'ADUBO01.shp' in texto and 'FAT32' in texto and 'DOSE' in texto, chave
        assert all(not p.startswith('/') and '\\' not in p for p in [CONTROLADORES[chave]['pasta']])
    assert 'soltos na raiz' in '\n'.join(passo_a_passo('agres', 'A', 'DOSE', 'kg/ha'))
    assert 'não confirmado' in '\n'.join(passo_a_passo('jacto', 'A', 'DOSE', 'kg/ha'))
    print('controladores OK: 10 controladores, pastas do pen drive, apelidos, passo a passo, Verion recusado')
