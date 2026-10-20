# Como publicar

Esta pasta `GitHub/` é a **raiz do repositório**. Publique seu conteúdo, não toda a pasta da instalação do Smart Library.

1. Crie um repositório vazio no GitHub (preferencialmente **privado** até revisar o conteúdo).
2. Copie/abra **somente esta pasta GitHub** no terminal.
3. Configure a URL do seu repositório e publique:

```bash
git init
git add .
git status
git commit -m "Smart Library v1.0.17"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
git push -u origin main
```

4. Confira o conteúdo do primeiro commit **antes** de executar `git push`. A configuração local `Dados/area_privada.json` não deve ser enviada.
5. Se quiser liberar contribuições externas, escolha uma licença e adicione um arquivo LICENSE.

**Cuidado:** o `.gitignore` não apaga arquivos privados já rastreados em commits antigos. Este export foi criado sem dados pessoais.
