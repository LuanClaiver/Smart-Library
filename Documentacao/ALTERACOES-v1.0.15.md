# Notas da versão 1.0.15

- Corrigida exibição de opções de executável/status conforme categoria Jogos.
- Pesquisa sob demanda de imagens por Wikimedia Commons ou Steam (apenas Jogos); link externo para buscador geral.
- Área Protegidos: login Admin + senha novamente a cada acesso; autorização adicional independente expira após 10 minutos e é invalidada ao sair.
- Unidade do sistema C: indisponível ao navegar pelo IP da rede. O bloqueio está nas rotas do backend, não só nos botões.
- `Abrir Smart Library.bat` passa a iniciar `Servidor/local_agent.py` quando o serviço estiver rodando. O agente somente escuta 127.0.0.1:38765 e recupera caminhos validados junto à API; não aceita caminhos arbitrários do navegador.
- Transferências seguem na aba original, conforme solicitado.
- Subpasta `GitHub` com fonte e documentação sem arquivos pessoais.

## Cuidados ao atualizar

O nome do serviço permanece `SmartLibraryLocal` e a porta da API continua **3000**. Não crie um segundo serviço; a opção 2 do Gerenciador atualiza o serviço existente para a pasta nova.

Pare o serviço anterior, faça backup de `Dados`, extraia em pasta nova e só depois copie os dados. A senha Admin não está no repositório GitHub e pode precisar de novo login após atualizar devido à divisão da sessão Admin e Protegidos.

O botão Local só estará presente no navegador `http://localhost:3000` ou `http://127.0.0.1:3000` do PC. Mesmo com o serviço ativo, execute `Abrir Smart Library.bat` no usuário conectado para iniciar o Auxiliar Local; sem ele, o botão informará a instrução de inicialização.

Nenhum arquivo original deve ser apagado apenas por atualizar o catálogo.
