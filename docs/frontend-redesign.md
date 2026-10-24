# Caderno de campo — frontend local

Direção visual aprovada: superfícies de carvão e tons quentes, títulos serifados,
instruções e fotografias apresentadas como notas de campo. A navegação escolhida
é uma gaveta recolhida tanto no desktop quanto no celular.

## Integração

- O histórico ocupa um `dialog` lateral nativo: foco contido no painel, Escape
  para fechar, clique no fundo para dispensar e retorno ao botão de abertura.
- Nova conversa e os títulos ficam na gaveta. Renomear/excluir ficam em menus
  por conversa; o menu do cabeçalho também permite editar a conversa atual.
- PDF pertence ao menu da conversa. O exportador existente continua separado,
  usando a prévia branca para impressão e sem carregar bibliotecas de PDF.
- O mapa aparece discretamente quando identificado. Não há seletor permanente,
  inventário de guias, contadores de imagens ou indicador de normalidade da API.
  Problemas de conexão/configuração continuam visíveis.
- A identificação do mapa continua pela mensagem. Se necessário, os botões de
  clarificação seguem a ordem do catálogo `/maps`, que acompanha os mapas do jogo.
  Novas clarificações guardam opções e pergunta original no IndexedDB, permitindo
  retomar a escolha depois de recarregar. O catálogo carrega antes do histórico.
- Rápido/Completo usam um menu compacto; escopo, geração e persistência do modo
  permanecem iguais. O menu fica indisponível durante uma requisição.
- As imagens mantêm todos os grupos recebidos. Referências numéricas substituem
  nomes técnicos visíveis. Os metadados originais ficam no texto alternativo.
  Ampliação permite navegar dentro do grupo por botões ou setas do teclado.
- O desktop apresenta instruções ao lado das imagens. No celular elas seguem
  em sequência. O acompanhamento recebe a mesma linguagem visual, preservando
  ações, roteiro, progresso, correções e explicações completas.
- O andamento real e o cancelamento permanecem. Removida a animação decorativa.
- A altura usa `visualViewport` quando disponível, para acomodar teclados móveis.
  O acompanhamento não foca automaticamente o campo em dispositivos de toque.

Não há novos serviços, fontes externas, frameworks, dependências de produção,
mudanças de API, limpeza de conversas, push ou publicação. PWA/desktop continuam
como próximas etapas independentes.

## Validação

- 21 testes frontend: IndexedDB/continuidade, restauração das escolhas de mapa,
  limites e teclado da galeria e abertura da gaveta após escritas pendentes.
- Sintaxe de todos os scripts e `git diff --check`.
- Navegador local: conversa salva com nove imagens, gaveta, menu de renomear,
  Rápido/Completo e persistência após reload, navegação das fotos, pergunta sem
  mapa com as 14 opções ordenadas, acompanhamento salvo e prévia de PDF pronta.
- Inspeção responsiva em 390 e 320 px. Isso não substitui testar teclado,
  impressão e interação num celular físico nem medir o uso junto do BO3.

O backend de geração não mudou; não é uma nova comparação de latência/qualidade
dos modelos. A suíte Python anterior não foi repetida por esta alteração visual.
