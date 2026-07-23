# Krono

Assistente pessoal para **Call of Duty: Black Ops III Zombies**. A aplicação
responde usando exclusivamente uma base local de guias e seleciona screenshots
associadas aos passos recuperados.

## O que mudou na versão remasterizada

- recuperação BM25 local antes da chamada ao modelo;
- uma única chamada de IA por pergunta;
- base carregada uma vez na inicialização;
- chunks por seção de Markdown, com corte de relevância e dominância por guia;
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

Preencha `GROQ_API_KEY` no `.env` e execute:

```bash
python -m uvicorn app.main:app --reload
```

Acesse [http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/).

## Qualidade

```bash
python -m ruff check app scripts tests
python -m pytest
python -m scripts.validate_kb
```

Para gerar previamente os thumbnails das imagens:

```bash
python -m scripts.prewarm_thumbnails
```

Os thumbnails e relatórios ficam em `.cache/` e não são versionados.

## Docker

```bash
docker compose up --build
```

O Compose lê a chave do arquivo `.env` e publica a aplicação em
`http://127.0.0.1:8000`.

## Como a resposta é montada

1. O mapa explícito ou o contexto ativo restringe a busca.
2. BM25 classifica as seções mais relevantes localmente.
3. Um corte relativo remove resultados frouxos.
4. Quando um documento vence claramente, outros guias não são misturados.
5. Somente os chunks e imagens aprovados entram no prompt.
6. O modelo devolve texto e IDs de imagens.
7. O servidor descarta qualquer ID que não tenha sido oferecido.

Veja [docs/knowledge-base.md](docs/knowledge-base.md) antes de adicionar um
novo mapa.
