# O quadro cronológico: formato fixo

Escreva sempre estes blocos, nesta ordem, com estes títulos. Bloco sem dado
fica, com a frase "não consultado" ou "a ferramenta não devolveu", e o
motivo. Não acrescente bloco de conclusão, parecer ou recomendação.

```
# Evidências de evento na lavoura — [nome da propriedade]

Emitido em [data]. Quadro de fatos: não é laudo pericial e não substitui a
vistoria.

## 1. Identificação
- Área: [fazenda salva ou arquivo], [município/UF se a ferramenta disse], [ha].
- Talhões consultados: [nomes e ha].
- Cultura: [cultura], segundo o usuário.
- Plantio: [data], segundo o usuário.

## 2. O evento informado
- Tipo: [seca | chuva em excesso | geada | granizo | vento | fogo | outro], segundo o usuário.
- Data: [dia, ou de ... a ...], segundo o usuário.
- O que as ferramentas medem deste tipo de evento: [uma linha, da tabela da skill].

## 3. Chuva
Janela do evento ([de] a [até], [N] dias):
- Total: [mm]. Média histórica (1991–2020) do mesmo período: [mm]. Diferença: [%].
- Dias de chuva: [N]. Maior chuva: [mm] em [data].
- Dias sem dado: [N]. Dias com confiança baixa: [N] ([datas]).

Safra, mês a mês:
| Mês | Chuva | Média histórica | Diferença |

Veranicos na janela da safra ([régua que a ferramenta escreveu]):
| De | Até | Dias | Chuva no período |

[Se o usuário enviou o pluviômetro da fazenda:]
Registro do pluviômetro da fazenda, informado pelo usuário:
| Data | mm |

## 4. Temperatura  [só em geada, frio ou calor]
- No dia do evento ([data]): mínima [°C], máxima [°C].
- Menor mínima da janela: [°C] em [data]. Maior máxima: [°C] em [data].
Dado modelado para a região; não é termômetro no talhão.

## 5. Índice de vegetação antes e depois
Índice: [NDVI | NDWI]. Média de cada talhão em cada imagem.
| Talhão | Última imagem antes | Valor | Primeira imagem depois | Valor | Diferença | Dias entre as duas |

Imagens durante o evento: [datas e valores, ou "nenhuma imagem limpa"].
[Se a queda coincide com o evento:] Coincidir no tempo não prova a causa: a
queda do índice pode ser falta de água, mas também colheita, dessecação, fim
de ciclo, praga, doença ou nuvem que sobrou na imagem.

## 6. Cronologia
| Data | O que há nessa data | De onde vem |
[uma linha por data, em ordem: o que o usuário informou; começo e fim de cada
veranico; os dias de chuva que importam para o evento; cada imagem, com o
índice de cada talhão]

## 7. Arquivos
- Gráfico do índice com a chuva: [link]
- Laudo da imagem de [data], antes do evento: [link]
- Laudo da imagem de [data], depois do evento: [link]
Os links expiram em 1 hora.

## 8. O que este quadro não mostra
- A causa da queda do índice e o tamanho da perda.
- [o que as ferramentas não medem deste tipo de evento]
- A chuva é a média da área por pluviômetros e satélites; a do talhão pode ter sido outra.
- Cultura e data de plantio são as informadas pelo usuário.
- [avisos das ferramentas, com as palavras delas]

## 9. Fontes
[as linhas do bloco "FONTES DOS DADOS" de cada ferramenta usada (índice, imagens, chuva e temperatura), inteiras e como vieram, sem repetir]
```

## Exemplo (dados inventados)

