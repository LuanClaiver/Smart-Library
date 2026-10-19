# Publicar Smart Library no GitHub

Repositório: **https://github.com/LuanClaiver/Smart-Library**.

## Publicação com dois cliques (Windows 11)

1. Instale [Git for Windows](https://git-scm.com/download/win), caso ainda não tenha.
2. Extraia o pacote **Smart-Library-v1.0.15-GitHub-com-envio.zip**.
3. Abra a pasta extraída e execute **`Enviar para GitHub.bat`**.
4. Na primeira publicação, o Git poderá solicitar nome/email para autoria dos commits e autenticação no GitHub por navegador.
5. Revise os nomes dos arquivos listados, digite **`PUBLICAR`** para autorizar e aguarde o resultado.
6. Acesse <https://github.com/LuanClaiver/Smart-Library> para conferir.

### Atualizações futuras

A cada nova versão do Smart Library, use um pacote GitHub atualizado que contenha os dois scripts de publicação. O envio usa um clone local persistente em `%LOCALAPPDATA%\SmartLibrary\GitHubRepo`, então pode publicar mesmo que cada versão seja extraída em uma pasta diferente. Não usa `--force` e não apaga alterações remotas. Arquivos removidos do projeto podem exigir limpeza manual no repositório, pois o script não os apaga automaticamente.

### Segurança

A cópia GitHub contém somente o código-fonte e arquivos de configuração de exemplo. A publicação só inclui arquivos e diretórios previamente autorizados e **nunca** transfere o `Dados` real (senhas, banco de dados, capas pessoais, mídia, logs ou miniaturas). O script mostra o que será enviado antes de publicar. O repositório é **público**: revise sempre a lista mostrada e não adicione segredos ao código-fonte.

Se o envio falhar, a janela mostrará a mensagem original do Git. A autenticação é feita pelo Git for Windows/Git Credential Manager, sem pedir sua senha do GitHub dentro deste script.
