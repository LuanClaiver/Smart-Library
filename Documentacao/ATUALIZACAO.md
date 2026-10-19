# Atualização para a v1.0.15

1. **Backup:** copie toda a pasta `Dados` da instalação atual para um local seguro.
2. **Serviço:** se `SmartLibraryLocal` estiver instalado, use **Remover Servico Windows.bat** da versão antiga como administrador. A instalação antiga aponta para o caminho do Python/script antigo, então não basta mover os arquivos.
3. Extraia `Smart-Library-v1.0.15.zip` em pasta **definitiva**. Não mescle a pasta `Servidor` antiga com a nova.
4. Copie o conteúdo da pasta `Dados` antiga para a pasta `Dados` nova (sobrescrevendo somente dados, não código).
5. Execute `Gerenciar Smart Library.bat` e consulte a senha Admin e o status do serviço; instale o serviço novamente, se desejar execução em segundo plano.
6. Após mudar de 8766 para 3000, execute a opção 8 do Gerenciador como administrador. A nova regra usa profile=any e remoteip=localsubnet para funcionar nas sub-redes locais sem abrir acesso público na Internet.
7. Atualize a página com `Ctrl+F5` para carregar o CSS novo. Se o navegador ainda mostrar v1.0.9, confira se o serviço antigo foi parado e se a página atual foi servida pela nova pasta.

**Não exclua o diretório anterior antes de confirmar** que sua base e a senha Admin funcionam na v1.0.15.

## Se algo não abrir

- Verifique o Python 3.10+, a porta 3000 e `Dados/servico.log` se estiver rodando como Serviço.
- Nunca abra `Interface/index.html` como arquivo local; acesse a URL HTTP.
- Caso queira voltar, pare/remova o serviço novo e reinstale o anterior, restaurando o backup de `Dados` se houve alterações de banco.

## Filtro Steam e mídias internas de jogos

Após a primeira inicialização da v1.0.15, as imagens e os áudios sob caminhos internos da Steam/SteamLibrary/steamapps e pastas típicas de recursos dos jogos passam a ficar ocultos do catálogo. **Nenhum arquivo é apagado ou movido.** A quantidade aparece em `Locais` e o Admin pode desativar o filtro ali. Não confundir com a área protegida: o filtro é apenas de organização visual e não substitui permissões/criptografia.

A configuração fica em `Dados/filtros.json`. Não é preciso novo escaneamento para filtrar os arquivos já cadastrados; os novos também seguem a regra.

### Serviço Windows
A nova opção Instalar Serviço Windows **atualiza** a entrada SmartLibraryLocal já existente, evitando erro 1073. Antes de atualizar, feche o programa interativo e pare o serviço antigo. Caso falhe, use a opção A (Diagnosticar Serviço). A compilação do host ocorre no Windows com PowerShell/.NET Framework.
