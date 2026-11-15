# Molde de uma skill

Copie a estrutura, troque o conteúdo. O que está entre colchetes é para
preencher; o que está em itálico é comentário e sai da versão final.

## A pasta

```
nome-da-skill/
  SKILL.md          o roteiro que a IA segue (obrigatório)
  README.md         para a pessoa que instala
  references/       material de consulta: tabelas, método, formatos
  scripts/          só se houver conta exata ou arquivo para gerar
```

- O nome da pasta é o `name` do cabeçalho: minúsculas, números e hífen.
- Só arquivos de texto, de preferência com menos de 64 KB cada.
- Nome de arquivo sem espaço e sem acento.
- Até dois níveis de pasta (`scripts/leitura.py`, `references/metodo.md`).

## O SKILL.md

```
---
name: nome-da-skill
description: >-
  [O que a skill faz, numa frase curta.] [O que entra e o que sai.] [O que
  ela pergunta ao usuário.] [O que ela não faz.] Acione com "[frase que o
  usuário diria]", "[outra frase]" ou quando [a situação].
---

# [Nome da skill]

[Duas ou três linhas: o que o usuário recebe no fim.]

## Regras

- [O que vale para tudo. O que a IA nunca faz nesta rotina.]
- [De quem é cada decisão.]

## O que precisa estar disponível

- [Conector, se usar: qual, e o que acontece sem ele.]
- [Arquivos de entrada: formatos aceitos.]
- [Bibliotecas, se tiver script.]

## Antes de rodar: as perguntas

1. [O que a IA tem de perguntar. Uma linha por pergunta.]
2. [O que já foi dito não se pergunta de novo.]

## Fluxo de trabalho (siga nesta ordem)

1. [Passo, com o nome exato da ferramenta ou o comando do script.]
2. [O que conferir antes de seguir.]
3. [Como entregar o resultado e o que dizer junto.]

## O que a skill não faz

- [Limites. Quando parar e devolver ao usuário.]
```

### A description decide tudo

A IA lê só a `description` para escolher a skill. Uma boa description:

- começa pelo verbo do trabalho ("Monta", "Converte", "Limpa", "Confere");
- diz o que entra e o que sai com as palavras do usuário;
- lista as frases de acionamento entre aspas, do jeito que ele fala;
- diz o que a skill não faz, para ela não ser chamada no lugar errado;
- cabe em 1.024 caracteres, com a primeira frase em até 220.

Fraca: "Skill para análise de solo."
Boa: "Padroniza o laudo de solo do laboratório numa tabela única, com as
unidades conferidas, e aponta o que falta. Entra o PDF ou a planilha do
laudo; sai um CSV. Não recomenda adubação. Acione com "padroniza esse
laudo", "organiza a análise de solo" ou quando o usuário enviar um laudo."

### O corpo é um roteiro, não um texto

- Frases no imperativo, um passo por linha, em ordem.
- O nome exato de cada ferramenta e de cada parâmetro, entre crases.
- Explique o porquê das regras: a IA segue melhor o que entende.
- Material longo (tabela de classes, descrição do método) vai para
  `references/` e é citado pelo caminho.
- Sem negrito em tudo, sem maiúsculas para gritar: destaque só a regra que
  costuma ser quebrada.

## Os scripts

- Um script de entrada com `--help` e com `--demo` (dado inventado embutido).
- Um autoteste por módulo: rodar o arquivo sem argumentos confere as contas.
- Quando houver escolha técnica, duas etapas: `--diagnostico` mostra o dado e
  as opções; a execução só roda com a escolha informada, e recusa sem ela.
- Recusas com motivo: "a coluna X não existe; as colunas são A, B, C".
- Saídas com nome fixo numa pasta escolhida pelo usuário (`--saida`).
- Sem caminho da sua máquina, sem rede, sem senha.
- Números com a unidade junto, datas em dd/mm/aaaa, decimal com vírgula nos
  documentos e com ponto nos arquivos de dados.

## O README.md

```
# [Nome da skill]

[O que a skill faz e para quem.]

## O que precisa
## Estrutura
## Instalar
## Como foi testada   (o que foi com dado real e o que foi com dado inventado)
## Avisos            (limites, de quem é a decisão)
```

## Antes de dizer que está pronta

- [ ] O `--demo` roda numa máquina limpa.
- [ ] Um caso real foi comparado com o resultado feito à mão.
- [ ] Os casos ruins são recusados com motivo.
- [ ] Alguém olhou o PDF, o mapa ou a planilha.
- [ ] O SKILL.md se sustenta sozinho, sem a conversa em que nasceu.
- [ ] `python scripts/validar.py <pasta>` não aponta erro.
- [ ] Não há dado de cliente, senha nem caminho da sua máquina na pasta.
- [ ] O README diz o que foi testado e o que não foi.
