# Contribuição

Antes de propor alterações:

1. Não compartilhe capturas ou arquivos com nomes/caminhos pessoais.
2. Execute `python -m unittest discover -s tests -v`, `python -m compileall -q Servidor` e `node --check Interface/app.js`.
3. Preserve migrações do banco SQLite e não apague arquivos reais durante testes.
4. Prefira mudanças incrementais e descreva riscos de segurança, em especial para APIs de gravação, upload e área protegida.
5. Nunca inclua credenciais, `Dados/` reais nem arquivos de mídia de terceiros.
