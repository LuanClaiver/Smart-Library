# Alterações da versão 1.0.16

- Escaneamentos: registros de fontes desconectadas deixam de ser excluídos; itens antigos são preservados caso haja erro de acesso em uma pasta. A limpeza do catálogo ocorre apenas após uma leitura concluída sem falhas.
- Backups: pasta `Dados/Backups`, com um backup por dia, retenção dos últimos 7 e criação manual por API de Admin. Cada arquivo ZIP tem snapshot SQLite consistente (API oficial do SQLite) e configurações relevantes. Não inclui a mídia nem miniaturas.
- Segurança: endurecimento da validação de Origin e testes de autenticação/privacidade.
- Testes: regressão para discos offline, varredura parcial, arquivos removidos e backups.
- GitHub: código e documentação atualizados, sem pasta de dados pessoais; inclui o publicador BAT corrigido.

**Importante:** `Dados/Backups` pode conter hashes de senha e configuração da pasta privada, portanto mantenha esta pasta protegida, fora do GitHub e de compartilhamentos públicos. Backups não são criptografados.
