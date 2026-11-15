# Histórico por satélite de cada talhão

Skill da comunidade agrônomo10X para montar, com a sua IA, o histórico de cada
talhão em várias safras: os ciclos de vegetação que o satélite viu, com
início, pico e fim prováveis, e a chuva de cada safra ao lado da média
histórica.

Serve para quem assume uma área e quer saber o que ela fez nos últimos anos,
para conferir se houve segunda safra, para comparar o calendário de um talhão
com o de outro e para levar um retrato da área a uma reunião.

Só descreve. Não diz a cultura, não estima produtividade e não aponta talhão
ou safra melhor e pior.

## O que precisa

- Os conectores **ClaudIA Sat** e **ClaudIA Clima** ligados na sua IA.
- A fazenda salva na conta, com os talhões, ou o arquivo de perímetro.
- Para as datas dos ciclos, as figuras e o PDF: um ambiente que rode Python 3
  com numpy e matplotlib. Sem ele, a skill entrega só a tabela simples.

Cada safra consultada consome, da franquia de satélite, a soma das áreas dos
talhões pedidos, e conta uma consulta de clima.

## Estrutura

```
historico-produtivo-talhao/
  SKILL.md               o roteiro que a IA segue
  README.md
  references/metodo.md   as regras da detecção dos ciclos e os limites
  scripts/
    calendario.py        entrada: --conferir, a rodada e --demo
    leitura.py           lê as respostas das ferramentas coladas em texto
    ciclos.py            acha os ciclos numa curva
    historico.py         junta as safras e monta o quadro
    saidas.py            CSV, figuras e PDF
    sintetico.py         quatro safras inventadas para a demonstração
```

Para ver funcionando sem conector nenhum:

```
python scripts/calendario.py --demo --saida saida-demo
```

Cada módulo roda sozinho como teste: `python scripts/ciclos.py`.

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- **Dados inventados** (os da demonstração): 12 ciclos de forma conhecida em
  4 safras e 3 áreas, com falhas de imagem sorteadas. O script achou os 12,
  com início e fim a até 8 dias do valor certo e o pico a até 15 dias (o pico
  é a imagem mais alta; com 40 dias sem imagem em volta, ele se afasta).
- **Dados reais, tirados das ferramentas**: 5 safras de uma fazenda de cerca
  de 90 ha, como área única, e 2 safras da mesma fazenda talhão por talhão
  (5 talhões), com as respostas copiadas para arquivo como a skill manda. É
  uma fazenda só, numa região só. Foi nesse teste que apareceram dois
  defeitos, já corrigidos: uma colheita era lida como queda isolada, e um
  patamar com ondulação virava dois ciclos.
- **O que não foi feito**: comparar as datas com o caderno de campo de uma
  fazenda (plantio e colheita anotados); rodar a skill inteira dentro de uma
  conversa em duas IAs diferentes; testar com mais de 8 talhões numa chamada.

## Avisos

- O início do ciclo não é a data do plantio, e o fim não é a da colheita.
- A média do talhão esconde manchas e talhões divididos.
- Em pasto, cana, café e mata, o que aparece é a estação do ano.
- Com muita nuvem, datas e picos ficam menos certos; o quadro diz onde.
- A leitura agronômica é do responsável técnico.

Autoria: Equipe agrônomo10X (OagronomIA).
