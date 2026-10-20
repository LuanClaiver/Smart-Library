# Smart Library v1.0.17 — Biblioteca Inteligente

## Identificação local (sem acesso à internet)

- Reconhecimento de episódios em nomes `S01E02`, `S02 E05` e `1x03`, incluindo série, temporada e episódio. Reconhece também temporadas por pastas `Temporada 01` ou `Season 01`.
- Extrai ano do nome de arquivos de filmes.
- Agrupa filmes em coleções com base nas pastas e em informações de metadados confirmadas, e séries pelo título identificado. **Não move, renomeia nem apaga arquivos.**
- Migração do SQLite: acrescenta `metadata_json`, `series_title`, `season`, `episode`, `collection_name`, `media_year`. É idempotente e preserva customizações anteriores.
- A detecção de séries ocorre ao escanear fontes Automático que contenham nomes de episódios, ou em fontes cadastradas como Séries. Categorias alteradas manualmente continuam prevalecendo.

## Busca de informações e capas (Admin, opcional)

- **Editar → Buscar informações:** pesquisa por nome de jogo, música, filme ou série. Confirme visualmente o resultado antes de aplicar.
- Fontes gratuitas: iTunes Search API para filmes/séries/músicas; Steam para jogos; MusicBrainz para músicas.
- Fonte opcional TMDb: configure `Dados/metadados.json` (copie `Dados/metadados.exemplo.json` e informe `tmdb_api_key` da API v3). TMDb é uma base independente; exige credencial própria.
- **Identificar capas (até 25):** consulta apenas itens públicos, disponíveis, sem capa nem metadados; só associa correspondências muito altas (>=94%) e mantém capas manuais. É executado em segundo plano, por acionamento do Admin, não durante a varredura.
- Não pesquisa itens classificados como Protegidos ou localizados na pasta privada. Não revela senha/chave TMDb nas APIs.
- Apenas o nome pesquisado é enviado ao provedor externo, não o conteúdo do arquivo. Requer internet no PC servidor; pode haver limites de acesso ou nenhuma correspondência.
- Todos os resultados encontrados exigem revisão de direitos e licenças das imagens antes de compartilhamento ou distribuição.

## Compatibilidade e limitações

- Funciona em modo interativo e Serviço Windows, porta 3000, sem dependências Python adicionais.
- A identificação é uma ajuda, não garante resultados corretos para itens com nomes genéricos, arquivos com nomes alterados ou coleções pouco conhecidas.
- Álbuns musicais completos, fontes avançadas e classificação contextual ficarão para refinamentos futuros.
- Os dados reais permanecem sob `Dados`. Não publicar `Dados/metadados.json` nem banco, miniaturas ou senhas.
- Serviço Windows, consultas externas e comportamento visual devem ser validados em um computador Windows 11.
