---
name: triagem-socioambiental-lote
description: >-
  Levanta vários imóveis rurais de uma vez e junta os fatos de cada um numa
  planilha, um imóvel por linha, com a ficha em PDF de cada um. Para cada CAR,
  fazenda salva ou perímetro, chama a ferramenta `dossie_pdf` da ClaudIA Sat e
  tira do resumo dela o uso do solo, a vegetação nativa aberta depois de 2008,
  2019 e 2020, PRODES e DETER, a sobreposição com unidades de conservação e
  terras indígenas, os termos de embargo, o relevo e o solo. Trabalha em lotes,
  faz a conta da franquia e diz o que falta da lista. Só fatos: não tem
  semáforo, nota nem parecer, e não diz que um imóvel está regular ou
  irregular; a única marcação é a do critério que o usuário informar. Acione
  com "triagem dos CARs", "levantamento de vários imóveis", "planilha
  socioambiental da carteira", "consulta em lote de CAR" ou quando o usuário
  trouxer uma lista de imóveis para levantar.
---

# Triagem de vários imóveis

Para cooperativa, revenda, trading, banco ou consultoria que precisa olhar
uma carteira de imóveis. O usuário recebe:

1. **uma ficha por imóvel**: o dossiê em PDF que a ferramenta `dossie_pdf`
   gera;
2. **a planilha** `triagem.csv`, com um imóvel por linha e todos os fatos em
   colunas (`references/colunas.md`);
3. **o quadro** `triagem.md`, com as colunas principais, para a conversa.

Quem produz o dado é a ferramenta do conector da comunidade agrônomo10X. O
script desta skill só lê o resumo que ela devolve e põe os imóveis lado a
lado.

## A regra que vale para tudo: só fatos

- NUNCA diga que um imóvel está regular, irregular, apto, inapto, aprovado,
  reprovado, liberado, embargado, com ou sem pendência, de risco alto, médio
  ou baixo. Não dê nota, faixa, cor, semáforo nem ordem do "pior" para o
  "melhor".
