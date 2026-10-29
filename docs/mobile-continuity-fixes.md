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
  retornou esse local e uma foto. Não utilizou a cota Groq de produção.
- Ruff, mypy e sintaxe JavaScript verificados. Resultados da suíte integral e das
  verificações finais são registrados nos commits desta correção.

Controle visual do Firefox indisponível nesta sessão: a ferramenta interrompeu
o acesso por falta de suporte à política de URLs desse navegador. **Ainda falta
validar abertura/fechamento do teclado num iPhone real, em Safari e PWA.**
Testes de viewport e uma execução correta do modelo não comprovam ausência de
bugs do WebKit nem correção factual de todas as futuras respostas. Estas mudanças
são locais, sem push ou deploy nesta etapa.
