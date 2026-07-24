# Estrutura da base de conhecimento

Cada mapa ocupa uma pasta em `maps/<map_id>/`.

```text
maps/
  der_eisendrache/
    index.json
    general.md
    main_ee.md
    images/
      main_ee/
        teleporter_ready.jpg
```

## `index.json`

Campos obrigatórios:

- `map_id`: identificador estável em `snake_case`;
- `display_name`: nome exibido;
- `aliases`: nomes e abreviações usados pelos jogadores;
- `summary`: resumo do mapa;
- `files`: todos os Markdown pesquisáveis.

Cada arquivo precisa de `path`, `category` e `summary`. Um Markdown que não
estiver no índice faz a validação falhar. Um caminho indexado que não existir
também faz a validação falhar.

## Markdown

Use um `#` para o título e `##` para seções recuperáveis:

```markdown
# Rocket Shield

## part 1 - first courtyard

Description and exact locations.

Related images:
- images/shield/part_1_location_a.jpg
- images/shield/part_1_location_b.jpg
```

As imagens devem ficar na mesma pasta do mapa, dentro de `images/`. Não use
espaços nos nomes de arquivo. Formatos aceitos:

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`
- `.gif`

Não é necessário repetir uma galeria completa no fim do documento. O loader
mantém compatibilidade com as galerias legadas, mas imagens próximas à seção
produzem respostas mais precisas.

## Validação obrigatória

Depois de importar ou editar conteúdo:

```bash
python -m scripts.validate_kb
python -m pytest
```

O validador detecta:

- índices inválidos;
- documentos ausentes ou não indexados;
- caminhos que escapam da pasta do mapa;
- referências de imagem quebradas;
- imagens órfãs;
- IDs duplicados.

## Fontes

Como o projeto é pessoal, screenshots públicas podem ser armazenadas
localmente. Ainda assim, registre a URL de origem durante a importação para
facilitar correções e substituir imagens no futuro.
