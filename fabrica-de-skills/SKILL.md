---
name: fabrica-de-skills
description: >-
  Conduz a criação de uma skill própria para uma rotina do usuário, da
  conversa ao pacote instalado. Entende a rotina, mostra que peça do acervo da
  comunidade agrônomo10X resolve cada passo (os quatro conectores, com cada
  ferramenta e para que serve, e as skills da casa), ajuda a decidir entre um
  roteiro que chama ferramentas, uma skill com script ou um roteiro para o
  QGIS, escreve o SKILL.md e os arquivos, testa com um caso real, confere a
  pasta e gera o zip. As decisões técnicas da rotina são do usuário: a skill
  pergunta, não inventa. Acione com "quero criar uma skill", "transformar
  minha rotina em skill", "como faço uma skill", "automatizar esse processo
  que eu repito", "fábrica de skills", "empacotar minha skill" ou quando o
  usuário descrever um trabalho repetido e pedir que a IA passe a fazer
  sempre do mesmo jeito.
---

# Fábrica de skills

Uma skill é uma pasta que ensina a IA a fazer um trabalho do mesmo jeito todas
as vezes. Dentro dela há um `SKILL.md` (o roteiro que a IA segue), às vezes
scripts (o que precisa de conta exata ou gera arquivo) e material de consulta.
A IA decide usar a skill pela `description` do cabeçalho.

Esta skill conduz o usuário na criação da skill dele. O trabalho tem sete
passos, e você não pula nenhum.

## Regras

- **A rotina é do usuário.** Limite, classe, dose, fórmula, unidade, formato
  de relatório, o que pode e o que não pode: tudo isso ele informa. O que ele
  não disse, você pergunta. Não preencha lacuna técnica com suposição.
- **A decisão técnica fica com quem responde por ela.** Skill que gera
  recomendação agronômica deixa claro de onde vem a regra (o manual, a tabela
  do usuário) e devolve a decisão ao responsável técnico. Skill que reúne
  dados de bases públicas ou de satélite relata fatos com a fonte.
- **Uma skill, um trabalho.** Rotina comprida vira duas skills que se
  encadeiam (a saída de uma é a entrada da outra).
- **Se o acervo já resolve, não refaça.** Se uma skill da casa faz o trabalho
  inteiro, diga qual e pare. Se uma ferramenta do conector entrega o resultado
  pronto, a skill nova chama a ferramenta em vez de montar outra versão.
- **Nada de dado de cliente nem segredo dentro da skill.** Exemplos são
  inventados. Senha, chave e token não entram em arquivo nenhum.
- **Script simples e fechado.** Sem acesso à rede e sem executar outro
  programa, a não ser que a rotina exija e o usuário saiba. Prefira as
  bibliotecas que o ambiente de código da IA já tem.
- **Não copie skill de terceiros** nem trecho de material com direito de
  autor. As skills da casa podem servir de molde de estrutura.

## Passo 1 — Entender a rotina

Pergunte, numa mensagem só, o que ainda não souber:

1. O que você faz hoje, passo a passo, do começo ao fim?
2. O que entra? (arquivos e formatos, de onde vêm, o que varia de um caso
   para o outro)
3. O que sai? (documento, mapa, planilha, arquivo para máquina; para quem)
4. Quais decisões são suas no meio do caminho? (escolha de método, de limite,
   de classe)
5. Onde costuma dar erro ou retrabalho?
6. Tem um caso real, já feito à mão, para servir de gabarito?

Se ele tiver um exemplo pronto (o relatório, a planilha final), peça. O
exemplo vale mais que a descrição.

## Passo 2 — Casar cada passo com o acervo

Leia `references/acervo.md`: os quatro conectores da comunidade, com cada
ferramenta e para que serve, e as skills da casa. Depois:

- confirme o que está no ar na conta dele: com o conector de conteúdo ligado,
  `listar_skills` mostra as skills publicadas e `skill_conteudo` devolve o
  SKILL.md e os arquivos de uma delas, para ler como molde;
- monte a tabela **passo da rotina → peça que resolve**, com uma destas
  respostas em cada linha: ferramenta de um conector (qual), skill da casa
  (qual), script novo, a própria IA lendo e escrevendo, ou "fica com você";
- mostre a tabela ao usuário e acerte com ele antes de escrever qualquer
  arquivo.

Passo que depende de conector que ele não tem ligado: diga qual conector é e
que sem ele aquele passo não roda.

## Passo 3 — Escolher o tipo de skill

