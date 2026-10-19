# Smart Library

Biblioteca local de arquivos e mídias para Windows 11, com interface Web (HTML, CSS e JavaScript), servidor HTTP Python/SQLite e execução opcional como Serviço Windows.

## Funcionalidades

- Catálogo de múltiplos discos/pastas, filtros e busca por categoria e extensão; visualização de mídias e capas.
- Reprodução de músicas e vídeos pelo navegador em formatos compatíveis.
- Navegação por pastas para filmes e séries; filtros de recursos internos de launchers de jogos.
- Administração autenticada, downloads públicos e uploads/movimentações somente pelo Admin.
- Área privada com uma **segunda confirmação de senha** ao entrar em Protegidos; configura-se sua pasta em `Dados/area_privada.json`.
- Na rede local, a unidade C: fica indisponível; operações locais podem usar C: no navegador localhost.
- Auxiliar Local opcional para abrir o Explorador quando o servidor roda como Serviço Windows.

## Início rápido no Windows

1. Instale Python 3.10+ no Windows 11.
2. Baixe/clone o projeto; abra `Abrir Smart Library.bat` para modo interativo.
3. Acesse `http://127.0.0.1:3000`.
4. Para instalar o Serviço Windows, execute `Gerenciar Smart Library.bat` como administrador, defina uma senha Admin e escolha a instalação de serviço. O processo depende do .NET Framework 4.x/PowerShell do Windows.
5. Configure `Dados/area_privada.json`, copiando o modelo `Dados/area_privada.exemplo.json` e substituindo pelo caminho desejado. Essa configuração **não** deve ser enviada ao Git.
6. Para uso em LAN, libere a porta 3000 no Firewall pelo Gerenciador; utilize `http://IP-DO-PC:3000`. **Não publique o servidor na internet.**

Observação: o recurso Abrir local precisa de `Abrir Smart Library.bat` executado na sessão do Windows se o Serviço já estiver ativo; esse atalho inicia o auxiliar local em `127.0.0.1:38765`. Não funciona para celulares e TVs.

## Estrutura

- `Servidor/`: backend Python, Serviço Windows e agente local.
- `Interface/`: HTML, CSS e JavaScript.
- `Ferramentas/`: scripts de instalação/diagnóstico.
- `Documentacao/`: guias de atualização e segurança.
- `Dados/`: somente exemplos no repositório; o banco SQLite e as configurações reais são gerados localmente.
- `tests/`: testes de acesso e segurança.

## Testes

```bash
python -m unittest discover -s tests -v
python -m compileall -q Servidor
node --check Interface/app.js
```

Sem dependências Python externas para o servidor HTTP básico. A busca de capas utiliza consultas externas opcionais (Wikimedia Commons/Steam). O uso de FFmpeg é opcional para miniaturas.

## Segurança e publicação

**Não inclua `Dados/` real, discos pessoais, senhas, arquivos de mídia ou bancos de dados em commits.** O `.gitignore` já cobre os formatos frequentes, mas confira com `git status` antes de cada commit. A autenticação ocorre via HTTP; use exclusivamente uma rede local confiável.

Leia [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md) e [PUBLICAR-NO-GITHUB.md](PUBLICAR-NO-GITHUB.md).

Este repositório não inclui licença de distribuição explícita. Escolha e adicione uma licença antes de convidar terceiros a redistribuir/modificar o código.
