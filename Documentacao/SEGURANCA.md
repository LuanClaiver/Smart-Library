# Segurança e acesso pela rede

- Visitantes podem consultar e reproduzir itens públicos; as rotas de edição exigem Admin.
- Itens protegidos devem continuar inacessíveis sem Admin. A pasta `Dados` nunca é servida como arquivo estático.
- O painel é HTTP **sem criptografia**, portanto use somente em redes privadas confiáveis; não redirecione a porta 3000 no roteador para a internet.
- O serviço roda com a identidade configurada no Windows e só pode administrar discos com permissões para essa conta.
- O atributo Windows `Oculto` não protege os arquivos diretamente no disco. Para proteção real no PC, use ACLs/criptografia do Windows.
- Antes de usar excluir ou mover remotamente, teste com arquivos sem importância e confira a Quarentena em modo Serviço.
- Reprodução em navegador depende dos codecs do dispositivo; conversão automática não está incluída.
