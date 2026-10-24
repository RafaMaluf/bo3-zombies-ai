# Multi-guias: proposta para alinhamento

Status: proposta alinhada com o usuário em 21/10/2026. A implementação local
e seus limites estão em [source-planning.md](source-planning.md). Este arquivo
preserva a discussão de arquitetura; a validação real final permanece pendente.

## Problemas observados

- O usuário recebeu uma pergunta sobre qual guia usar ao pedir o escudo de
  Gorod Krovi. A base contém tanto o guia principal quanto uma referência à
  melhoria; isso não deve obrigar o jogador a escolher arquivos internos.
- Um único arquivo pode misturar objetivos. O guia de Der Eisendrache reúne
  energia, Pack-a-Punch, teletransporte e jump pads. Expandir o arquivo inteiro
  não equivale a responder completamente ao objetivo pedido.
- Os registros de Pack-a-Punch revelaram que contar marcadores de listas é
  uma aproximação inadequada para validar a cobertura de uma explicação.

## Fluxo proposto

1. Resolver mapa, objetivo e nível de detalhe, preservando o contexto ativo.
2. Consultar o catálogo de todo o mapa: objetivos, seções, pré-requisitos e
   referências. A unidade de seleção passa a ser o objetivo/seção, não o arquivo.
3. Montar um plano de fontes para o objetivo e suas dependências, distinguindo
   requisitos obrigatórios, condicionais e equipamentos apenas recomendados.
4. Recuperar os trechos completos pertinentes, seguir referências e remover
   duplicatas. Um arquivo de referência pode apontar ao guia canônico sem
   introduzir uma escolha artificial ou repetir o mesmo procedimento.
5. Ordenar as ações por dependência e execução, preservando a associação entre
   instruções, fontes e grupos de imagens. O mesmo plano serve ao resumo, à
   explicação completa e ao acompanhamento de uma fase por vez.
6. Validar estrutura JSON, fontes permitidas, cobertura dos passos definidos
   no plano e ordem. Diferenciar erros de formato de falhas de conteúdo. A
   quantidade de bullets ou palavras não é uma prova de completude factual.

## Alcance e desempenho

Todos os guias do mapa ficam disponíveis para consulta. Isso não exige enviar
todo o conteúdo em toda pergunta. Usar catálogo e relações locais para buscar
os trechos necessários, ampliando a seleção quando faltarem dependências.
Manter limites explícitos de contexto, chamadas e ciclos de expansão. Se um
plano não couber, dividir por fases de maneira visível, sem cortar conteúdo
silenciosamente nem tratar o número de arquivos como ambiguidade do pedido.

Começar pelas relações revisadas dos objetivos principais (EE e Pack-a-Punch),
com referências a seções e imagens existentes. Referências inferidas precisam
ser verificadas na base: o modelo não deve inventar dependências. Validar
referências quebradas, ciclos e ordem no carregamento da base.

## Exemplos e critérios de aceite propostos

- “Escudo de Gorod”: usar o procedimento base e suas peças. Não perguntar qual
  arquivo consultar nem incluir a melhoria como se fosse obrigatória.
- “Melhoria do escudo”: seguir a referência ao procedimento completo e
  contextualizar a necessidade do escudo base.
- “EE de Origins”: integrar os pré-requisitos documentados de outros guias nas
  fases correspondentes, com imagens corretas e sem repetir etapas.
- “Pack-a-Punch”: incluir energia e acesso necessários; excluir objetivos
  independentes só porque compartilham o arquivo.
- Perguntar quando faltar uma escolha de jogo que altere a resposta, como mapa
  desconhecido ou variante não resolvida. Não usar a quantidade de fontes como
  motivo para pedir ao jogador que escolha um guia.
- Resumido ou completo continua sendo uma decisão de apresentação; a seleção
  de fontes deve cobrir o objetivo em ambos os casos.

## Antes da implementação

Corrigir a rejeição indevida das respostas de Pack-a-Punch e reproduzir os
casos relatados com e sem histórico. Verificar também a sequência de seleção
de mapa mostrada na captura: a imagem isolada não prova que a pergunta sobre
o mapa foi enviada depois de Der Eisendrache estar ativo.

Frontend, persistência do estado da partida e publicação permanecem fora desta
etapa. Alinhar esta proposta com o usuário antes de implementar multi-guias.
