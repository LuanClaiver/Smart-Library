# Segurança

- **Somente LAN confiável**: a API usa HTTP sem TLS e não deve ser exposta à internet pública.
- Visitantes: leitura e download apenas de arquivos catalogados não protegidos.
- Admin: alteração/transferência de arquivos somente com login; operações de exclusão têm confirmação.
- **Protegidos**: a senha Admin deve ser digitada novamente a cada entrada; uma autorização temporária é encerrada ao sair.
- A unidade `C:` não é publicada em sessões por IP remoto. O auxiliar Explorador usa apenas loopback e abre IDs catalogados validados pela API.
- Antes de publicar o código, verifique se `Dados/`, `*.db`, `*.log`, `*.env` ou caminhos pessoais não estão presentes no commit.
- O aplicativo não criptografa arquivos originais do Windows. Proteção de visualização não substitui ACLs nem BitLocker.

Para avisar sobre vulnerabilidades, prefira contato privado com o mantenedor do repositório em vez de incluir credenciais ou dados privados em issues públicas.
