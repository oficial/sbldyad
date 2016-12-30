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

    # def on_window_command(self, window, name, args):
    #     # if name == 'goto_definition':
    #     print("on_window_command: %s(%s)" % (name,args))
    #     return None

    # def on_post_window_command(self, window, name, args):
    #     # if name == 'goto_definition':
    #     print("on_post_window_command: %s(%s)" % (name,args))
    #     return None