- **A marcação só existe com a regra do usuário.** Se ele disser o critério
  da casa dele ("marque quem tem PRODES depois de 2019", "embargo que toque o
  perímetro"), a planilha ganha uma coluna com o nome dessa regra e "sim",
  "não" ou "sem dado". A regra é dele: não sugira qual usar, não diga qual é
  a exigida por norma ou por comprador, e não chame o resultado de aprovado
  ou reprovado.
- **Célula vazia não é zero.** Seção que a ferramenta não conseguiu gerar
  fica vazia, com o motivo na coluna "Seções que não saíram". Não escreva
  "nenhum" onde não houve leitura.
- **Não é certidão.** Diga "pelas bases públicas, na data de cada uma". Os
  termos de embargo vêm sem nome e sem documento de pessoa: não procure, não
  deduza nem escreva quem é o embargado.
- **Sobreposição é geometria, não situação jurídica.** Dizer que 22 ha
  sobrepõem uma unidade de conservação é um fato de mapa; o que isso
  significa depende da categoria da unidade, da data e do órgão.
- Diferença entre o declarado no CAR e o observado é uma subtração. Não
  interprete.
- **Solo** é estimativa de um mapa mundial de 250 m, não medição.
- Se o usuário pedir a conclusão ("quais posso comprar?", "quem está
  irregular?"), diga que a planilha não conclui, entregue os fatos e devolva
  a decisão a ele e ao responsável técnico ou jurídico.

## O que precisa estar disponível

- **Conector ClaudIA Sat**, com `dossie_pdf`. Sem ele, avise e pare.
- **A lista de imóveis**: números de CAR (o perímetro vem da consulta pública
  do SICAR), fazendas salvas na conta (`listar_fazendas`) ou arquivos de
  perímetro. Só imóveis no Brasil.
- **Ambiente que roda Python** (só a biblioteca padrão) para a planilha. Sem
  ele, veja "Sem ambiente de código".

## Antes de chamar: as perguntas (numa mensagem só)

1. **A lista**: os CARs, um por linha, ou a planilha de onde vêm. Confira o
   formato de cada número (UF, 7 dígitos, 32 caracteres) antes de gastar
   consulta; número fora do formato volta para o usuário.
2. **A área de cada imóvel**, se ele tiver (na planilha dele, ou pela skill
   `consulta-car`). É o que permite fazer a conta da franquia antes.
3. **Se há um critério da casa** para marcar na planilha. Se não houver, a
   planilha sai sem coluna de critério. Não proponha um.
4. Se ele quiser que constem nas fichas: quem pediu e o responsável técnico.

## A conta da franquia e o tamanho do lote

Cada dossiê consome, da franquia de hectares do usuário, a área do imóvel, e
leva de 20 segundos a pouco mais de 1 minuto.

- Com as áreas em mãos: some, diga o total em hectares e quantos imóveis
  cabem no que a conta libera por dia e por mês.
- Sem as áreas: diga que só vai saber a área de cada imóvel depois do dossiê
  dele, e vá informando o acumulado.
- **Faça lotes de até 5 imóveis.** Depois de cada lote, diga o acumulado em
  hectares, quantos faltam e pergunte se segue. Lista grande se faz em vários
  dias.
- Se a ferramenta recusar por limite, repita o motivo como ela disse, pare e
  ofereça continuar depois: os que já foram feitos estão salvos na pasta.

## Fluxo de trabalho (siga nesta ordem)

1. **Grave a lista** em `lista.txt`, um imóvel por linha (o CAR, ou o nome
   que vai identificar a fazenda salva ou o arquivo).
2. **Para cada imóvel do lote**, chame `dossie_pdf` com `car` (sozinho: não
   envie perímetro junto), ou `fazenda`, ou `geometria`; mais
   `nome_propriedade`, `solicitante` e `responsavel` quando informados. As
   chamadas de um lote podem ir juntas.
3. **Grave a resposta de cada um** num arquivo de texto na pasta
   `respostas/`, com a resposta **como veio**, da primeira linha ("DOSSIÊ DE
   USO E OCUPAÇÃO DO SOLO pronto: ...") até antes do bloco "Arquivo:", e no
   alto duas linhas suas:
   ```
   IMOVEL: <o CAR, ou o nome, igual ao da lista>
   FICHA: <o nome com que o PDF foi salvo>
   ```
   Não resuma, não reescreva e não redigite número de memória.
4. **Entregue a ficha** de cada imóvel (o link do PDF) logo que sair. Os
   links **expiram em 1 hora**: diga para baixar na hora e guardar com o nome
   que está na linha `FICHA`.
5. **Confira**:
   `python scripts/triagem.py --pasta respostas --lista lista.txt --conferir`.
   Ele mostra cada imóvel lido, a área, as seções lidas, o que não saiu e o
   que falta da lista. Se um número não bater com a resposta, corrija o
   arquivo.
6. **Monte a planilha** (a cada lote, ou no fim):
   `python scripts/triagem.py --pasta respostas --lista lista.txt --saida saida`,
   com um `--criterio "coluna operador número"` para cada regra que o usuário
   informou (`--colunas` lista as colunas que servem).
7. **Escreva na conversa** o conteúdo de `triagem.md` e entregue
   `triagem.csv`.
8. **Repita os avisos**: imóvel com seção que "NÃO SAIU DESTA VEZ" (ofereça
   gerar de novo depois, e só esse), "NÃO INCLUÍDO NESTA EMISSÃO",
   "OBSERVAÇÃO QUE ESTÁ NO DOCUMENTO" e bases de restrição não lidas.

## Critério do usuário: como escrever

`--criterio "prodes_2020_ha > 0"` · `--criterio "embargos_n >= 1"` ·
`--criterio "ti_ha > 0"` · `--criterio "aberta_depois_2008_ha > 5"`

Operadores: `>`, `>=`, `<`, `<=`, `=`. A coluna sai com o nome "Critério do
usuário: ..." e os valores "sim", "não" ou "sem dado" (a seção daquele número
não saiu: não dá para dizer que não). Ao relatar, diga "pelo critério que
você informou, N de M imóveis", nunca "N reprovados".

## Sem ambiente de código

Faça as chamadas do mesmo jeito e monte à mão a tabela com as colunas
principais do `references/colunas.md`, copiando cada número da linha do
resumo de onde ele vem. Com mais de 10 imóveis, diga que a planilha completa
precisa de um ambiente que rode Python.

## O que a skill não faz

- Não dá parecer, laudo, nota de risco nem certidão, e não classifica imóvel.
- Não consulta matrícula, CCIR, ITR, cadastros de pessoas, listas de trabalho
  análogo à escravidão, licenças nem autos de infração fora das bases do
  dossiê.
- Não cobre o que o dossiê não cobre: territórios quilombolas,
  assentamentos, florestas públicas, embargos de órgãos estaduais e a zona de
  amortecimento das unidades de conservação.
- Não confere se o CAR é do produtor informado nem se o imóvel é o da nota
  fiscal, do contrato ou da lavoura financiada.
- Não gera de novo um dossiê para "melhorar" um resultado.
- Para um imóvel só, use a skill `dossie-uso-ocupacao-solo`; para o quadro de
  crédito, `relatorio-credito-rural`.

## Sigilo das fontes

Cite as fontes como estão na última página de cada ficha em PDF. Sobre como o
dado é processado, a única frase é: processado pelas ferramentas da
comunidade agrônomo10X (OagronomIA).
