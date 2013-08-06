#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import json 
import shutil
import urllib  
import sublime
import hashlib
import subprocess
import sublime_plugin

# TODO [1]: Se o MD5 do arquivo atual bater com o dos metadados então nao precisa atualizar

def get_engine_port():
	if not hasattr(sublime, 'engine_port'):
		sublime.active_window().active_view().run_command('configure_engine_port')
	print("Porta do engine:%s"%(sublime.engine_port))
	return sublime.engine_port

def handle_filename(filename):
	if sublime.platform() == 'linux':
		return filename.replace('Z:','').replace('\\','/')
	return filename

def load_metadata(filename):
	# Carrega o arquivo de metadados
	if not os.path.isfile("%s.metadata"%(filename)):
		print("Arquivo de metadados não foi encontrado!")
		return None
	return json.load(open("%s.metadata"%(filename)))

def save_metadata(filename, metadata):
	changed_metadata = "%s.metadata_new"%(filename) 
	with open(changed_metadata, mode='w') as md2:
		md2.write(json.dumps(metadata))
	shutil.move(changed_metadata, "%s.metadata"%(filename) )
def get_file_md5(filename):
	md5 = hashlib.md5()
	with open(filename) as f:
		md5.update(f.read())
	return md5.hexdigest()

def send_request(port, script, data):
	payload = urllib.parse.urlencode(data)
	http_request = urllib.request.Request(
		url='http://127.0.0.1:%s/%d'%(port, script), 
		data=bytes(payload, encoding="ISO8859-1"),
		headers={"User-Agent": "Sublime Dyad"})
	http_response = urllib.request.urlopen(http_request)
	json_resp = http_response.readall().decode('utf-8')
	print("Result:%s"%(json_resp))
	return json.loads(json_resp)

def merge_files(command, filename, jsResult):
	md = load_metadata(filename)
	mergeFile = handle_filename(jsResult.get('mergeFile'))	
	return subprocess.call(["/usr/bin/meld", filename, mergeFile])	

class SyncFileCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		pass

class SaveFileCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		fn   = self.view.file_name()
		port = get_engine_port()
		md   = load_metadata(fn)
		# TODO [1]
		# if md.get('md5') == get_file_md5(fn):
		# 	sublime.message_dialog("Arquivo não foi alterado!")
		# 	return
		print("Arquivo p/ sincronizar: %s"%(fn))
		# Prepara os dados da requisicao
		js = send_request( port, 27178271, {
			'file': fn,
			'ikey': md.get('ikey'),
			'iversion':md.get('iversion'),
			'user':self.view.settings().get('engineUser'),
			'passwd':self.view.settings().get('enginePasswd')
		})
		self.handle_result(edit, js, fn, md)

	def handle_result(self, edit, jsResult, filename, metadata):
		cod = jsResult.get('cod')
		if cod == 'CONFLITO_DE_VERSAO':
			if not sublime.ok_cancel_dialog(
					"Conflito de versão!\nVersão local:%d\nVersão no banco:%d\nFazer o merge?"%(metadata.get('iversion'),jsResult.get('iversion'))):
				return
			result = merge_files(self, filename, jsResult)
			if result != 0: # 0 = OK!
				print('O merge terminou de forma inesperada! Código de retorno:%d'%(result))
				return
			shutil.copyfile( handle_filename(jsResult.get('mergeFile')), filename)
			metadata['iversion'] = jsResult.get('iversion')
			# metadata['md5'] = get_file_md5(filename)
			save_metadata(filename, metadata)
		elif cod == 'SCRIPT_ATUALIZADO':
			metadata['iversion'] = jsResult.get('iversion')
			save_metadata(filename, metadata)
			sublime.message_dialog("Operação realizada com sucesso!")
		elif cod == 'SCRIPT_NAO_ATUALIZADO':
			sublime.message_dialog("Nenhum reg==tro atualizado!")
		elif cod == 'ARQUIVO_NAO_ENCONTRADO':
			sublime.message_dialog("O arquivo informado não foi encontrado pelo engine!")
		elif cod == 'SCRIPT_NAO_ENCONTRADO':
			sublime.message_dialog("O script informado não foi encontrado na IVFS da base de destino!")
		elif cod == 'PARAMETROS_INSUFICIENTES':
			sublime.message_dialog("Alguma informação obrigatória não foi passada para o engine!")
		elif cod == 'ERRO_AO_ATUALIZAR':
			sublime.message_dialog("Erro ao atualizar o script! Verifique o log no console.")
		else:
			sublime.message_dialog("Retorno inesperado! Verifique o log no console.")

class FileInfoCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		filename = self.view.file_name()
		metadata_file = filename + '.metadata'
		if os.path.isfile(metadata_file):
			mdf = open(metadata_file)
			js = json.load(mdf)
			sublime.message_dialog('Dados do arquivo:\nChave:%s\nVersao:%s'%(js.get('ikey'), js.get('iversion')))
		else:
			sublime.error_message('Arquivo de metadados não encontrado!')
