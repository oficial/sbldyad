import sublime
import sublime_plugin

class TratadorDeEventos(sublime_plugin.EventListener):

    def on_load(self, view):
        view.run_command("show_file_info")

    def on_pre_save(self, view):
        pass
        # print("Antes de salvar")

    def on_post_save(self, view):
        view.run_command("register_file_change")
