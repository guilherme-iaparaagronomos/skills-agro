# Limpeza de dados de monitor de produtividade

Skill que limpa **dado denso de máquina**: pontos de monitor de colheita e de
sensores embarcados (condutividade elétrica, sensor de dossel, altimetria).
Um filtro de cada vez, com o parâmetro à vista e a contagem do que saiu.

**O que ela faz:**

- **Diagnóstico** do arquivo bruto antes de mexer: colunas, passadas,
  velocidade, enchimento da máquina no começo das passadas, largura parcial e
  o que o arquivo não tem.
- **Doze filtros em ordem**: posição, perímetro, valor impossível, bordadura,
  velocidade, variação de velocidade, largura, umidade, começo e fim de
  passada, passada curta, limites do conjunto e vizinhança.
- O corte de começo e fim de passada é **medido no próprio arquivo**.
- Avisa quando os pontos removidos estão **agrupados**, porque mancha real da
  área não é erro de máquina.
- Entrega CSV e shapefile dos pontos limpos, CSV do que saiu com o motivo e
  relatório em PDF com o mapa de antes e depois.

Ela só remove pontos: não corrige valor, não desloca o dado pelo atraso da
máquina e não interpola.

## Estrutura

- [`SKILL.md`](SKILL.md) — o playbook que a IA segue.
- `scripts/limpar.py` — a linha de comando (diagnóstico, limpeza e exemplo).
- `scripts/limpeza.py` — os perfis e a ordem dos filtros.
- `scripts/filtros.py` — passadas, medida do enchimento, limites e vizinhança.
- `scripts/leitura.py` — CSV, TXT e shapefile de pontos; palpite das colunas.
- `scripts/saidas.py` — CSV, shapefile e o relatório em PDF.
- `scripts/sintetico.py` — a colheita simulada com erros plantados, usada no
  exemplo e nos testes.
- `scripts/areas.py`, `geometria.py`, `shapefile_min.py` — leitura do
  perímetro e projeção, iguais aos das outras skills da casa.
- `references/filtros.md` — cada filtro, os padrões e as fontes.

Cada script tem um teste embutido: `python scripts/<nome>.py`. O exemplo
completo: `python scripts/limpar.py --demo`.

## Instalar

Baixe [`limpeza-monitor-produtividade.zip`](../../../releases/latest/download/limpeza-monitor-produtividade.zip)
e envie em **claude.ai → Configurações → Capacidades → Skills**.

## Avisos

A skill foi medida em colheita simulada, com erros plantados em pontos
sabidos; dado de máquina de verdade é mais sujo. Os parâmetros são decisão do
responsável técnico, e o relatório mostra todos. Achou um arquivo que ela lê
mal? Abra uma [issue](../../../issues/new/choose).
