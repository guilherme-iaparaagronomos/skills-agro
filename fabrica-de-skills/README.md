# Fábrica de skills

Skill que **conduz a criação da sua própria skill**: você descreve uma rotina
que repete, e a IA transforma em um pacote que ela mesma passa a seguir, do
mesmo jeito todas as vezes.

**O que ela faz, em sete passos:**

1. entende a rotina com você (o que entra, o que sai, onde estão as suas
   decisões);
2. mostra que peça do acervo da comunidade agrônomo10X resolve cada passo: os
   quatro conectores, com cada ferramenta e para que serve, e as skills da
   casa;
3. ajuda a escolher o tipo: roteiro que chama ferramentas, skill com script
   ou roteiro para o QGIS;
4. escreve o `SKILL.md`, os scripts e o README, por um molde;
5. testa: exemplo inventado, um caso real seu, casos ruins e a conferência do
   resultado;
6. confere a pasta e gera o zip;
7. orienta a instalação e o primeiro uso.

As decisões técnicas da rotina são suas: a skill pergunta, não inventa.

## O que precisa

Uma IA que rode código (para o conferidor e para as skills com script). Os
conectores da comunidade ajudam, mas não são obrigatórios: com o conector de
conteúdo ligado, a IA confere a lista de skills que está no ar e lê uma skill
da casa como molde.

## Estrutura

- [`SKILL.md`](SKILL.md) — o roteiro dos sete passos.
- `references/acervo.md` — o mapa do acervo: os conectores, as ferramentas e
  as skills da casa. É gerado a partir do que está no ar e traz a data.
- `references/modelo.md` — o molde de SKILL.md, de README e de scripts, e a
  lista de conferência.
- `scripts/validar.py` — confere a pasta de uma skill (cabeçalho, arquivos
  citados, tamanho, sintaxe dos scripts, segredo esquecido, acesso à rede) e
  gera o zip. Só biblioteca padrão do Python.

```
python scripts/validar.py <pasta da skill>
python scripts/validar.py <pasta da skill> --empacotar
python scripts/validar.py            # autoteste
```

## Instalar

Baixe [`fabrica-de-skills.zip`](../../../releases/latest/download/fabrica-de-skills.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Como foi testada

O conferidor tem autoteste (uma skill correta, uma com nome inválido, arquivo
citado que não existe, chave esquecida e erro de sintaxe) e foi passado em
todas as skills da casa. O mapa do acervo é gerado a partir da lista de
ferramentas que está no ar; o gerador para quando aparece uma ferramenta sem
descrição no mapa. O roteiro dos sete passos é o que a equipe segue para
fazer as skills da casa; ele ainda não foi acompanhado com um membro criando
a primeira skill.

## Avisos

A skill criada é sua, para a sua IA: ela não entra no catálogo da comunidade.
A lista de ferramentas muda com o tempo; o que vale é o que o conector mostra
na sua conta. A fábrica não valida a agronomia da sua rotina. Divergências ou
melhorias? Abra uma [issue](../../../issues/new/choose).
