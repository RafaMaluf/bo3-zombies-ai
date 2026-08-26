# Krono

Assistente pessoal para **Call of Duty: Black Ops III Zombies**. A aplicação
usa uma base local de guias como fonte canônica e seleciona screenshots
associadas aos passos recuperados. A versão atual não pesquisa a internet
durante a conversa.

## O que mudou na versão remasterizada

- recuperação híbrida: BM25 local + embeddings Voyage com Reciprocal Rank Fusion;
- índice semântico versionado e validado contra o conteúdo atual da base;
- fallback automático para BM25, com circuit breaker quando a API de embeddings falha;
- uma única chamada de IA por pergunta;
- base carregada uma vez na inicialização;
- chunks por seção de Markdown, com corte de relevância e dominância por guia;
- até três guias nomeados podem ser respondidos juntos; acima disso, o usuário
  escolhe quais deseja para evitar respostas enormes;
- instruções de idioma impedem que verbos e nomes genéricos em inglês sejam
  misturados em respostas em português;
- imagens registradas por IDs estáveis, com legenda e vínculo à seção;
- thumbnails WebP gerados sob demanda e armazenados em cache;
- validação automática de índices, documentos e imagens;
- frontend responsivo com seleção de mapa, fontes e galeria;
- testes, lint, Docker e CI.

## Base atual

- Shadows of Evil
- The Giant
- Der Eisendrache
- Zetsubou No Shima
- Gorod Krovi
- Revelations
- Nacht der Untoten
- Verrückt
- Shi No Numa
- Kino der Toten
- Ascension
- Shangri-La
- Moon
- Origins

O comando de validação informa a contagem exata de documentos, chunks e
imagens:

```bash
python -m scripts.validate_kb
```

## Rodando localmente

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
```

No Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Preencha `GROQ_API_KEY` no `.env`. Para habilitar a busca semântica híbrida,
preencha também `VOYAGE_API_KEY` e mantenha `EMBEDDING_PROVIDER=voyage`.
Depois execute:

```bash
python -m uvicorn app.main:app --reload
```

Acesse [http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/).

## Modelo

O padrão é `openai/gpt-oss-120b` no Groq, com raciocínio baixo para privilegiar
velocidade. Ele pode ser trocado sem alteração de código:

```dotenv
GROQ_MODEL=openai/gpt-oss-120b
```

O antigo `llama-3.3-70b-versatile` está programado para sair do Groq em
16 de agosto de 2026. O GPT-OSS 120B foi escolhido por estar em produção,
ter bom desempenho multilíngue, contexto de 131 mil tokens e suporte a saída
JSON. No plano gratuito, o limite publicado é de 30 requisições por minuto,
1.000 por dia, 8 mil tokens por minuto e 200 mil por dia.

Referências: [deprecações](https://console.groq.com/docs/deprecations),
[GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b) e
[limites](https://console.groq.com/docs/rate-limits).

## Busca híbrida

O texto dos 602 chunks é convertido previamente em vetores de 1.024 dimensões
com `voyage-4-large`. O índice gerado fica em `embeddings/` e é carregado uma
única vez na inicialização. Em cada pergunta, apenas a consulta é enviada para
a Voyage; os vetores dos documentos não são recalculados.

BM25 e similaridade vetorial não são alternativas exclusivas. O Krono combina
os dois rankings com Reciprocal Rank Fusion: BM25 preserva nomes exatos,
siglas, números de passos e termos próprios de Zombies, enquanto os embeddings
recuperam paráfrases e perguntas semanticamente equivalentes.

Se a Voyage estiver indisponível, a conversa continua com BM25. Um circuit
breaker evita repetir chamadas lentas durante a falha. Para reconstruir o
índice depois de alterar a base:

```bash
python -m scripts.build_embedding_index
```

O manifesto contém o modelo, a dimensão, os IDs dos chunks e um hash da base.
Um índice ausente, corrompido, criado com outro modelo ou desatualizado é
rejeitado na inicialização; nesse caso, o servidor permanece disponível em
modo BM25.

## Imagens

As imagens dos guias são publicadas em object storage com chaves imutáveis
baseadas no SHA-256 do arquivo original. O manifesto versionado em
`assets/image-manifest.json` relaciona cada imagem da base às variantes
`original`, `full` e `thumb`; nenhuma credencial de storage é enviada ao
frontend.

O pipeline de geração, upload idempotente, verificação, backup e migração de
provedor está documentado em [docs/assets.md](docs/assets.md).

## Qualidade

```bash
python -m ruff check app scripts tests
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
python -m scripts.validate_kb
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_retrieval --suite evals/chronicles_queries.json
python -m scripts.evaluate_retrieval --hybrid
python -m scripts.evaluate_retrieval --hybrid --suite evals/chronicles_queries.json
```

Para gerar previamente os thumbnails das imagens:

```bash
python -m scripts.prewarm_thumbnails
```

Com a aplicação em execução, valide os endpoints e respostas reais:

```bash
python -m scripts.smoke_api
python -m scripts.smoke_api --live-chat
```

Os thumbnails e relatórios ficam em `.cache/` e não são versionados.

## Importando novos mapas

O pipeline em `scripts.ingest_map` baixa os guias definidos em um manifesto,
converte as imagens para WebP, remove duplicatas, registra a procedência e
valida o mapa antes de alterar `maps/`.

```bash
python -m scripts.ingest_map ingestion/manifests/nacht_der_untoten.json --dry-run
```

Veja [docs/ingestion.md](docs/ingestion.md) para o formato do manifesto e
[docs/evaluations.md](docs/evaluations.md) para adicionar os casos de busca.

## Docker

```bash
docker compose up --build
```

O Compose lê a chave do arquivo `.env` e publica a aplicação em
`http://127.0.0.1:8000`.

