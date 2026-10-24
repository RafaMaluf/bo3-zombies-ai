# Respostas visuais e acompanhamento de guias

O endpoint `POST /chat` mantém `answer`, `sources` e `relevant_images` para
compatibilidade. Respostas estruturadas acrescentam `introduction` e `blocks`.
Cada bloco tem título, texto Markdown, referências aos chunks usados e imagens
daquelas seções. O frontend apresenta a introdução seguida dos blocos, sem
repetir o texto completo de `answer` ou a galeria legada.

## Responsabilidades

- `chat_service.py`: coordena recuperação, contexto, geração e apresentação;
- `guidance.py`: constrói as fases e valida a navegação explícita;
- `presentation.py`: valida referências e associa os grupos de imagens;
- `main.py`: inicializa serviços e expõe os endpoints HTTP.

O modelo escreve os blocos e referencia os IDs `[SOURCE ...]` fornecidos no
prompt. O servidor descarta referências desconhecidas e não aceita URLs de
imagem fornecidas pelo modelo. As imagens são resolvidas pela relação entre
chunk e imagem da base. Uma mesma imagem é exibida apenas uma vez na resposta.

Grupos de locais alternativos não são cortados para caber no limite. O padrão
de `MAX_BLOCK_IMAGES` é 36. Se um grupo não couber, o bloco continua com o texto
e informa que existem mais imagens. O limite de candidatas também preserva
grupos completos. `MAX_RESPONSE_IMAGES` continua valendo para a galeria legada.

As legendas existentes nem sempre descrevem o local exato. Um vínculo entre
seção e imagem não comprova que a foto A corresponde ao primeiro item de uma
lista. A interface mostra o grupo por peça/fase; a associação individual exige
curadoria explícita dos metadados.

## Guias longos

Uma pergunta ampla sobre o Easter Egg principal de um mapa cujo guia tenha
ao menos seis fases começa pelo roteiro. Perguntas pontuais continuam usando
a recuperação normal. Pedir explicitamente o guia completo mostra todas as
fases com imagens.

O documento legado de Origins contém oito passos dentro de uma única seção.
O adaptador de leitura separa preparação e passos, preservando as referências
originais das imagens. Não modifica Markdown, IDs canônicos nem o índice
semântico existente. Os outros guias usam suas seções ordenadas.

`guide_state` contém mapa, caminho do guia, fase atual, fases marcadas como
concluídas e quantidade opcional de jogadores. O servidor só aceita guias
principais existentes no mapa e índices de fases válidos.

`guide_action` aceita:

- `start`: consultar a primeira fase;
- `jump` com `guide_phase`: consultar uma fase sem concluir as anteriores;
- `complete`: marcar a fase atual e consultar a próxima;
- `overview`: mostrar o roteiro preservando a fase atual;
- `full`: mostrar o guia completo preservando o progresso;
- `stop`: deixar de usar o contexto guiado.

Perguntas de continuação não avançam o progresso. Uma consulta a outro guia
usa a busca normal e o navegador mantém o acompanhamento anterior. Trocar de
mapa ou limpar a conversa encerra esse acompanhamento.

O estado pertence à conversa aberta no navegador, não a uma sessão no
servidor. Recarregar a página ainda limpa conversa e progresso. Persistência,
estado detalhado dos equipamentos continuam planejados. A seleção de
dependências entre guias está em [source-planning.md](source-planning.md);
as fases navegáveis continuam sendo as do guia principal.

## Verificação local

```bash
python -m pytest tests/test_presentation.py tests/test_guidance.py tests/test_chat_blocks.py
python -m ruff check app scripts tests
node --check frontend/app.js
```

Os testes usam modelos simulados e não precisam de Groq ou Voyage. Para rodar
toda a suíte sem usar a Voyage configurada no `.env`, defina
`EMBEDDING_PROVIDER=none` no ambiente do processo de testes.

Casos de referência: escudo de Shadows com três grupos de três imagens;
roteiro de Origins; começar, tirar dúvida, escolher fase e marcar conclusão;
guia completo; rejeição de IDs de fonte, caminhos e fases desconhecidos.
