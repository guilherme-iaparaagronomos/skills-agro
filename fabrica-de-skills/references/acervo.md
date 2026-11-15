# O acervo da comunidade agrônomo10X

Lista gerada em 2026-11-15 a partir do que está no ar: 172 ferramentas em quatro conectores e 14 skills da casa.
Ela muda com o tempo. Antes de prometer uma peça ao usuário, confirme que ela existe na conta dele: as ferramentas aparecem na lista de
ferramentas da IA quando o conector está ligado, e `listar_skills` mostra as skills publicadas hoje.

Como ler: cada linha é o nome da ferramenta e para que ela serve. O jeito de chamar (os parâmetros) está na descrição que o próprio
conector entrega à IA; não copie parâmetro de memória para dentro de uma skill sem conferir lá.

## Conector de conteúdo da comunidade

Aulas, lives, fórum, mentorias, vagas, eventos e os catálogos de ferramentas de IA e de skills. Serve para skills que ensinam, que indicam o que estudar ou que partem de uma skill da casa.

- `recomendar_conteudo` — indica qual aula ou live assistir sobre um tema.
- `buscar_conteudo` — acha os trechos das aulas e lives que respondem a uma dúvida, com o minuto.
- `catalogo_trilhas` — lista as trilhas publicadas.
- `aula_conteudo` — resumo e transcrição de uma aula.
- `catalogo_lives` — lista as lives gravadas, com a data de cada uma.
- `live_conteudo` — descrição e transcrição de uma live.
- `buscar_forum` — busca discussões do fórum por um termo.
- `listar_mentorias` — horários livres da mentoria individual e as mentorias em grupo.
- `listar_vagas` — vagas de emprego publicadas na comunidade.
- `listar_eventos` — próximos eventos.
- `listar_ferramentas` — ferramentas de IA do catálogo da comunidade, por tema.
- `listar_skills` — skills publicadas no catálogo, por tema.
- `skill_conteudo` — conteúdo completo de uma skill do catálogo (o SKILL.md e os arquivos).

## Conector ClaudIA Sat (satélite)

Imagens, índices, mapas e documentos de uma área. A área entra como perímetro em texto (GeoJSON, KML ou WKT), como fazenda salva ou, no dossiê, pelo número do CAR. Cada chamada desconta a área consultada da franquia de hectares da conta: uma skill que chama várias vezes precisa fazer a conta e avisar antes.

- `listar_fazendas` — fazendas salvas na conta: nome, área e talhões.
- `salvar_fazenda` — guarda um perímetro com um nome, para as próximas chamadas usarem só o nome.
- `listar_talhoes` — lê o perímetro e lista a área total e os talhões.
- `mapa_talhoes` — mapa esquemático com o nome e a área de cada talhão.
- `datas_disponiveis` — datas de imagem num intervalo, com o percentual da área sem nuvem.
- `imagem_satelite` — imagem mais recente em GeoTIFF: cor real e os índices NDVI, NDRE, EVI, GNDVI, SAVI e NDWI.
- `laudo_pdf` — laudo em PDF com um mapa por índice.
- `composto_indice` — imagem composta (média ou mediana) de um índice num intervalo de datas.
- `curva_indice` — curva de um índice no tempo: da área, de um talhão ou de cada talhão (até 400 dias por chamada).
- `curva_com_chuva` — a curva do índice ao lado da chuva do mesmo período, com os veranicos marcados.
- `imagem_cbers` — imagem de detalhe, de 2 m, em cor real.
- `relevo_fazenda` — altitude, declive, classes de relevo, faixas de mecanização e curvas de nível.
- `uso_do_solo` — uso do solo de 1985 ao último mapa e o que foi aberto depois de 2008, 2019 e 2020.
- `cobertura_do_solo` — cobertura do solo recente, de 10 m, num período.
- `monitorar_cobertura` — evolução da cobertura mês a mês ou ano a ano e a mudança entre dois períodos.
- `prodes_fazenda` — supressão de vegetação nativa (PRODES) e alertas (DETER) do INPE na área.
- `restricoes_fazenda` — unidades de conservação, terras indígenas e termos de embargo que a área sobrepõe ou que ficam perto.
- `solo_textura_carbono` — estimativa de textura e carbono do solo por um mapa mundial de 250 m.
- `dossie_pdf` — dossiê de uso e ocupação do solo em PDF, pelo número do CAR, por um perímetro ou por uma fazenda salva.

## Conector ClaudIA Clima

Clima agora, histórico de chuva, previsão e janela de pulverização, por ponto, perímetro ou fazenda salva. As consultas contam na franquia de clima da conta.

