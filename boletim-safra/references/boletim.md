# O boletim: formato fixo

Escreva sempre estes blocos, nesta ordem, com estes títulos. Bloco sem dado
fica, com "não consultado" ou "a ferramenta não devolveu", e o motivo. Não
acrescente bloco de análise, alerta ou recomendação.

```
# Boletim da safra — [nome da propriedade]
[Período: de dd/mm/aaaa a dd/mm/aaaa] · emitido em [data] · índice: [NDVI]

## 1. Imagens
- Última imagem limpa: [data] ([N] dias atrás).
- Imagem anterior: [data].
- Imagens no período do boletim: [N] ([datas]).
[Se a última tem mais de 10 dias:] O boletim descreve a lavoura de [data], não a de hoje.

## 2. Talhão a talhão
| Talhão | Área | Última imagem | Imagem anterior | Diferença | Mesma época em [ano−1] | Mesma época em [ano−2] |
[uma linha por talhão, na ordem do arquivo; em cada célula de imagem, o valor e a data]

Diferença = última imagem − imagem anterior ([N] dias entre as duas).
[Se há safras passadas:] Comparar com outros anos compara calendários: o que
estava plantado e quando. A diferença pode vir daí.

## 3. Chuva
No período ([de] a [até], [N] dias):
- Total: [mm]. Média histórica (1991–2020) do mesmo período: [mm]. Diferença: [%].
- Dias de chuva: [N]. Maior chuva: [mm] em [data].

Na safra, desde [mês/ano]:
| Mês | Chuva | Média histórica | Diferença |
[o mês em curso vai até o dia ...]
- Total: [mm]. Média histórica do mesmo período: [mm]. Diferença: [%].

## 4. Previsão
[as linhas do texto pronto da ferramenta, como vieram]

## 5. Arquivo
- Laudo da imagem de [data]: [link] (expira em 1 hora).

## 6. Avisos
[os avisos das ferramentas, com as palavras delas]
O boletim descreve o que o satélite e o registro de chuva mostram. A leitura
da lavoura e a decisão de manejo são do responsável técnico.

## 7. Fontes
- Índice e imagens: Copernicus Sentinel-2 L2A; processado pelas ferramentas da comunidade agrônomo10X (OagronomIA).
- Chuva: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).
[a linha de fonte da previsão, exatamente como a ferramenta devolveu]
```

## Exemplo (dados inventados)

```
# Boletim da safra — Fazenda Exemplo
Período: de 01/11/2025 a 15/11/2025 · emitido em 16/11/2025 · índice: NDVI

## 1. Imagens
- Última imagem limpa: 13/11/2025 (3 dias atrás).
- Imagem anterior: 08/11/2025.
- Imagens no período do boletim: 2 (08/11 e 13/11).

## 2. Talhão a talhão
| Talhão | Área | Última imagem | Imagem anterior | Diferença | Mesma época em 2024 | Mesma época em 2023 |
|---|---|---|---|---|---|---|
| Sede | 41,0 ha | 0,46 em 13/11 | 0,38 em 08/11 | +0,08 | 0,52 em 12/11/2024 | 0,31 em 14/11/2023 |
| Baixada | 45,4 ha | 0,33 em 13/11 | 0,29 em 08/11 | +0,04 | 0,49 em 12/11/2024 | sem imagem limpa |
| Pasto | 18,2 ha | 0,51 em 13/11 | 0,50 em 08/11 | +0,01 | 0,47 em 12/11/2024 | 0,44 em 14/11/2023 |

Diferença = última imagem − imagem anterior (5 dias entre as duas).
Comparar com outros anos compara calendários: o que estava plantado e quando.
A diferença pode vir daí.

## 3. Chuva
No período (01/11/2025 a 15/11/2025, 15 dias):
- Total: 96,4 mm. Média histórica (1991–2020) do mesmo período: 81,0 mm. Diferença: +19%.
- Dias de chuva: 6. Maior chuva: 34,0 mm em 04/11/2025.

Na safra, desde outubro de 2025:
| Mês | Chuva | Média histórica | Diferença |
|---|---|---|---|
| out/2025 | 121,7 mm | 118,0 mm | +3% |
| nov/2025 (até o dia 15) | 96,4 mm | 81,0 mm | +19% |
- Total: 218,1 mm. Média histórica do mesmo período: 199,0 mm. Diferença: +10%.

## 4. Previsão
[as linhas que a ferramenta devolveu, como vieram]

## 5. Arquivo
- Laudo da imagem de 13/11/2025: [link] (expira em 1 hora).

## 6. Avisos
- Os dias desde 01/11/2025 ainda podem ser revisados (dado provisório).
O boletim descreve o que o satélite e o registro de chuva mostram. A leitura
da lavoura e a decisão de manejo são do responsável técnico.

## 7. Fontes
- Índice e imagens: Copernicus Sentinel-2 L2A; processado pelas ferramentas da comunidade agrônomo10X (OagronomIA).
- Chuva: pluviômetros e satélites da comunidade agrônomo10X (OagronomIA).
[a linha de fonte da previsão, exatamente como a ferramenta devolveu]
```