```
# Evidências de evento na lavoura — Fazenda Exemplo

Emitido em 10/06/2025. Quadro de fatos: não é laudo pericial e não substitui a
vistoria.

## 1. Identificação
- Área: fazenda salva "Fazenda Exemplo", 86,4 ha.
- Talhões consultados: Sede (41,0 ha) e Baixada (45,4 ha).
- Cultura: milho segunda safra, segundo o usuário.
- Plantio: 20/02/2025, segundo o usuário.

## 2. O evento informado
- Tipo: seca, segundo o usuário.
- Data: de 05/04/2025 a 12/05/2025, segundo o usuário.
- O que as ferramentas medem deste tipo de evento: chuva dia a dia, total ao
  lado da média histórica, veranicos com datas e o índice antes e depois.

## 3. Chuva
Janela do evento (21/03/2025 a 27/05/2025, 68 dias):
- Total: 31,4 mm. Média histórica (1991–2020) do mesmo período: 148,0 mm. Diferença: −79%.
- Dias de chuva: 6. Maior chuva: 11,2 mm em 02/04/2025.
- Dias sem dado: 0. Dias com confiança baixa: 4 (de 28/04 a 01/05/2025).

Safra, mês a mês:
| Mês | Chuva | Média histórica | Diferença |
|---|---|---|---|
| fev/2025 | 198,3 mm | 205,0 mm | −3% |
| mar/2025 | 122,6 mm | 168,0 mm | −27% |
| abr/2025 | 14,9 mm | 86,0 mm | −83% |
| mai/2025 | 9,8 mm | 57,0 mm | −83% |

Veranicos na janela da safra (7 ou mais dias seguidos com menos de 2 mm por dia):
| De | Até | Dias | Chuva no período |
|---|---|---|---|
| 12/03/2025 | 19/03/2025 | 8 | 1,2 mm |
| 04/04/2025 | 14/05/2025 | 41 | 3,1 mm |

## 5. Índice de vegetação antes e depois
Índice: NDVI. Média de cada talhão em cada imagem.
| Talhão | Última imagem antes | Valor | Primeira imagem depois | Valor | Diferença | Dias entre as duas |
|---|---|---|---|---|---|---|
| Sede | 03/04/2025 | 0,74 | 18/05/2025 | 0,41 | −0,33 | 45 |
| Baixada | 03/04/2025 | 0,71 | 18/05/2025 | 0,52 | −0,19 | 45 |

Imagens durante o evento: 13/04 (Sede 0,72; Baixada 0,70), 28/04 (0,61; 0,66), 08/05 (0,48; 0,57).
Coincidir no tempo não prova a causa: a queda do índice pode ser falta de
água, mas também colheita, dessecação, fim de ciclo, praga, doença ou nuvem
que sobrou na imagem.

## 6. Cronologia
| Data | O que há nessa data | De onde vem |
|---|---|---|
| 20/02/2025 | Plantio | usuário |
| 12/03 a 19/03/2025 | Veranico de 8 dias, 1,2 mm | curva com chuva |
| 02/04/2025 | Chuva de 11,2 mm, a maior da janela | histórico de chuva |
| 03/04/2025 | Imagem: Sede 0,74; Baixada 0,71 | curva com chuva |
| 04/04/2025 | Começo do veranico de 41 dias | curva com chuva |
| 05/04/2025 | Início do evento | usuário |
| 13/04/2025 | Imagem: Sede 0,72; Baixada 0,70 | curva com chuva |
| 28/04/2025 | Imagem: Sede 0,61; Baixada 0,66 | curva com chuva |
| 08/05/2025 | Imagem: Sede 0,48; Baixada 0,57 | curva com chuva |
| 12/05/2025 | Fim do evento | usuário |
| 14/05/2025 | Fim do veranico de 41 dias | curva com chuva |
| 18/05/2025 | Imagem: Sede 0,41; Baixada 0,52 | curva com chuva |
| 22/05/2025 | Aviso de sinistro | usuário |

## 7. Arquivos
- Gráfico do índice com a chuva: [link]
- Laudo da imagem de 03/04/2025, antes do evento: [link]
- Laudo da imagem de 18/05/2025, depois do evento: [link]
Os links expiram em 1 hora.

## 8. O que este quadro não mostra
- A causa da queda do índice e o tamanho da perda.
- A umidade do solo e o déficit hídrico.
- A chuva é a média da área por pluviômetros e satélites; a do talhão pode ter sido outra.
- Cultura e data de plantio são as informadas pelo usuário.
- Em 4 dias da janela (28/04 a 01/05/2025) a ferramenta marcou a chuva com confiança baixa.

## 9. Fontes
- Índice: Copernicus Sentinel-2 L2A. Contains modified Copernicus Sentinel data (2025) — contém dados modificados do Copernicus Sentinel.
- Chuva: MERGE (CPTEC/INPE) e CHIRPS v3 (Climate Hazards Center, Universidade da Califórnia em Santa Bárbara).
- Temperatura, umidade e vento: dados de satélite modelados — comunidade agrônomo10X (OagronomIA).
```

No exemplo o bloco 4 não aparece porque o evento não é de temperatura. Em
geada, frio ou calor ele entra, entre o 3 e o 5.
