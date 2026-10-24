# Contrato de completude entre guias

Estado: arquitetura aprovada para implementação local. Sem alteração de frontend,
push ou deploy. A fonte factual continua sendo o Markdown de cada mapa.

## Responsabilidades

O índice derivado identifica seções, grupos de procedimentos e relações com
evidência. O resolvedor calcula requisitos transitivos e ordem. O modelo escolhe
o objetivo dentro do contexto e explica o plano; não pode remover requisitos
conhecidos para caber num resumo. A apresentação preserva as imagens das fontes.

Cada relação declara consumidor, fornecedor, tipo (`requires`, `recommended`
ou `illustrates`), trecho literal de evidência e condição textual, quando existe.
Uma relação pode apontar para um grupo completo de seções. Exemplo: a exigência
de quatro cajados melhorados expande construção, melhorias específicas,
preparação compartilhada e conclusão da melhoria. O grupo não implica que toda
seção de qualquer arquivo seja obrigatória.

Condições solo/co-op são preservadas e explicadas; desconhecer jogadores não
autoriza escolher silenciosamente uma variante. Progresso concluído só pode ser
usado quando explicitamente declarado pelo usuário. Não é inferido por uma
resposta anterior. O estado persistente da partida permanece uma etapa futura.

## Invariantes

1. Fontes e relações pertencem ao mesmo mapa e existem no catálogo canônico.
2. Evidências precisam corresponder ao texto da seção citada. Validade textual
   não substitui a revisão semântica da relação.
3. Requisitos transitivos conhecidos não podem ser omitidos, mesmo que o modelo
   entregue um JSON válido. Recomendações permanecem identificadas como opcionais.
4. Não existem ciclos obrigatórios. A ordem das fases principais é preservada.
5. Fase guiada inclui somente seus requisitos; não acrescenta fases futuras.
6. Resumo e completo têm o mesmo escopo obrigatório. O resumo agrupa detalhes;
   completo recebe as seções integrais, condições, locais e imagens.
7. Cada imagem continua vinculada à seção de origem. Deduplicação não remove
   locais alternativos diferentes. Fontes repetidas são explicadas uma vez.
8. Mudanças nas fontes invalidam relações derivadas afetadas por fingerprint.
   Índices ausentes, desatualizados ou inconsistentes não passam por verificados.
9. Cobertura conhecida é explícita: um grupo revisado não certifica todos os
   objetivos do mapa. Descobertas pelo modelo não se tornam fatos revisados.
10. Limites de capacidade e delegações essenciais a guias ausentes geram erro
    explícito. Lacunas textuais registradas na revisão não podem ser preenchidas
    como fatos inventados; o grafo não certifica a completude do conteúdo gerado.

## Ampliação de 22/10/2026

Revisão mapa a mapa em [relationship-review.md](relationship-review.md), com
inventário em `assets/guide-review.json`. Relações condicionais propagam sua
condição transitivamente; alternativas não viram uma lista conjunta obrigatória.
Um requisito também alcançado por caminho incondicional não fica limitado a
uma rota opcional. Resumos só agrupam passos com a mesma condição e mantêm uma
âncora externa válida para o grupo.

Referências ilustrativas podem usar recortes literais validados do documento
original, sem copiar upgrades/etapas alheias ou imagens fora do trecho revisado.
O índice registra o fingerprint do pai, limites exatos e imagens permitidas.
Arquivos de redirecionamento satisfazem o objetivo por sua receita canônica.
Enciclopédias compostas continuam passando por seleção de objetivo quando necessário.
Cobertura de relações, seleção do objetivo e completude do texto gerado são
responsabilidades diferentes; a validação do índice não certifica a resposta final.

## Implementação incremental

O resolvedor é genérico. O catálogo inclui todos os mapas; relações revisadas
ficam em dados versionados, sem `if mapa == ...` no algoritmo. Começamos pela
matriz de regressão dos procedimentos complexos e disponibilizamos o mecanismo
de leitura completa para descobrir relações de objetivos ainda não revisados.
As relações novas precisam de evidência e validação; revisão humana dos casos
de referência continua necessária.

As relações revisadas expandem o plano antes da geração. Para fontes não
cobertas, o planejamento consulta texto completo em lotes, em vez de depender
somente de títulos ou de prefixos truncados. A execução reutiliza o índice local;
não faz uma reconstrução de toda a base em cada mensagem.

## Critérios de aceite

Casos independentes verificam conjuntos obrigatórios, exclusões, precedência,
imagens e variantes. Testes simulados verificam o mecanismo sem custo. Somente
a validação real confirma a integração com o modelo, com registro de custo e
tempo. Falhas semânticas permanecem visíveis, mesmo com todos os testes de JSON
aprovados. O índice não é uma promessa de infalibilidade factual.
