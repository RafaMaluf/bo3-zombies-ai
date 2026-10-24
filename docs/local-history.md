# Histórico local e exportação

Implementado e validado localmente em 23/10/2026. Sem push ou deploy.

## Experiência

“Nova conversa” preserva a anterior e abre outro registro. “Conversas” permite
reabrir, renomear e excluir registros. A exclusão pede confirmação e remove as
mensagens e a partida daquela conversa; não afeta as outras. Não há exclusão
automática, fila circular, conta, sincronização ou importação.

Cada conversa tem um acompanhamento próprio. Só a conversa aberta fica ativa.
Sair do acompanhamento pausa a partida. O chat mostra o overview, as instruções
com imagens, as dúvidas e os registros legíveis das ações (“Terminei: objetivo”,
“Consultar etapa: objetivo”, correções etc.). Consultar não conclui objetivos.
Concluir o EE salva o último evento e um resumo dos objetivos registrados, sai
automaticamente do modo focado e mostra a conversa na interação mais recente.

Na retomada, o backend valida o catálogo e o estado. Uma explicação já salva para
a mesma sessão, objetivo e revisão pode ser reutilizada, sem gerar novamente o
texto da etapa. O catálogo ainda pode exigir uma chamada curta para traduzir
rótulos. A retomada não deve ser descrita como funcionamento offline.

## Armazenamento e limites

IndexedDB `krono.history.v1`, versão 1, contém:

- `conversations`: título, mapa selecionado, datas, contador, revisão, convites já
  oferecidos e estado estruturado da partida.
- `messages`: chave composta `[conversationId, seq]`, autoria, texto ou blocos,
  referências das imagens/fontes e marcação de contexto.
- `settings`: última conversa selecionada e marcador de migração.

As imagens não são copiadas para o banco. Uma resposta com blocos não duplica
todo o texto concatenado. O renderizador de Markdown é compartilhado pelo chat e
pela prévia de exportação e escapa HTML de mensagens e títulos.

A interface carrega **30 mensagens por página** e **20 títulos por página**.
Navegar por mensagens anteriores substitui a página visível; não acumula todo o
histórico no DOM. Há retorno explícito às recentes. Mensagens novas também mantêm
essa janela limitada. Imagens continuam com carregamento lazy. O contexto enviado
ao modelo usa somente as dez interações recentes selecionadas, com limite de
12.000 caracteres por item, além do estado da partida compatível com o mapa.

Atualizar a partida e acrescentar o evento da ação ocorre na mesma transação.
Essa transação termina antes de iniciar a próxima geração. Se ela falhar, o
acompanhante mantém o foco anterior, evitando que o botão Terminei conclua uma
etapa nova que ainda não foi mostrada. Se a geração falhar depois de uma gravação
bem-sucedida, a conclusão permanece salva e a repetição só refaz a explicação.

Revisões otimistas impedem uma aba desatualizada de sobrescrever a conversa.
BroadcastChannel cancela operações na aba que recebeu uma atualização do mesmo
registro e carrega o estado recente. Exclusões não permitem ressuscitar registros
por gravações tardias. Falhas de armazenamento mostram aviso; não provocam limpeza
automática. Sem IndexedDB, apenas o conteúdo recente da aba permanece utilizável,
com aviso explícito de que não foi salvo.

A partida antiga em `localStorage["krono.match.v1"]` é migrada uma única vez para
“Partida recuperada”. Criação e marcador de migração são atômicos entre abas; o
valor antigo só é removido após confirmar a gravação. Isso preserva o estado
existente, mas não recria conversas antigas que nunca foram armazenadas.

Tudo é específico do navegador/perfil/origem. Alterar host ou porta cria outro
armazenamento. Limpar os dados do site ou políticas do navegador podem remover os
registros. Não há backup garantido nem sincronização com outros dispositivos.

## PDF

“Exportar PDF” abre uma prévia local com a conversa inteira. Depois de carregar
as imagens, “Salvar como PDF” abre a impressão do navegador; selecionar o destino
PDF produz um arquivo compartilhável. A exportação não envia a conversa ao
servidor. O servidor fornece apenas as imagens pelos IDs já existentes.

A prévia tem fundo branco, layout A4, texto selecionável, imagens em duas colunas
e regras para não cortar fotografias entre páginas. Não inclui seletores e
controles do app nem legendas de arquivos nas fotografias. Carrega até quatro
imagens por vez e avisa quando uma imagem está indisponível, permitindo salvar o
restante. Usa thumbnails para controlar o tamanho do arquivo. O resultado pode
variar com o navegador e as opções da impressão; o diálogo nativo requer suporte
do navegador usado (Firefox/Chrome). Há instrução alternativa em webviews que
não implementam impressão.

A exportação inteira é processada sob demanda e pode consumir mais memória que a
leitura paginada do chat. O PDF não restaura o estado interativo; não há JSON ou
importação nesta versão.

## Validação

- **406 testes Python passaram**, sem alteração de código do backend nesta etapa.
- **17 testes Node passaram** usando fake-indexeddb, dependência somente de teste:
  atomicidade, revisões concorrentes, exclusão, paginação, reabertura, migração,
  falhas de armazenamento, ordem de gravação/geração, conclusão do acompanhamento,
  reutilização da explicação e escape de HTML.
- Ruff, sintaxe dos scripts JavaScript e `git diff --check` passaram. A CI inclui
  instalação dos pacotes de desenvolvimento Node e os testes do frontend.
- Navegador real: resposta de escudo pelo OpenRouter, nove imagens preservadas
  após recarregar, renomeação e prévia de exportação com as nove imagens.
- Respostas controladas no navegador: iniciar, pausar, trocar conversa, retomar a
  partida correta, registrar Terminei, informar várias etapas e concluir 9/9 com
  retorno automático ao chat. Nenhum texto de fixture é tratado como validação
  factual do guia.
- Paginação da interface: 85 mensagens salvas, 30 elementos visíveis; recentes
  56–85, página anterior 26–55. Atualização em segunda aba recarregou o registro
  sem sobrescrever o histórico. Layout conferido em desktop e 390 × 844.
- Prévia de impressão inspecionada visualmente. O diálogo nativo e a gravação do
  arquivo PDF não foram automatizados pelo navegador de teste.

Medição única no navegador interno desta máquina, em banco temporário separado:

| Respostas sintéticas | Texto serializado | Gravação em 20 lotes | Ler 30 mensagens | Ler lista |
| --- | --- | --- | --- | --- |
| 1.000 | 17.034.020 bytes | 174 ms | 7 ms | 1 ms |

O tamanho é JSON lógico, não espaço físico medido no SSD. A medição não inclui
geração de IA, decodificação de imagens, exportação completa ou teste de FPS com
BO3 aberto. Confirma leitura limitada; não prova impacto zero durante gameplay.

Para reproduzir testes: `npm ci`, `npm test` (Node 24 usado localmente). A página
`tests/frontend/benchmark.html` pode ser servida em um servidor de teste que
também exponha `/app/history-store.js`; não integra a interface de produção. Ela
cria e remove seu banco temporário. O botão adicional cria uma conversa marcada
como teste com 85 mensagens, somente para conferir a paginação no app de teste.
