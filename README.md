sblpackage
==========

Just a sublimetext 3 test package

TODO
==========

- Tratar ação de excluir e renomear scripts
    - Copiar a implementação dos comandos "DeleteFileCommand", "RenamePathCommand";
        - Na implementação customizada, considerar o cache local (SQLite);
    - Incluir no listener um metodo para o evento "on_window_command", redirecionando esses comandos para a versão customizada;

- Tratar ação de incluir script
    - No listener do evento "on_post_save", trocar o comando "register_file_change" por um novo que verifique se o arquivo existe no cache;

- Pegar a referencia à ferramenta de merge de acordo com a plataforma (Win/Linux)