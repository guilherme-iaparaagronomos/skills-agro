#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confere a pasta de uma skill e, se estiver tudo certo, empacota o zip para instalar na IA.

    python validar.py <pasta da skill>                    confere e mostra o relatório
    python validar.py <pasta da skill> --empacotar        confere e gera <nome>.zip ao lado da pasta
    python validar.py <pasta da skill> --empacotar x.zip  idem, no caminho indicado
    python validar.py                                     autoteste

Só biblioteca padrão. Não acessa rede e não executa nada da skill conferida: os scripts dela são
só lidos e compilados para achar erro de sintaxe.
"""
import os
import re
import sys
import zipfile

LIMITE_NOME = 64
LIMITE_DESCRICAO = 1024
LIMITE_PRIMEIRA_FRASE = 220
LIMITE_ARQUIVO = 64 * 1024
LINHAS_SKILL_LONGO = 500
TEXTO = {'.md', '.py', '.txt', '.csv', '.tsv', '.json', '.yaml', '.yml', '.html', '.css', '.js', '.mjs', '.ts', '.sql', '.r', '.sh'}
FORA_DO_PACOTE = {'__pycache__', '.git', '.venv', 'venv', 'node_modules', '.ipynb_checkpoints'}
NOME_OK = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
ARQUIVO_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
SEGREDOS = [
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'), 'chave privada'),
    (re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'), 'chave de API (sk-...)'),
    (re.compile(r'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'), 'token (eyJ...)'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), 'chave de nuvem (AKIA...)'),
    (re.compile(r'(?i)\b(api[_-]?key|secret|token|senha|password|passwd)\b\s*[:=]\s*["\'][^"\'\s]{8,}["\']'), 'segredo escrito no arquivo'),
]
REDE_OU_EXECUCAO = re.compile(
    r'^\s*(?:import|from)\s+(requests|urllib|http\.client|httpx|aiohttp|socket|ftplib|smtplib|subprocess|paramiko)\b'
    r'|\bos\.system\s*\(|\bos\.popen\s*\(|\beval\s*\(|\bexec\s*\(', re.M)
CAMINHO_DA_MAQUINA = re.compile(r'(?<![A-Za-z])[A-Za-z]:\\\\?(?:Users|Usuarios|Documents)\b|/home/[a-z]|/Users/[A-Za-z]')
CITADO = re.compile(r'`((?:references|scripts|assets|templates)/[A-Za-z0-9._/-]+)`')


class Relatorio:
    def __init__(self):
        self.itens = []

    def ok(self, texto):
        self.itens.append(('ok', texto))

    def aviso(self, texto):
        self.itens.append(('aviso', texto))

    def erro(self, texto):
        self.itens.append(('erro', texto))

    @property
    def erros(self):
        return [t for n, t in self.itens if n == 'erro']

    @property
    def avisos(self):
        return [t for n, t in self.itens if n == 'aviso']

    def texto(self):
        marca = {'ok': '[ok]   ', 'aviso': '[aviso]', 'erro': '[ERRO] '}
        linhas = [f'{marca[n]} {t}' for n, t in self.itens]
        linhas.append('')
        linhas.append(f'{len(self.erros)} erro(s) · {len(self.avisos)} aviso(s)')
        if self.erros:
            linhas.append('Corrija os erros antes de empacotar. Aviso não impede: leia e decida.')
        return '\n'.join(linhas)


def ler_frontmatter(texto):
    """Devolve (campos, corpo). Aceita `chave: valor`, valor entre aspas e bloco `>-`, `>`, `|` ou `|-`."""
    texto = texto.replace('\r\n', '\n')
    if not texto.startswith('---\n'):
        return None, texto
    fim = texto.find('\n---', 4)
    if fim < 0:
        return None, texto
    bloco = texto[4:fim].split('\n')
    corpo = texto[fim + 4:].lstrip('\n')
    campos, chave, modo, partes = {}, None, None, []

    def fecha():
        if chave is None:
            return
        if modo in ('>', '>-'):
            campos[chave] = ' '.join(p.strip() for p in partes if p.strip())
        elif modo in ('|', '|-'):
            campos[chave] = '\n'.join(p.strip() for p in partes).strip()
        else:
            campos[chave] = ' '.join(p.strip() for p in partes).strip().strip('"\'')

    for linha in bloco:
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$', linha)
        if m and not linha.startswith((' ', '\t')):
            fecha()
            chave, resto = m.group(1), m.group(2).strip()
            if resto in ('>', '>-', '|', '|-'):
                modo, partes = resto, []
            else:
                modo, partes = None, [resto]
        elif chave is not None:
            partes.append(linha)
    fecha()
    return campos, corpo


def primeira_frase(texto):
    ponto = texto.find('. ')
    return texto[:ponto + 1] if ponto > 0 else texto


def arquivos_da_pasta(pasta):
    achados = []
    for raiz, pastas, nomes in os.walk(pasta):
        pastas[:] = sorted(p for p in pastas if p not in FORA_DO_PACOTE and not p.startswith('.'))
        for nome in sorted(nomes):
            if nome.startswith('.') or nome.endswith('.pyc'):
                continue
            caminho = os.path.join(raiz, nome)
            achados.append((os.path.relpath(caminho, pasta).replace(os.sep, '/'), caminho))
    return achados


def validar(pasta):
    r = Relatorio()
    pasta = os.path.abspath(pasta)
    if not os.path.isdir(pasta):
        r.erro(f'a pasta não existe: {pasta}')
        return r, None
    nome_pasta = os.path.basename(pasta.rstrip('/\\'))
    skill_md = os.path.join(pasta, 'SKILL.md')
    if not os.path.isfile(skill_md):
        r.erro('falta o SKILL.md na raiz da pasta (com esse nome, em maiúsculas)')
        return r, None
    bruto = open(skill_md, 'rb').read()
    try:
        texto = bruto.decode('utf-8')
    except UnicodeDecodeError:
        r.erro('o SKILL.md não está em UTF-8: salve de novo como UTF-8')
        return r, None
    campos, corpo = ler_frontmatter(texto.lstrip('\ufeff'))
    if campos is None:
        r.erro('o SKILL.md precisa começar com o cabeçalho entre duas linhas `---` (name e description)')
        return r, None

    nome = campos.get('name', '')
    if not nome:
        r.erro('falta `name` no cabeçalho')
    elif not NOME_OK.match(nome):
        r.erro(f'`name` só pode ter minúsculas, números e hífen (sem acento nem espaço): "{nome}"')
    elif len(nome) > LIMITE_NOME:
        r.erro(f'`name` com {len(nome)} caracteres (o limite é {LIMITE_NOME})')
    else:
        r.ok(f'name: {nome}')
        if nome != nome_pasta:
            r.aviso(f'o nome da pasta ("{nome_pasta}") é diferente do `name` ("{nome}"): deixe iguais')

    descricao = campos.get('description', '')
    if not descricao:
        r.erro('falta `description` no cabeçalho: é por ela que a IA decide quando usar a skill')
    else:
        if len(descricao) > LIMITE_DESCRICAO:
            r.erro(f'`description` com {len(descricao)} caracteres (o limite é {LIMITE_DESCRICAO})')
        else:
            r.ok(f'description: {len(descricao)} caracteres')
        if len(descricao) < 120:
            r.aviso('`description` curta: diga o que a skill faz, o que entra, o que sai e quando usar')
        if '"' not in descricao and '“' not in descricao:
            r.aviso('`description` sem frases de acionamento entre aspas (ex.: "quero o mapa de...", "faz o relatório de...")')
        frase = primeira_frase(descricao)
        if len(frase) > LIMITE_PRIMEIRA_FRASE:
            r.aviso(f'a primeira frase da `description` tem {len(frase)} caracteres: até {LIMITE_PRIMEIRA_FRASE} ela cabe inteira numa vitrine')
        if '<' in descricao or '>' in descricao:
            r.aviso('`description` com < ou >: tire, algumas IAs recusam')

    if not re.search(r'^# \S', corpo, re.M):
        r.aviso('o corpo do SKILL.md não tem um título (`# Nome da skill`)')
    linhas = corpo.count('\n') + 1
    if linhas > LINHAS_SKILL_LONGO:
        r.aviso(f'SKILL.md com {linhas} linhas: passe o material de consulta para `references/` e deixe aqui o roteiro')
    if not re.search(r'(?im)^\s*(\d+\.|-)\s+\S', corpo):
        r.aviso('o SKILL.md não tem passos em lista: a IA segue melhor um fluxo numerado')

    arquivos = arquivos_da_pasta(pasta)
    relativos = {rel for rel, _ in arquivos}
    for citado in sorted(set(CITADO.findall(corpo))):
        if citado.rstrip('/') not in relativos and not any(x.startswith(citado.rstrip('/') + '/') for x in relativos):
            r.erro(f'o SKILL.md cita `{citado}`, que não existe na pasta')
    tem_principal = False
    total = 0
    for rel, caminho in arquivos:
        tamanho = os.path.getsize(caminho)
        total += tamanho
        ext = os.path.splitext(rel)[1].lower()
        base = os.path.basename(rel)
        if base.lower() in ('.env', 'credentials.json', 'id_rsa') or ext in ('.pem', '.key', '.p12', '.pfx'):
            r.erro(f'{rel}: arquivo de credencial não entra numa skill')
            continue
        if any(not ARQUIVO_OK.match(parte) for parte in rel.split('/')):
            r.aviso(f'{rel}: nome com espaço, acento ou símbolo; use letras sem acento, números, ponto, hífen e sublinhado')
        if rel.count('/') > 2:
            r.aviso(f'{rel}: pasta dentro de pasta dentro de pasta; deixe em até dois níveis (scripts/x.py)')
        if ext not in TEXTO:
            r.aviso(f'{rel}: não é arquivo de texto ({ext or "sem extensão"}); confira se a IA onde você vai instalar aceita')
            continue
        if tamanho > LIMITE_ARQUIVO:
            r.aviso(f'{rel}: {tamanho // 1024} KB; acima de 64 KB divida em arquivos menores')
        try:
            conteudo = open(caminho, 'rb').read().decode('utf-8')
        except UnicodeDecodeError:
            r.aviso(f'{rel}: não está em UTF-8')
            continue
        for padrao, o_que in SEGREDOS:
            if padrao.search(conteudo):
                r.erro(f'{rel}: parece ter {o_que}; tire antes de empacotar')
        if CAMINHO_DA_MAQUINA.search(conteudo):
            r.aviso(f'{rel}: tem um caminho da sua máquina (a pasta do seu usuário); a skill roda em outro lugar')
        if ext == '.py':
            try:
                compile(conteudo, rel, 'exec')
            except SyntaxError as e:
                r.erro(f'{rel}: erro de sintaxe na linha {e.lineno}: {e.msg}')
                continue
            if REDE_OU_EXECUCAO.search(conteudo):
                r.aviso(f'{rel}: acessa a rede ou executa outro programa; confirme que é isso mesmo e diga no SKILL.md')
            if "__name__" in conteudo and '__main__' in conteudo:
                tem_principal = True
    r.ok(f'{len(arquivos)} arquivo(s), {total // 1024 or 1} KB no total')
    if any(rel.startswith('scripts/') and rel.endswith('.py') for rel in relativos) and not tem_principal:
        r.aviso('nenhum script tem o bloco `if __name__ == "__main__":`; sem ele não dá para rodar nem testar pela linha de comando')
    if 'README.md' not in relativos:
        r.aviso('sem README.md: ele é para a pessoa que vai instalar (o SKILL.md é para a IA)')
    return r, (nome or nome_pasta)


def empacotar(pasta, nome, destino=None):
    pasta = os.path.abspath(pasta)
    destino = destino or os.path.join(os.path.dirname(pasta), f'{nome}.zip')
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, caminho in arquivos_da_pasta(pasta):
            z.write(caminho, f'{nome}/{rel}')
    return destino


def _autoteste():
    import shutil
    import tempfile
    base = tempfile.mkdtemp(prefix='fabrica-')
    try:
        boa = os.path.join(base, 'mapa-de-exemplo')
        os.makedirs(os.path.join(boa, 'scripts'))
        os.makedirs(os.path.join(boa, 'references'))
        with open(os.path.join(boa, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write('---\nname: mapa-de-exemplo\ndescription: >-\n  Monta o mapa de exemplo a partir do perímetro e da tabela do usuário.\n'
                    '  Pergunta a classe e a unidade. Acione com "quero o mapa de exemplo" ou\n  "faz o mapa do talhão".\n---\n\n'
                    '# Mapa de exemplo\n\n1. Pergunte o perímetro.\n2. Rode `scripts/mapa.py`.\n3. Leia `references/metodo.md`.\n')
        with open(os.path.join(boa, 'README.md'), 'w', encoding='utf-8') as f:
            f.write('# Mapa de exemplo\n')
        with open(os.path.join(boa, 'scripts', 'mapa.py'), 'w', encoding='utf-8') as f:
            f.write('def soma(a, b):\n    return a + b\n\n\nif __name__ == "__main__":\n    assert soma(1, 2) == 3\n    print("ok")\n')
        with open(os.path.join(boa, 'references', 'metodo.md'), 'w', encoding='utf-8') as f:
            f.write('# Método\n')
        os.makedirs(os.path.join(boa, 'scripts', '__pycache__'))
        open(os.path.join(boa, 'scripts', '__pycache__', 'mapa.cpython-312.pyc'), 'wb').write(b'\x00')
        r, nome = validar(boa)
        assert not r.erros and not r.avisos, r.texto()
        zipado = empacotar(boa, nome)
        nomes = sorted(zipfile.ZipFile(zipado).namelist())
        assert nomes == ['mapa-de-exemplo/README.md', 'mapa-de-exemplo/SKILL.md', 'mapa-de-exemplo/references/metodo.md',
                         'mapa-de-exemplo/scripts/mapa.py'], nomes

        campos, corpo = ler_frontmatter('---\nname: x\ndescription: "uma: duas"\n---\n# T\n')
        assert campos == {'name': 'x', 'description': 'uma: duas'} and corpo == '# T\n', (campos, corpo)
        campos, _ = ler_frontmatter('---\nname: x\ndescription: |\n  linha 1\n  linha 2\n---\n')
        assert campos['description'] == 'linha 1\nlinha 2', campos

        ruim = os.path.join(base, 'Skill Ruim')
        os.makedirs(os.path.join(ruim, 'scripts'))
        chave = 'sk-' + 'a1B2c3D4e5F6g7H8i9J0k1L2'
        with open(os.path.join(ruim, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write('---\nname: Skill Ruim\ndescription: curta\n---\nUse `references/nao-existe.md`.\n')
        with open(os.path.join(ruim, 'scripts', 'roda.py'), 'w', encoding='utf-8') as f:
            f.write(f'import requests\nCHAVE = "{chave}"\ndef f(:\n')
        with open(os.path.join(ruim, '.env'), 'w', encoding='utf-8') as f:
            f.write('X=1\n')
        r, _ = validar(ruim)
        juntos = '\n'.join(r.erros)
        assert '`name` só pode ter' in juntos, juntos
        assert 'nao-existe.md' in juntos, juntos
        assert 'chave de API' in juntos, juntos
        assert sum('description' in a for a in r.avisos) >= 2, r.avisos

        sintaxe = os.path.join(base, 'com-erro')
        os.makedirs(os.path.join(sintaxe, 'scripts'))
        with open(os.path.join(sintaxe, 'SKILL.md'), 'w', encoding='utf-8') as f:
            f.write('---\nname: com-erro\ndescription: Faz uma coisa bem explicada, com entrada e saída, e é acionada com "faz a coisa" quando o usuário pede a coisa inteira.\n---\n# X\n1. passo\n')
        with open(os.path.join(sintaxe, 'scripts', 'a.py'), 'w', encoding='utf-8') as f:
            f.write('import subprocess\ndef f(:\n')
        r, _ = validar(sintaxe)
        assert any('erro de sintaxe' in e for e in r.erros), r.texto()

        sem = os.path.join(base, 'vazia')
        os.makedirs(sem)
        r, _ = validar(sem)
        assert any('falta o SKILL.md' in e for e in r.erros)
        r, _ = validar(os.path.join(base, 'nao-existe'))
        assert any('não existe' in e for e in r.erros)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print('autoteste: ok')


def main(args):
    if not args:
        _autoteste()
        return 0
    if args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    pasta = args[0]
    r, nome = validar(pasta)
    print(r.texto())
    if '--empacotar' in args:
        if r.erros:
            print('\nNão empacotei: há erro.')
            return 1
        i = args.index('--empacotar')
        destino = args[i + 1] if len(args) > i + 1 and not args[i + 1].startswith('--') else None
        print(f'\nPacote: {empacotar(pasta, nome, destino)}')
    return 1 if r.erros else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv[1:]))