- `listar_fazendas` — fazendas salvas na conta (as mesmas do conector de satélite).
- `salvar_fazenda` — guarda um perímetro com um nome (vale também no conector de satélite).
- `janela_pulverizacao` — janela de pulverização hora a hora: Delta T, vento, rajada e chuva.
- `clima_atual` — condições agora num local: temperatura, chuva, umidade e vento.
- `clima_historico` — chuva desde 1998, por dia, mês ou ano, ao lado da média histórica; dias de chuva, veranico e graus-dia.
- `contexto_chuva` — a chuva deste ano até hoje comparada com a dos outros anos.
- `previsao_tempo` — previsão diária dos próximos dias.
- `previsao_horas` — previsão hora a hora das próximas 12 horas ou do dia de amanhã.
- `previsao_dias` — previsão dos próximos 7 ou 14 dias, com a chance de chuva de cada dia.
- `video_nuvens` — vídeo das nuvens observadas pelo satélite nas últimas horas.

## Conector ClaudIA QGIS

Opera o QGIS aberto no computador do usuário, pelo plugin ClaudIA QGIS: 130 ferramentas, agrupadas abaixo pelo que fazem. Skill para o QGIS é roteiro: diz o que conferir, em que ordem chamar e o que perguntar antes de alterar o projeto.

**Conexão e diagnóstico** — saber se o QGIS está conectado, qual versão e o que está instalado.

`ping`, `diagnose`, `list_qgis_instances`, `get_qgis_info`, `get_message_log`, `list_plugins`, `get_plugin_info`, `reload_plugin`, `get_setting`, `set_setting`

**Projeto** — abrir, criar e salvar o projeto, o sistema de coordenadas e as variáveis dele.

`get_project_info`, `load_project`, `create_new_project`, `save_project`, `set_project_crs`, `get_project_variables`, `set_project_variable`

**Camadas** — listar, achar, adicionar, organizar, exportar e remover camadas; trazer os arquivos da ClaudIA Sat para o projeto.

`get_layers`, `find_layer`, `get_layer_info`, `get_layer_schema`, `get_layer_extent`, `get_layer_crs`, `set_layer_crs`, `add_vector_layer`, `add_raster_layer`, `add_web_layer`, `create_memory_layer`, `duplicate_layer`, `remove_layer`, `set_layer_visibility`, `set_layer_property`, `set_layer_order`, `get_layer_tree`, `create_layer_group`, `move_layer_to_group`, `get_active_layer`, `set_active_layer`, `export_layer`, `export_kml`, `add_layers_from_claudia_sat`

**Feições e edição** — ler, criar, alterar, apagar e selecionar feições, com o modo de edição.

`get_layer_features`, `add_features`, `update_features`, `delete_features`, `update_feature_geometry`, `start_editing`, `commit_edits`, `rollback_edits`, `get_edit_status`, `undo_edits`, `redo_edits`, `select_features`, `get_selection`, `clear_selection`, `identify_features`

**Campos, tabelas e expressões** — estatística de um campo, calculadora de campo, junções, consulta SQL e expressões do QGIS.

`get_field_statistics`, `get_unique_values`, `field_calculator`, `add_field`, `delete_field`, `rename_field`, `add_table_join`, `spatial_join`, `execute_sql`, `evaluate_expression`, `validate_expression`

**Estilo e rótulos** — simbologia de vetor e de raster, rótulos e arquivos de estilo.

`set_layer_style`, `set_simple_symbol`, `set_raster_style`, `get_layer_labeling`, `set_layer_labeling`, `apply_style_qml`, `save_style_qml`

**Mapa na tela** — enquadrar, definir a escala, marcadores, temas de mapa e, só quando o usuário pede, a imagem do mapa.

`get_canvas_extent`, `set_canvas_extent`, `get_canvas_scale`, `set_canvas_scale`, `zoom_to_layer`, `get_bookmarks`, `add_bookmark`, `remove_bookmark`, `get_map_themes`, `add_map_theme`, `remove_map_theme`, `apply_map_theme`, `render_map`, `get_canvas_screenshot`, `get_3d_screenshot`

**Raster** — metadados do raster, calculadora raster, estatística por zona e leitura de valores em pontos.

`get_raster_info`, `raster_calculator`, `zonal_statistics`, `sample_raster_values`

**Processamento** — rodar os algoritmos da caixa de ferramentas do QGIS, em lote, por modelo ou em segundo plano.

`execute_processing`, `execute_processing_batch`, `list_processing_algorithms`, `get_algorithm_help`, `get_processing_providers`, `create_processing_model`, `list_processing_models`, `run_model`, `start_processing_job`, `get_processing_job`, `cancel_processing_job`, `batch_commands`

**Layout e atlas** — montar a folha de impressão (mapa, texto, legenda, escala, imagem, tabela), o atlas e a exportação em PDF ou imagem.

`list_layouts`, `create_layout`, `get_layout_info`, `add_layout_map`, `add_layout_label`, `add_layout_legend`, `add_layout_scalebar`, `add_layout_picture`, `add_layout_table`, `configure_atlas`, `export_layout`, `export_atlas`, `remove_layout`

**Banco de dados** — conexões salvas no QGIS: listar tabelas, trazer e levar camadas, rodar SQL.

