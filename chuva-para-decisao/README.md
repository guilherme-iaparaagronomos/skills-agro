# Chuva para decisão

Skill para a sua IA descrever como a chuva se comportou num local, na época
que interessa a uma decisão de plantio ou de manejo. A resposta vem sempre em
contagem de anos: "em 7 de 10 anos choveu pelo menos 20 mm no primeiro
decêndio de outubro", "veranico de 10 dias ou mais em 4 de 10 anos".

O dado vem das ferramentas do conector **ClaudIA Clima**, da comunidade
agrônomo10X. As contas são de um script em Python que lê o texto das
ferramentas, confere e só então calcula.

## O que entrega

- **Calendário da chuva**, com a tabela mensal desde 1998: mediana, faixa,
  menor e maior de cada mês; total e posição de cada ano agrícola; o mês em
  que as águas firmaram e terminaram, por uma regra mensal; graus-dia.
- **O ano em curso** ao lado dos outros, com as frases da ferramenta.
- **A janela dia a dia** que você escolher, em vários anos: chuva por
  decêndio, veranicos, a data em que as águas firmaram e, noutra janela, a
  data em que terminaram.
- Relato em texto, tabelas em CSV, gráficos e relatório em PDF.

Os cortes e as regras (dia seco, tamanho do veranico, milímetros do decêndio,
regra do início e do fim das águas, base dos graus-dia) são seus: a skill
mostra os de uso comum e pergunta. Sem eles o script não calcula.

## O que precisa

- Conector ClaudIA Clima ligado à sua IA.
- Ambiente que rode Python 3.9 ou mais novo, com `numpy` e `matplotlib`.
- O local: fazenda salva, perímetro ou latitude e longitude.

Cada chamada conta uma consulta de clima da sua conta: 1 para a tabela mensal,
1 para o ano em curso e 1 por ano de cada janela. A skill diz a conta antes de
chamar.

## Estrutura

```
chuva-para-decisao/
  SKILL.md                 o roteiro que a IA segue
  README.md
  references/
    metodo.md              as regras, as contas e os limites
    arquivos.md            o formato dos arquivos que o script lê e grava
  scripts/
    chuva.py               a entrada: --conferir, o cálculo e --demo
    leitura.py             lê o texto das ferramentas e confere a transcrição
    mensal.py              calendário mensal, ano agrícola, regra mensal, graus-dia
    janela.py              decêndios, veranicos, início e fim das águas
    relato.py              as frases do relato
    saidas.py              CSV, gráficos e PDF
    sintetico.py           dados inventados para a demonstração e os testes
```

## Instalar

Baixe a pasta (ou o zip da página da skill) e instale como skill na sua IA.
Para ver funcionando sem conector, com dados inventados:

```
python scripts/chuva.py --demo
```

Cada módulo tem um teste embutido: `python scripts/janela.py`, e assim por
diante.

## Como foi testada

- **Testes embutidos** em seis módulos, com séries inventadas de resposta
  conhecida: início das águas plantado numa data, falso início, veranico de
  tamanho conhecido, decêndio com frequência conhecida, fim das águas
  plantado.
- **Contas refeitas por outro caminho** (expressões regulares e laços
  simples, sem usar os módulos da skill) em 3.000 séries diárias, 300
  conjuntos de anos e 300 tabelas mensais sorteadas: 44.910 conferências, sem
  diferença. Essa conferência achou um erro de um dia nos "dias até o alvo de
  graus-dia", corrigido antes da publicação.
- **Linha de comando**: 33 casos, 10 de uso normal e 23 de entrada ruim (dia
  a menos, valor trocado, ano faltando, ano repetido, locais diferentes,
  regra pela metade, arquivo trocado). Cada um recusa com o motivo.
- **Com o conector de verdade**, num ponto do Centro-Oeste: a tabela mensal de
  julho de 1998 a junho de 2026, o ano em curso, dez anos da janela de 15/09 a
  30/11 e cinco anos da janela de 01/04 a 31/05, em 17 consultas. A
  transcrição foi feita pela IA, como no uso real: 1.747 valores, e todos os
  blocos fecharam com os totais da ferramenta. Com dia seco abaixo de 2 mm, a
  maior sequência seca contada pelo script foi igual ao veranico máximo da
  ferramenta nos quinze blocos. As datas do fim das águas foram conferidas
  lendo o texto da ferramenta.
- **O PDF foi olhado**, página a página, com os dados reais e com a
  demonstração.

O que **não** foi testado:

- outro regime de chuva com dado real. Local sem estação seca, com chuva de
  inverno ou no hemisfério norte só passou por séries inventadas;
- janela que atravessa a virada do ano com dado real (só inventado);
- dia "SEM DADO" numa resposta real: não apareceu nenhum nos testes. O
  tratamento foi testado com dado inventado;
- o roteiro dentro de uma conversa com um usuário, e em mais de uma IA.

## Avisos

- É **descrição do registro, não previsão**. Não diz quanto vai chover nem
  quando plantar. A decisão é do responsável técnico.
- 10 a 28 anos mostram o que é comum, não o que é raro.
- A chuva é a estimada para o local a partir de pluviômetros e satélites, não
  a do pluviômetro da fazenda.
- Não é o ZARC e não o substitui.
- A tabela mensal e a janela dia a dia saem de réguas diferentes da
  ferramenta: não compare os milímetros de uma com os da outra.

Fonte da chuva: pluviômetros e satélites da comunidade agrônomo10X
(OagronomIA).
