#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import json
import fnmatch
import threading
import sublime
import sublime_plugin

#TODO - Utilizar o módulo shelve para persistir o indice de chaves em disco
#TODO - Validar path passado no construtor
#TODO - Ao abrir um script com o CTRL+ENTER (OpenKeyCommand), localizar o arquivo na arvore
#TODO - Permitir scripts positivos

class BuildIndexCommand(sublime_plugin.WindowCommand):
    def run(self):
        if hasattr(sublime,'keyindex'):
            if not sublime.ok_cancel_dialog("Indice ja construído. Substituir?"):
                return
        project_data = self.window.project_data()
        project_basepath = project_data.get('folders')[0].get('path')
        builder = KeyIndexBuilder( project_basepath ) 
        builder.start()
        self.check_build_process( builder )

    def check_build_process(self, thread, i=0, dir=1):
        if thread.is_alive():
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            self.window.active_view().set_status('', 'Indexando [%s=%s]' % (' ' * before, ' ' * after))
            sublime.set_timeout(lambda: self.check_build_process( thread, i, dir), 100)
            return        
        # Trata o resultado
        if not thread.result:
            print("Thread concluiu mas não há resultado!")
            return
        sublime.keyindex = thread.result
        #sublime.active_window().keyindex = thread.result
        sublime.status_message("Indice construido com sucesso!")
        self.window.active_view().set_status('','')
       
class OpenKeyCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		window = sublime.active_window()
		project_data = window.project_data()
		project_basepath = project_data.get('folders')[0].get('path')
		#print("Diretorio do projeto: %s"%(project_basepath))
		# 1.Seleciona a palavra na qual o cursor está
		self.view.run_command('expand_selection', {"to":"word"})
		# 2.Pega a primeira palavra selecionada
		sels = self.view.sel()
		if len(sels) == 0:
			return
		searchkey = self.view.substr(sels[0])
		# 3.Verifica se a palavra selecionada é um numero 
		if not searchkey.isdigit():
			print('%s is not a valid key!'%(searchkey))
			return
		if not searchkey.startswith('-'):
			searchkey = '-%s'%(searchkey)
		searchkey = int(searchkey)	
		# 4.Verifica se o index existe		
		if not hasattr(sublime,'keyindex'):
			sublime.status_message("Key index not built!")
			return
		# 5.Pega a URL do script no index
		#print('Procurando a chave:[%s]'%(searchkey))
		iurl = sublime.keyindex.get(searchkey)
		#print("Encontrou: %s"%(iurl))
		if not iurl:
			sublime.status_message("Key %s not found in index!"%(searchkey))
			#print("%d chave(s)"%(len(sublime.keyindex.keys())))
			#print(sublime.keyindex.keys())
			return
		# 6.abrir o arquivo com Window.open_file(filename) 
		if not os.path.isfile( os.path.join(project_basepath,iurl)):
			#print("Não encontrou o script: %s"%(os.path.join(project_basepath,iurl)))
			sublime.status_message("Script not found: %s"%(iurl))
			return
		window.open_file(os.path.join(project_basepath,iurl))

class KeyIndexBuilder(threading.Thread):  
    def __init__(self, project_path):  
        self.path = project_path
        self.result = None  
        threading.Thread.__init__(self)  
    def run(self):  
        index = {}
        ikey = iurl = None
        try:
            for root, dirnames, filenames in os.walk(self.path):
                for filename in fnmatch.filter(filenames, '*.metadata'):
                    try:
                        if os.path.isfile(os.path.join(root,filename)):
                            js = json.load(open(os.path.join(root,filename), encoding='ISO8859-1'))
                            ikey = js.get('ikey')
                            iurl = js.get('iurl')
                            if iurl.startswith(os.path.sep):
                            	iurl = iurl.lstrip(os.path.sep) 
                            index[ikey] = iurl
                        else:
                            print('File not found:%s|%s'%(root, filename))
                            break
                    except UnicodeDecodeError as e1:
                        print('Erro ao ler o arquivo:%s\nErro:%s'%(os.path.join(root,filename), e1))
                        break
                    except Exception as e2:
                        print('Erro ao abrir o arquivo:%s\nErro:%s'%(os.path.join(root,filename), e2))
                        break
            self.result = index
            return
        except Exception as e:
            err = 'Erro:%s' % (e)
            print(err)
        sublime.error_message(err)  
        self.result = None  