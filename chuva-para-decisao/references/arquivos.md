# Os arquivos que o script lê

O script não chama ferramenta nenhuma. Ele lê arquivos de texto com o que a
`clima_historico` e a `contexto_chuva` devolveram. Quem grava esses arquivos é
a IA, a partir das respostas das ferramentas.

Se o ambiente guarda a resposta da ferramenta num arquivo, passe o arquivo
como veio: o script entende o texto original. Se não guarda, transcreva do
jeito resumido abaixo, que é mais curto e é conferido do mesmo jeito.

Regras gerais:

- Copie os números como a ferramenta escreveu: vírgula decimal (`12,4`) e
  ponto de milhar (`1.621,5`). Número com ponto e três casas sem vírgula
  (`1.234`) é recusado, porque não dá para saber se é mil ou um vírgula dois.
- Linha que começa com `#` é comentário.
- Os exemplos abaixo têm números inventados.

## 1. Tabela mensal (`--mensal`)

Uma chamada de `clima_historico` com `escala` = `mes`.

No alto, as três linhas da ferramenta, como vieram:

```
Chuva — Fazenda X (01/07/1998 a 30/06/2025, 9862 dias):
RESUMO: total 43.250,4 mm · média histórica (1991–2020) do mesmo período: 44.100,0 mm → -2% · confiança alta
TEMPERATURA: graus-dia 135900.5 (base 10°C) · médias das mínimas 18.9°C e das máximas 28.6°C
```

Depois, uma linha por mês. Vale a linha da ferramenta inteira:

```
1998-10: 180,4 mm (média 148,2 mm → +22%) · temp média 20.2–29.4°C · graus-dia 458.7
```

ou a linha resumida, com o mês, a chuva e, se for usar graus-dia, os
graus-dia:

```
1998-10 180,4 458.7
```

No jeito resumido, as linhas do alto podem ser trocadas por:

```
local: Fazenda X
periodo: 01/07/1998 a 30/06/2025
total: 43.250,4
gdd_total: 135900.5
base_gdd: 10
normal: 262,3 215,9 251,4 117,4 33,4 17,4 8,6 20,3 52,2 148,2 273,6 270,9
```

- `total` é o da linha `RESUMO`; `gdd_total` e `base_gdd` são os da linha
  `TEMPERATURA`. São eles que conferem a transcrição: sem `total`, a soma dos
  meses não é conferida e o relato avisa.
- `normal` é opcional: as 12 médias 1991–2020 que a ferramenta mostra ao lado
  de cada mês, de janeiro a dezembro. Entram na tabela e no gráfico.
- Mês "SEM DADO" fica `1998-10 SEM DADO`.
- Ou todos os meses têm graus-dia, ou nenhum.

O que o script confere: meses contínuos e sem repetição; soma dos meses contra
o `total`; soma dos graus-dia contra o `gdd_total`; período contra o primeiro
e o último mês. Mês cortado numa ponta do período fica fora das contas.

## 2. Janela dia a dia (`--janela` e `--janela-fim`)

Uma chamada de `clima_historico` com `escala` = `dia` para cada ano, sempre com
o mesmo dia e mês de início e de fim. Todos os anos no mesmo arquivo, um bloco
depois do outro.

Cada bloco começa pelas três linhas da ferramenta, **como vieram**:

```
Chuva — Fazenda X (01/10/2024 a 30/11/2024, 61 dias):
RESUMO: total 412,6 mm · média histórica (1991–2020) do mesmo período: 421,8 mm → -2% · confiança alta
AGRO: 31 dia(s) de chuva · veranico máx 9 dia(s) (03/10/2024 a 11/10/2024) · maior chuva 52,2 mm em 26/10/2024
```

Depois, os milímetros de cada dia, na ordem, em linhas `mm:`. Uma linha por
mês ou por dezena de dias ajuda a não pular dia:

```
mm: 0,0 0,0 0,0 0,0 5,1 14,2 5,3 0,6 8,1 0,9
mm: 5,6 23,4 6,1 0,8 3,2 4,7 7,5 3,3 1,8 2,0
...
```

- Dia "SEM DADO" vira `SD`.
- No lugar das linhas `mm:` valem as linhas de dia da ferramenta inteiras
  (`2024-10-01: chuva 0,0 mm · temp 24–38°C · ...`). Não misture os dois jeitos
  no mesmo bloco.
- A linha `AVISOS:` da ferramenta, se vier, pode ser copiada junto: o relato a
  repete.

O que o script confere em cada ano:

1. o número de valores é o número de dias da primeira linha;
2. a soma fecha com o `total` da linha `RESUMO`;
3. o dia da "maior chuva" tem o valor informado, e nenhum dia passa dele;
4. os dias do "veranico máx" informado têm todos até 2 mm, e o dia antes e o
   dia depois têm chuva;
5. o número de dias SEM DADO é o que a ferramenta informou.

E no conjunto: a mesma janela em todos os anos, sem ano repetido, sem ano
faltando no meio (a não ser com `--anos-salteados`), o mesmo local e pelo
menos 5 anos.

Se a conferência recusar, o erro diz o ano e, quando dá, o dia. Releia a
resposta da ferramenta daquele ano e corrija. Não mude valor para a soma
fechar.

## 3. Ano em curso (`--contexto`)

O texto da `contexto_chuva`, como veio. O script copia as frases para o relato
e para o PDF sem mexer, e para na linha "COMO RESPONDER", que é instrução para
a IA e não vai para o usuário.

## 4. O que sai na pasta `--saida`

| Arquivo | O que tem |
|---|---|
| `relato.md` | as frases do relato, bloco a bloco, e os avisos |
| `relatorio.pdf` | as tabelas, os gráficos e o relato |
| `calendario_mensal.csv` | uma linha por mês do calendário |
| `anos_agricolas.csv` | total, posição, mês das águas e graus-dia de cada ano agrícola |
| `janela_decendios.csv` | uma linha por decêndio, com o total de cada ano |
| `janela_por_ano.csv` | uma linha por ano: totais da ferramenta, sequências secas, início das águas |
| `fim_das_aguas_por_ano.csv` | a data do fim das águas e os dias do início ao fim |
| `calendario.png`, `janela_decendios.png`, `janela_dias.png` | os gráficos |
| `analise.json` | todos os números |

Os CSV usam ponto e vírgula e vírgula decimal.
