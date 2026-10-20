# Roadmap do Smart Library

Roteiro aprovado para as próximas versões. A prioridade é preservar biblioteca, segurança e dados antes de ampliar o escopo. Novos recursos serão testados antes do lançamento.

## v1.0.16 — Estabilidade e organização (concluída)
- Escaneamento tolerante a erros: mantém registros se uma unidade desconectar ou uma pasta não puder ser lida.
- Revalidação de acesso a arquivos privados e bloqueio remoto da unidade C:.
- Backup automático diário consistente do SQLite e configurações, com retenção de sete cópias.
- Testes de regressão para banco, erros de varredura e permissões.

## v1.0.17 — Biblioteca inteligente (implementada; validar no Windows)
- Reconhecimento local de séries, temporadas, episódios e ano de filmes.
- Visões por Séries / Coleções, Por pastas e Todos os arquivos.
- Busca opcional de informações e capa via Steam, iTunes, MusicBrainz e TMDb (com chave própria).
- Identificação em lote de até 25 itens públicos sem capa; aplica automaticamente apenas correspondência de alta confiança.
- Preserva capas manuais e biblioteca anterior. Refinar automaticamente nomes ambíguos e álbuns musicais futuramente.

## v1.0.18 — Reprodução avançada (pendente)
- Histórico e continuar assistindo; próximo episódio; trilhas de áudio e legendas.
- Conversão/transcodificação sob demanda por FFmpeg para celulares e TVs.
- Testes de codecs e desempenho com acesso remoto na rede local.

## v1.0.19 — Interface, mobile e desempenho (pendente)
- Layout responsivo e experiência instalável PWA.
- Favoritos, coleções próprias, playlists e fila de reprodução.
- Escaneamento incremental e melhorias para bibliotecas muito grandes.

## Futuro / revisões transversais
- Arquivos idênticos e semelhantes: refinamento de duplicados com exclusão sempre supervisionada.
- Diagnóstico e monitoramento do Serviço Windows.
- Auditoria de autenticação, operações de leitura/escrita, CSRF, upload/download e exposição LAN antes de recomendar publicação/uso em redes não confiáveis.
- Teste em Windows 11 com disco desconectado, caminhos da Steam/Epic, contas de serviço e TV/celular.
