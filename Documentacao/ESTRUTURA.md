# Estrutura do projeto

```text
Smart-Library-v1.0.11/
├── Abrir Smart Library.bat         Inicializador local / abre serviço existente
├── Gerenciar Smart Library.bat     Menu de administração do sistema
├── README.md                       Guia rápido
├── Servidor/                       Código Python, API e serviço Windows
│   ├── server.py
│   ├── admin_password.py
│   ├── duplicate_finder.py
│   └── SmartLibraryServiceHost.cs (host Windows compilado no instalador)
│   └── windows_service.py (legado, mantido para compatibilidade)
├── Interface/                      HTML, CSS, JS e ícone da aplicação
│   ├── index.html
│   ├── app.css
│   ├── app.js
│   └── favicon.svg
├── Ferramentas/                     Scripts administrativos e FFmpeg opcional
│   ├── Instalar Servico Windows.bat
│   ├── Remover Servico Windows.bat
│   ├── Status Servico Windows.bat
│   ├── Iniciar Servico Windows.bat
│   ├── Parar Servico Windows.bat
│   ├── Alterar Senha Admin.bat
│   ├── Liberar Acesso Rede Local.bat
│   └── Instalar Miniaturas (Opcional).bat
├── Dados/                           Base de dados e miniaturas (persistente)
└── Documentacao/                    Instruções e manutenção
```

- `Servidor` e `Interface` são código da aplicação, podem ser substituídos nas atualizações.
- `Dados` contém suas configurações, senha Admin, catálogo e miniaturas, **nunca substitua sem backup**.
- `Ferramentas` concentra operações que exigem permissões elevadas. Não execute os BAT sem compreender o efeito.
- `Miniaturas` pode ser ocultada no Windows, mas atributos ocultos não equivalem a criptografia.
