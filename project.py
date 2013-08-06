import sublime
import sublime_plugin

class CreateEngineProjectCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		sublime.message_dialog("Ainda não implementado!")

class ConfigureEnginePortCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		self.view.window().show_input_panel("Porta do engine", "8080", self.handle_user_input, None, None)

	def handle_user_input(self, port):
		sublime.engine_port = port