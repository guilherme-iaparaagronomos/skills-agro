# Estatística experimental

Skill que faz a **análise estatística de um ensaio agronômico** a partir da
planilha das parcelas: análise de variância, pressupostos, comparação de
médias com letras (ou regressão, quando o fator é dose) e relatório em PDF.

**O que ela faz:**

- **Diagnóstico** antes de qualquer teste: o papel de cada coluna, o
  delineamento que encontrou, o quadro da análise de variância, os
  pressupostos (Shapiro-Wilk, Bartlett, Levene, resíduos discrepantes) e o que
  cada transformação faria.
- **Delineamentos**: inteiramente casualizado, blocos casualizados, fatorial
  duplo (com desdobramento da interação) e parcela subdividida em blocos.
- **Testes de médias**: Tukey, t (LSD), SNK, Duncan, Scott-Knott e Dunnett.
- **Regressão polinomial** para um fator quantitativo, com os graus testados.
- **Saídas**: quadro da ANOVA, CV, médias com letras, gráfico, tabelas em CSV
  e relatório em PDF.

Ela **não escolhe** o teste, a significância, a transformação nem o grau da
regressão: mostra os números e pergunta. E não recomenda cultivar, dose nem
manejo: descreve o resultado estatístico.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue.
- `scripts/analise.py` — a linha de comando (diagnóstico, análise e exemplo).
- `scripts/leitura.py` — lê CSV, TSV, TXT e XLSX.
- `scripts/delineamento.py` — o palpite do papel das colunas e a conferência
  da estrutura do ensaio.
- `scripts/modelo.py` — o quadro da análise de variância, os resíduos, os
  pressupostos, as transformações e a regressão.
- `scripts/medias.py` — os testes de médias e as letras.
- `scripts/ensaio.py` — a sequência do diagnóstico e da análise, e os avisos.
- `scripts/saidas.py` — CSV, gráficos e o relatório em PDF.
- `scripts/sintetico.py` — os ensaios inventados do exemplo e dos testes.
- `references/metodo.md` — cada conta, contra o que foi conferida e os limites.

Cada script tem um teste embutido: `python scripts/<nome>.py`. O exemplo
completo: `python scripts/analise.py --demo`.

## Instalar

Baixe [`estatistica-experimental.zip`](../../../releases/latest/download/estatistica-experimental.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Como foi testada

Com dados inventados. O quadro da análise de variância, os resíduos, o
desdobramento e a regressão foram conferidos, número por número, contra
`scipy` e `statsmodels`; Tukey e Dunnett, contra as funções do `scipy`; e
todos os testes de médias por simulação de 40 mil ensaios sem diferença
verdadeira. O Scott-Knott não tinha outra implementação na máquina para
comparar: foi conferido só pela simulação. A skill ainda não foi usada num
ensaio de verdade nem comparada com os programas de estatística mais usados
na agronomia. Os detalhes estão em `references/metodo.md`.

## Avisos

O relatório descreve o resultado da análise no teste e na significância que
o usuário escolheu. A interpretação agronômica e a recomendação são do
responsável técnico. Achou um resultado diferente do seu programa de
estatística? Abra uma [issue](../../../issues/new/choose) com a planilha.