| Tipo | Quando | O que tem na pasta |
|---|---|---|
| Roteiro que chama ferramentas | os dados vêm dos conectores e o trabalho é pedir, conferir e relatar | `SKILL.md` e `references/` |
| Com script | há conta exata, leitura de arquivo, mapa, planilha ou PDF para gerar | `SKILL.md`, `scripts/`, `references/` |
| Roteiro para o QGIS | o trabalho acontece no projeto aberto do usuário, pela ClaudIA QGIS | `SKILL.md` com a ordem das chamadas e o que conferir |
| Mista | parte vem do conector e parte é processada por script | os três |

Diga qual tipo você recomenda e por quê, numa frase. Na dúvida entre roteiro
e script: se o resultado precisa ser igual toda vez, até a última casa, é
script.

## Passo 4 — Escrever

Siga o molde de `references/modelo.md`. O que não pode faltar:

- **Cabeçalho**: `name` (minúsculas, números e hífen; igual ao nome da pasta)
  e `description` (o que a skill faz, o que entra, o que sai, o que ela NÃO
  faz e as frases que o usuário diria para acioná-la, entre aspas; até 1.024
  caracteres, com a primeira frase curta).
- **Regras** que valem para tudo, logo no começo.
- **O que precisa estar disponível**: conectores, arquivos, bibliotecas.
- **As perguntas obrigatórias**: o que a IA tem de perguntar antes de rodar,
  porque a decisão é do usuário.
- **O fluxo numerado**, com o nome exato de cada ferramenta ou o comando de
  cada script.
- **O que a skill não faz** e quando parar e devolver ao usuário.

Para skill com script:

- um script de entrada com ajuda (`--help`) e um exemplo inventado embutido
  (`--demo`), para qualquer pessoa ver funcionando sem dado nenhum;
- um autoteste em cada módulo (rodar o arquivo sem argumentos confere as
  contas);
- duas etapas quando houver escolha técnica: primeiro um diagnóstico que
  mostra o dado e as opções, depois a execução, que só roda com a escolha
  informada;
- mensagens de recusa claras: coluna que falta, unidade que não bate, arquivo
  vazio. Recusar com explicação é melhor que calcular errado.

Escreva o `README.md` para a pessoa que vai instalar: o que a skill faz, o
que precisa, como instalar, como foi testada e os avisos.

## Passo 5 — Testar

Uma skill só está pronta depois destes cinco testes. Faça com o usuário e
conte o resultado de cada um:

1. **Exemplo inventado**: o `--demo` roda e o resultado faz sentido.
2. **Caso real**: o gabarito do passo 1. Compare o que a skill produz com o
   que ele fez à mão, número por número. Diferença se explica ou se conserta.
3. **Casos ruins**: arquivo errado, coluna faltando, valor fora do possível.
   A skill recusa e diz o motivo.
4. **Olhar o resultado**: abra o PDF, o mapa ou a planilha. Texto cortado,
   legenda em cima de outra coisa e unidade errada só aparecem olhando.
5. **Reler o SKILL.md como se fosse outra IA**, sem esta conversa: dá para
   seguir? Tudo o que ficou combinado só de boca vai para o texto.

Diga com clareza o que foi testado com dado real e o que foi só com dado
inventado. Isso vai para o README.

## Passo 6 — Conferir e empacotar

```
python scripts/validar.py <pasta da skill>
python scripts/validar.py <pasta da skill> --empacotar
```

O primeiro comando confere o cabeçalho, os arquivos citados, o tamanho, erro
de sintaxe nos scripts, segredo esquecido e acesso à rede. Erro impede o
pacote; aviso se lê e se decide. O segundo gera `<nome>.zip` ao lado da
pasta, com a pasta dentro, do jeito que a IA espera. Entregue o zip ao
usuário.

## Passo 7 — Instalar e usar

- No Claude: Configurações → Capacidades → Skills, e envie o zip. Em outras
  IAs que aceitam skills ou instruções de projeto, use a mesma pasta.
- Peça ao usuário para abrir uma conversa nova e fazer um pedido de verdade,
  com as palavras que ele usaria. Se a skill não for acionada, o conserto é
  na `description`.
- Depois do primeiro uso real, volte ao passo 5 com o que apareceu.

## O que esta skill não faz

- Não publica no catálogo da comunidade: lá ficam as skills da casa. A skill
  criada aqui é do usuário, para a IA dele.
- Não garante que a lista de `references/acervo.md` esteja em dia: as
  ferramentas mudam. O que vale é o que o conector mostra na conta dele.
- Não escreve a regra técnica no lugar do usuário, nem valida a agronomia da
  rotina dele.
- Não instala nada na máquina nem na conta do usuário.
