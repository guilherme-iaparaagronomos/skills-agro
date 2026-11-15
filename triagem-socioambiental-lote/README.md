# Triagem de vários imóveis

Skill da comunidade agrônomo10X para levantar, com a sua IA, uma lista de
imóveis rurais de uma vez: para cada CAR, fazenda salva ou perímetro, a
ficha em PDF e uma linha numa planilha com o uso do solo, a vegetação nativa
aberta depois de 2008, 2019 e 2020, PRODES e DETER, a sobreposição com
unidades de conservação e terras indígenas, os termos de embargo, o relevo e
o solo.

Serve para cooperativa, revenda, trading, banco e consultoria que precisam
olhar uma carteira.

Só fatos. A planilha não tem semáforo, nota nem parecer, e não diz que um
imóvel está regular ou irregular. Se você tem um critério da casa, informe:
ela marca quem se encaixa, numa coluna com o nome da sua regra.

## O que precisa

- O conector **ClaudIA Sat** ligado na sua IA.
- A lista de imóveis (números de CAR, fazendas salvas ou perímetros).
- Para a planilha: um ambiente que rode Python 3 (só a biblioteca padrão).

Cada imóvel consome, da franquia de satélite, a área dele, e leva de 20
segundos a pouco mais de 1 minuto. A skill trabalha em lotes de até 5, diz o
acumulado e o que falta da lista, e continua de onde parou.

## Estrutura

```
triagem-socioambiental-lote/
  SKILL.md                o roteiro que a IA segue
  README.md
  references/colunas.md   cada coluna da planilha e de onde ela vem
  scripts/
    triagem.py            entrada: --conferir, a planilha, --criterio e --demo
    leitura.py            lê o resumo que a ferramenta do dossiê devolve
    sintetico.py          quatro imóveis inventados para a demonstração
```

Para ver funcionando sem conector nenhum:

```
python scripts/triagem.py --demo --criterio "prodes_2020_ha > 0" --saida saida-demo
```

## Instalar

Baixe o zip pelo botão da página da skill, ou a pasta deste repositório, e
adicione como skill na sua IA (em Claude: Configurações › Capacidades ›
Skills; em outras IAs compatíveis, a pasta de skills do projeto).

## Como foi testada

- **Dados inventados**: quatro imóveis, um deles com duas seções que não
  saíram; a planilha deixa as células vazias e o critério responde "sem dado".
- **Respostas reais da ferramenta**: dois dossiês gerados de verdade, de dois
  perímetros pequenos (6 e 33 ha), copiados para arquivo como a skill manda.
  Todas as colunas foram lidas e conferidas uma a uma com o texto.
- **O que não foi feito**: imóvel que entra pelo número do CAR (os dois
  entraram por perímetro, então a linha "o que o CAR declara" só foi lida no
  formato tirado do código da ferramenta); imóvel com supressão, embargo ou
  sobreposição de verdade (os dois tinham tudo zero); lote grande, com
  retomada no dia seguinte; a skill inteira dentro de uma conversa em duas
  IAs diferentes.

## Avisos

- Não é certidão nem parecer. Vale pelas bases públicas, na data de cada uma.
- Célula vazia não é zero: a seção não saiu naquela emissão.
- Os termos de embargo vêm sem nome e sem documento de pessoa.
- O dossiê não cobre territórios quilombolas, assentamentos, florestas
  públicas, embargos estaduais nem zona de amortecimento.
- Se o texto do resumo da ferramenta mudar, o leitor precisa acompanhar: o
  `--conferir` mostra as seções lidas de cada imóvel justamente para isso.
- A decisão sobre cada imóvel é de quem responde por ela.

Autoria: Equipe agrônomo10X (OagronomIA).