## Como a resposta é montada

1. O mapa explícito ou o contexto ativo restringe a busca.
2. BM25 e embeddings classificam as seções por sinais complementares.
3. Reciprocal Rank Fusion combina os rankings e um corte relativo remove
   resultados frouxos.
4. Quando um documento vence claramente, outros guias não são misturados.
   Se a pergunta nomear explicitamente dois ou três guias, a busca distribui
   os chunks entre eles.
5. Somente os chunks e imagens aprovados entram no prompt.
6. O modelo devolve texto e IDs de imagens.
7. O servidor descarta qualquer ID que não tenha sido oferecido.

Veja [docs/knowledge-base.md](docs/knowledge-base.md) antes de adicionar um
novo mapa.

## Pesquisa externa

É possível acrescentar pesquisa na internet. O modelo padrão suporta uma
ferramenta de busca, mas ela não está habilitada nesta versão. A direção
recomendada é um fallback híbrido:

1. responder primeiro com a base local;
2. pesquisar apenas quando a base for insuficiente ou quando o usuário pedir;
3. exibir URL e distinguir claramente conteúdo local de conteúdo externo;
4. nunca incorporar silenciosamente o resultado pesquisado à base canônica.

Pesquisar sempre tornaria a resposta menos reproduzível e aumentaria o risco
de misturar BO1, BO3, versões modificadas e informações incorretas. Consulte a
[documentação de ferramentas do Groq](https://console.groq.com/docs/tool-use/built-in-tools).

## Decisão de arquitetura

A estrutura atual é adequada ao tamanho e ao tipo do projeto, não uma solução
universal. Markdown continua sendo a fonte canônica e o índice vetorial é um
artefato derivado e reproduzível. Como são apenas 602 chunks, os vetores ficam
em um arquivo binário local: adicionar Pinecone, Qdrant ou outro banco vetorial
traria infraestrutura sem benefício prático neste estágio.

Os limites conhecidos são:

- recuperação semântica depende da Voyage para vetorizar novas consultas, mas
  possui fallback lexical;
- a qualidade dos chunks depende da estrutura dos guias importados;
- fatos rígidos como versão do mapa, modo e quantidade de jogadores deveriam
  evoluir para metadados estruturados;
- o mapa ativo tem prioridade para evitar que nomes de áreas sejam confundidos
  com outros mapas;
- a antiga dominância de um único documento era frágil para perguntas com
  vários objetivos; o caso explícito de até três guias agora é tratado.

Antes de trocar modelos, pesos ou adicionar reranking, a mudança deve superar
as duas suítes de avaliação versionadas. Isso evita aumentar a complexidade
com base apenas em exemplos isolados.

## Configuração

Além de `GROQ_API_KEY` e `GROQ_MODEL`, a busca híbrida usa:

- `EMBEDDING_PROVIDER` — use `voyage` para habilitar embeddings;
- `VOYAGE_API_KEY` — chave usada somente no servidor;
- `VOYAGE_MODEL` — deve ser o mesmo modelo registrado no índice.

O comportamento também pode ser ajustado por:

- `MAX_RETRIEVED_CHUNKS` — quantidade máxima de chunks recuperados;
- `MAX_MULTI_DOCUMENTS` — quantidade máxima de guias em uma única resposta;
- `MAX_CONTEXT_CHARS` — tamanho máximo do contexto enviado ao modelo;
- `MAX_CANDIDATE_IMAGES` — imagens oferecidas ao modelo;
- `MAX_RESPONSE_IMAGES` — imagens devolvidas ao frontend;
- `MAX_HISTORY_MESSAGES` — mensagens anteriores mantidas no contexto;
- `ALLOWED_ORIGINS` — origens CORS permitidas.

## Licença

O código-fonte é disponibilizado sob a licença MIT. Guias, screenshots, nomes,
marcas e demais materiais de terceiros não são licenciados por este projeto e
permanecem sob os direitos de seus respectivos proprietários.
