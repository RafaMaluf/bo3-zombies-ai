# Teclado mobile e continuidade — 29/10/2026

## Incidente

No Safari/PWA do iPhone, focar o compositor deslocava a interface para fora da
área visível. Na conversa exportada, após uma resposta sobre as pinturas do arco
do lobo, “onde eu pego a flecha?” recebeu as instruções e fotos do arco elétrico.

## Correções

- O documento mantém sua geometria; a aplicação acompanha altura e deslocamento
  do `visualViewport`, tanto em `resize` quanto em `scroll`. Atualizações são
  agrupadas por frame, sem polling, sem forçar a rolagem global e sem alterar a
  posição de leitura da conversa. Zoom por gesto continua disponível.
- Campos editáveis usam no mínimo 16px; cabeçalho respeita a área segura. O
  compositor limita a própria altura ao espaço visível. Toque não recebe foco
  automático após uma resposta ou mudança de mapa. A gaveta também acompanha a
  área visível. Cache do PWA e referências dos arquivos passam para v3.
- Uma continuação curta e implícita de um único objetivo confirmado restringe a
  busca ao guia anterior, antes da seleção dos trechos. O filtro vale para ranking
  lexical e semântico. Não acrescenta uma chamada ao modelo para esse caso.
- Objetivos explícitos novos têm prioridade. Pedidos de outros itens, famílias,
  comparações e histórico com várias fontes continuam no fluxo de resolução.
  Uma resposta sem fontes não ressuscita silenciosamente um assunto antigo.
- Perguntas pontuais não são obrigadas a citar o primeiro resultado da busca.
  Essa regra anterior também podia trocar a flecha inicial pela etapa do altar
  final, mesmo dentro do guia correto. A seleção do trecho usa a pergunta e seu
  contexto; procedimentos ordenados mantêm a cobertura obrigatória das etapas.
- Histórico serve para interpretar referências, não como evidência factual.
  Fontes válidas, corpo não vazio e JSON continuam sendo verificados.

## Verificação e limites

- Regressões offline em português, inglês e espanhol, Rápido/Completo, fotos,
  troca de objetivo, famílias e ranking com um guia concorrente acima do correto.
- Contrato pontual verificado em direto/resumo/detalhado; fontes desconhecidas,
  resposta sem blocos e blocos sem fonte continuam sendo rejeitados.
- 26 testes de frontend: inclui teclado abrindo/fechando, deslocamento sem resize,
  rotação, retorno à página, zoom e foco automático. São eventos simulados, não
  um teclado físico de iPhone.
- Teste real local com GPT-OSS-120B/OpenRouter: após as pinturas, a pergunta sobre
  a flecha retornou a parede quebrada à esquerda da escada, com a foto da etapa
  inicial do guia do lobo. A repetição com histórico resumido do PDF também
  retornou esse local e uma foto. O replay HTTP em `/chat`, com o índice Voyage
  ativo, também retornou a etapa inicial e sua foto (14,7 s nesta execução).
  A miniatura indicada também respondeu HTTP 200 (`image/webp`), com TLS validado.
  Não utilizou a cota Groq de produção.
- Suíte Python final: **427 testes aprovados**. Frontend: **26 testes aprovados**.
  Ruff, mypy e sintaxe JavaScript sem erros.

Controle visual do Firefox indisponível nesta sessão: a ferramenta interrompeu
o acesso por falta de suporte à política de URLs desse navegador. **Ainda falta
validar abertura/fechamento do teclado num iPhone real, em Safari e PWA.**
Testes de viewport e uma execução correta do modelo não comprovam ausência de
bugs do WebKit nem correção factual de todas as futuras respostas. Estas mudanças
foram publicadas na `main` até `dd895f8`. O retorno do aparelho confirmou que
conversas existentes melhoraram, mas revelou a falha de boas-vindas abaixo.

## Aceite no aparelho

Em Safari e no PWA instalado, abrir uma resposta longa, rolar até um ponto
intermediário e tocar no campo: cabeçalho e compositor devem continuar na área
visível, sem sobreposição à barra de status. Digitar, fechar o teclado e repetir;
a resposta não deve reabrir o teclado sozinha. Conferir também rotação da tela,
campo do acompanhamento e renomeação de conversa. No chat Rápido, repetir
pinturas do lobo → localização da flecha; a foto deve ser a da parede no subsolo.

## Retorno do iPhone: conversa nova

O estado vazio tinha um problema adicional de flexbox: com 214px disponíveis na
área central, as boas-vindas ocupavam 381px e sobrepunham o compositor. Reproduzido
em navegador headless com o HTML, CSS e JavaScript reais, mantendo o layout
viewport e reduzindo apenas o visual viewport.

- Boas-vindas podem encolher e rolam dentro de seus próprios limites. A área
  central impede pintura sobre o compositor.
- Uma consulta à altura do contêiner compacta as boas-vindas em pouco espaço:
  retira a logo e reduz título e espaçamento. Os atalhos continuam acessíveis.
  A apresentação normal retorna quando há espaço novamente.
- Cache do PWA passa a v4; somente a referência do CSS muda. Não há nova lógica
  de teclado nem alteração na geração das respostas.
- Regressão reproduzida antes da correção: 5 dos 7 cenários Chromium falhavam.
  Depois: **14 testes de layout aprovados em Chromium e WebKit**, incluindo a
  troca de uma conversa existente por uma nova, viewport deslocado, campo com
  várias linhas, fechamento do teclado simulado e larguras 320/393/430px,
  paisagem e desktop. O teste verifica inclusive qual elemento recebe o toque
  no centro do campo, detectando a sobreposição.
- Os 26 testes unitários frontend e o teste de entrega dos arquivos PWA passam.
  Playwright é dependência apenas de desenvolvimento; o CI executa as regressões
  nos dois motores. Não há chamadas de modelo nesses testes.

Executar com `npm run test:layout`, após
`npx playwright-core install chromium webkit`. Para os dois motores, definir
`KRONO_LAYOUT_ENGINES=chromium,webkit`. Um Chromium já instalado pode ser usado
com `KRONO_CHROMIUM_PATH`. Isso valida layout nos motores, **não substitui a
abertura do teclado no iPhone físico**.
