import os
import os.path
import sublime
import sublime_plugin
from Dyad.objects import CacheLoader, CacheManager



class ConfigPortCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        return self.window.project_data() is not None

    def run(self):
        proj_data = self.window.project_data()
        if proj_data is None:
            sublime.error_message("Nenhum projeto aberto nessa janela!")
            return
        porta = self.get_project_setting('engine_port')
        self.window.show_input_panel("Porta do engine", porta or "", self.handle_user_input, None, None)

    def get_project_setting(self, key):
        proj_data = self.window.project_data()
        try:
            return proj_data[key]
        except KeyError:
            return None

    def handle_user_input(self, port):
        try:
            proj_data = self.window.project_data()
            proj_data['engine_port'] = port
            self.window.set_project_data(proj_data)
        except Exception as e:
            sublime.error_message("Erro: %s" % e)

class ConfigUserCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        return self.window.project_data() is not None

    def run(self):
        proj_data = self.window.project_data()
        if proj_data is None:
            sublime.error_message("Nenhum projeto aberto nessa janela!")
            return
        usuario = self.get_project_setting('engine_user')
        self.window.show_input_panel("Usuário", usuario or "", self.handle_user_input, None, None)

    def get_project_setting(self, key):
        proj_data = self.window.project_data()
        try:
            return proj_data[key]
        except KeyError:
            return None

    def handle_user_input(self, user):
        try:
            proj_data = self.window.project_data()
            proj_data['engine_user'] = user
            self.window.set_project_data(proj_data)
        except Exception as e:
            sublime.error_message("Erro: %s" % e)

class LoadCacheCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        prj = self.window.project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True

    def run(self):
        try:
            mensagem_confirmacao = """Atenção! Todos os arquivos do projeto serão descartados e uma nova cópia da IVFS será gerada em disco. Deseja mesmo continuar ?"""
            if sublime.yes_no_cancel_dialog(mensagem_confirmacao, "Arrocha!", "Deixa quieto!") is not sublime.DIALOG_YES:
                return
            print(self.window)
            loader = CacheLoader(self.window)
            loader.start()
            self.check_load_progress( loader )
        except Exception as e:
            sublime.error_message("Erro: %s" % e)

    def check_load_progress(self, loader, i=0, dir=1):
        try:
            if loader.is_alive():
                before = i % 8
                after = (7) - before
                if not after:
                    dir = -1
                if not before:
                    dir = 1
                i += dir
                self.window.active_view().set_status('', 'Carregando [%s=%s]' % (' ' * before, ' ' * after))
                sublime.set_timeout(lambda: self.check_load_progress( loader, i, dir), 100)
                return
            self.window.active_view().set_status('','')
            sublime.run_command("refresh_folder_list")
            sublime.message_dialog("Cache carregado com sucesso!")
        except Exception as e:
            sublime.error_message("Erro: %s" % e)

class CopyKeyToClipboardCommand(sublime_plugin.WindowCommand):
    def is_visible(self, files):
        if len(files) <= 0:
            return False
        prj = self.window.project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True

    def run(self, files):
        for f in files:
            v = self.window.find_open_file(f)
            if v is None:
                return

            self.copy_file_key(v,f)

    def copy_file_key(self, view, file):
        cache = CacheManager(self.window)
        dados_do_script = cache.get_script(file)
        if dados_do_script is None:
            return
        sublime.set_clipboard(str(dados_do_script.get('chave')))
        sublime.status_message("Chave %d copiada" % dados_do_script.get('chave'))


class ShowFileInfoCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        prj = self.view.window().project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True
    def run(self, edit):
        filename = self.view.file_name()
        if not filename:
            return
        # pasta_do_projeto = os.path.dirname(self.view.window().project_file_name())
        cache = CacheManager(self.view.window())
        dados_do_script = cache.get_script(filename)
        if dados_do_script is not None:
            self.view.set_status('chave', ("Chave:%d" % dados_do_script.get('chave')))
            self.view.set_status('versao', ("Versão:%d" % dados_do_script.get('versao')))

class OpenKeyCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        prj = self.view.window().project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True

    def run(self, edit):
        proj_data = self.view.window().project_data()
        # if proj_data is None:
        #     sublime.error_message("Nenhum projeto aberto nessa janela!")
        #     return
        # if not proj_data.get('engine_port'):
        #     sublime.error_message("Esse não é um projeto de cache local ou a porta ainda não foi configurada!")
        #     return
        self.view.run_command('expand_selection', {"to":"word"})
        sels = self.view.sel()
        if len(sels) == 0:
            return
        regiao_da_palavra = self.view.word(sels[0])
        palavra = self.view.substr(regiao_da_palavra)
        if not palavra.isdigit():
            return
        regiao_da_palavra.a = regiao_da_palavra.a - 1
        palavra_expandida = self.view.substr(regiao_da_palavra)
        try:
            int(palavra_expandida)
            palavra = palavra_expandida
        except ValueError:
            pass
        searchkey = int(palavra)
        # print("Chave selecionada: %d" % searchkey)
        cache = CacheManager(self.view.window())
        dados_do_script = cache.get_script_or_class(searchkey)
        if dados_do_script is None:
            return
        if dados_do_script.get('erro') > 0:
            sublime.error_message("Aconteceu algum problema e não foi possível exportar esse arquivo para o projeto do sublime!")
            return
        pasta_raiz = proj_data.get('folders')[0].get('path')
        caminho_script = os.path.join(pasta_raiz, dados_do_script.get('path'))
        caminho_script = caminho_script.replace('\\','/')
        if os.path.isfile(caminho_script):
            self.view.window().open_file(caminho_script)

class RegisterFileChangeCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        prj = self.view.window().project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True

    def run(self, edit):
        filename = self.view.file_name()
        if not filename:
            return
        cache = CacheManager(self.view.window())
        cache.set_file_changed(filename)

class SaveFileCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        prj = self.view.window().project_data()
        if prj is None:
            return False
        if prj.get('engine_port') is None:
            return False
        return True

    def run(self, edit):
        self.filename = self.view.file_name()
        if self.filename is None:
            return
        dados_do_projeto = self.view.window().project_data()
        self.user = dados_do_projeto['engine_user'] or None
        if self.user is None:
            raise Exception("Configure a usuário antes de prosseguir!")
        self.view.window().show_input_panel("Senha do usuario", "", self.handle_user_input, None, None)

    def handle_user_input(self, passwd):
        try:
            cache = CacheManager(self.view.window())
            cache.save_script(self.filename, self.user, passwd)
        except Exception as e:
            sublime.error_message("Erro: %s" % e)