`list_connections`, `create_postgresql_connection`, `list_connection_tables`, `add_layer_from_connection`, `import_layer_to_connection`, `execute_connection_sql`

**Coordenadas** — converter coordenadas entre sistemas.

`transform_coordinates`

**Desfazer e registro** — tirar um retrato do projeto antes de mexer, voltar a ele e exportar o roteiro do que foi feito.

`create_checkpoint`, `list_checkpoints`, `restore_checkpoint`, `export_session`

**Código** — executar código PyQGIS no QGIS do usuário; é o último recurso, só com pedido explícito.

`execute_code`

## Skills da casa

Estão no catálogo da comunidade e no repositório público. Sirva-se delas de três jeitos: usar como está, encadear (a saída de uma é a entrada da outra) ou ler como molde (`skill_conteudo` devolve o SKILL.md e os arquivos).

| Skill | O que faz | Como roda |
|---|---|---|
| `5a-aproximacao-mg` | Recomendações para o uso de corretivos e fertilizantes em Minas Gerais (5ª Aproximação, CFSEMG, 1999). | script no ambiente de código da IA |
| `amostragem-georreferenciada` | Plano de amostragem georreferenciada a partir do perímetro dos talhões: pontos de coleta numerados em grade regular, em células com amostra composta ou por zona de manejo. | script no ambiente de código da IA |
| `analise-drone-qgis` | Roteiro para analisar ortomosaico de drone no QGIS pela ClaudIA QGIS — linhas de plantio, falhas, contagem de plantas e segmentação — rápido, validado e evitando os erros já vistos. | roteiro para a ClaudIA QGIS |
| `boletim-100-sp` | Recomendações de adubação e calagem para o Estado de São Paulo (Boletim 100, IAC). | script no ambiente de código da IA |
| `consulta-car` | Consulta pública do CAR (Cadastro Ambiental Rural / SICAR): a partir do número de registro, traz município, estado, latitude, longitude, área do imóvel, módulos fiscais e data de cadastro — direto da base oficial (consul | script no ambiente de código da IA |
| `conversor-geo` | Converte arquivos geográficos entre Shapefile, KML, KMZ, GeoJSON, GPX, CSV e WKT, reprojeta entre graus e UTM, mede a área em hectares, une talhões e conserta o que é seguro na geometria. | script no ambiente de código da IA |
| `dossie-uso-ocupacao-solo` | Gera o dossiê de uso e ocupação do solo de um imóvel rural em PDF pela ferramenta dossie_pdf da ClaudIA Sat e conduz a conversa: o que pedir, como chamar e como relatar só os fatos, com a fonte de cada um. | roteiro que chama as ferramentas dos conectores |
| `estatistica-experimental` | Analisa ensaios agronômicos: lê a tabela, descreve o delineamento e confere os pressupostos; com o teste e a significância que o usuário escolher, entrega a análise de variância, as médias com letras e o relatório. | script no ambiente de código da IA |
| `interpolacao-idw` | Mapas interpolados por IDW, em classes, com a área de cada classe em hectares e em % e uma apostila em PDF, para qualquer dado medido em pontos (solo, produtividade, condutividade elétrica, pragas). | script no ambiente de código da IA |
| `interpolacao-krigagem` | Interpolação por krigagem ordinária de qualquer dado medido em pontos: análise de solo, produtividade, condutividade elétrica, pragas. | script no ambiente de código da IA |
| `layout-mapa-qgis` | Monta no QGIS do usuário, pela ClaudIA QGIS, o layout final de um mapa num modelo profissional fixo, com a área de cada classe em hectares e em % na legenda, e exporta em PDF e PNG. | roteiro para a ClaudIA QGIS |
| `limpeza-monitor-produtividade` | Limpa dado denso de máquina (monitor de colheita, condutividade elétrica, sensor de dossel, altimetria) com filtros em ordem, cada um com o parâmetro e a contagem do que removeu, e entrega os pontos limpos e o relatório. | script no ambiente de código da IA |
| `relatorio-credito-rural` | Monta o quadro de fatos de uma área para análise de crédito rural pelas ferramentas da ClaudIA Sat e da ClaudIA Clima: o dossiê do imóvel em PDF, as últimas safras por satélite e a chuva dos últimos anos. | roteiro que chama as ferramentas dos conectores |
| `zonas-de-manejo` | Divide o talhão em zonas de manejo a partir das camadas que o usuário tiver (solo, produtividade, relevo, índice de vegetação), em pontos ou rasters, e entrega os polígonos, a tabela por zona e o relatório. | script no ambiente de código da IA |

## O que o acervo não tem

- Ferramenta que grave ou altere dados nas bases públicas, que envie e-mail ou mensagem, ou que leia arquivos da máquina do usuário fora do QGIS.
- Laudo de laboratório, análise de solo, matrícula, nota fiscal: esses são arquivos do usuário, que a skill lê no ambiente de código da IA.
- Recomendação agronômica pronta: as ferramentas entregam o dado; dose, produto e manejo são decisão do responsável técnico.
