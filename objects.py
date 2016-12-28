import os
import os.path
import glob
import json
import shutil
import sqlite3
import sublime
import threading
import subprocess
import urllib.request
from urllib.parse import urlencode

EXPORT_IVFS = 36446544
SAVE_SCRIPT = 27178271

def send_request(port, script, data):
    payload = urlencode(data)
    http_request = urllib.request.Request(
        url='http://127.0.0.1:%s/%d'%(port, script),
        data=bytes(payload, encoding="ISO8859-1"),
        headers={
            "User-Agent": "Sublime Dyad",
            # "Content-Type": "application/x-www-form-urlencoded; charset=iso-8859-1"
        })
    http_response = urllib.request.urlopen(http_request)
    # resp = http_response.readall()
    # print("Result:%s"%(json_resp))
    return http_response #json.loads(json_resp)

class CacheManager(object):
    def __init__(self, window):
        self.window = window
        project_file = window.project_file_name()
        if project_file is None:
            raise Exception("Nenhum projeto aberto nessa janela!")
        self.db_path = os.path.dirname(project_file)
        self.db_file_name = os.path.join(self.db_path,"cache.db")
        self.is_new_databse = True
        if os.path.isfile(self.db_file_name):
            self.is_new_databse = False
        self.conn = sqlite3.connect(self.db_file_name)

    def __del__(self):
        if self.conn is not None:
            self.conn.close()

    def initialize(self):
        #
        self.create_table()

    def create_table(self):
        self.conn.execute('''
            create table SCRIPTS (
                CHAVE integer primary key,
                CLASSE integer,
                VERSAO integer,
                NOME text,
                PATH text,
                ERRO integer,
                ALTERADO integer
            )
        ''')
        self.conn.commit()

    def reset(self):
        self.conn.execute("delete from SCRIPTS")
        self.conn.commit()

    def insert_script(self, valores):
        self.conn.execute("""
            insert into SCRIPTS (chave, classe, versao, nome, path, erro, alterado)
            values (?, ?, ?, ?, ?, ?, 0)""", valores
        )
        self.conn.commit()

    def file_details(self, file_data):
        if len(file_data) < 7:
            raise Exception("Dados insuficientes do arquivo!")
        return {
            'chave':    file_data[0],
            'classe':   file_data[1],
            'versao':   file_data[2],
            'nome':     file_data[3],
            'path':     file_data[4],
            'erro':     file_data[5],
            'alterado': file_data[6],
        }

    def get_script(self, path):
        cur = self.conn.cursor()
        cur.execute("select * from SCRIPTS where PATH = ?", (path,))
        return self.file_details(cur.fetchone())

    def get_script_by_key(self, key):
        cur = self.conn.cursor()
        cur.execute("select * from SCRIPTS where CHAVE = ?", (key,))
        return self.file_details(cur.fetchone())

    def get_script_or_class(self, key):
        cur = self.conn.cursor()
        cur.execute("""
            select *
            from SCRIPTS
            where CHAVE = ?
               or CLASSE = ?
            order by NOME
            limit 1
        """, (key,key,))
        return self.file_details(cur.fetchone())

    def set_file_changed(self, filename):
        cur = self.conn.cursor()
        cur.execute("update SCRIPTS set ALTERADO = 1 where PATH = ?", (filename, ))
        self.conn.commit()

    def update_script(self, file_details):
        cur = self.conn.cursor()
        cur.execute("""
            update scripts
            set alterado=0, versao=:versao
            where chave=:chave
        """, file_details)
        self.conn.commit()

    def save_script(self, filename, user, passwd):
        dados_do_script = self.get_script(filename)
        if dados_do_script is None:
            raise Exception("Arquivo não encontrado no cache do sublime!")

        dados_do_projeto = self.window.project_data()
        if dados_do_projeto is None:
            raise Exception("Nenhum projeto aberto nessa janela!")

        porta = dados_do_projeto['engine_port'] or None
        if porta is None:
            raise Exception("Configure a porta antes de prosseguir!")

        arquivo_projeto = self.window.project_file_name()
        nome_da_base = os.path.splitext(os.path.basename(arquivo_projeto))[0]
        resposta_do_engine = send_request(porta, SAVE_SCRIPT, {
            'base': nome_da_base,
            'ikey': dados_do_script.get('chave'),
            'iversion': dados_do_script.get('versao'),
            'file': filename,
            'user': user,
            'passwd': passwd
        })
        resposta = resposta_do_engine.readall().decode('iso-8859-1')
        print("Resposta: %s" % resposta)
        resposta_json = json.loads(resposta)
        self.handle_save_result(dados_do_script, resposta_json)

    def handle_save_result(self, dados_do_script, result):
        cod = result.get('cod')
        if cod == 'CONFLITO_DE_VERSAO':
            if not sublime.ok_cancel_dialog(
                "Conflito de versão!\nVersão local:%d\nVersão no banco:%d\nFazer o merge?"%(dados_do_script.get('versao'), result.get('iversion'))):
                return
            mergeFile = result.get('mergeFile')
            result = subprocess.call(["/usr/bin/meld", dados_do_script.get('path'), mergeFile])
            if result != 0: # 0 = OK!
                print('O merge terminou de forma inesperada! Código de retorno:%d'%(result))
                return
            shutil.copyfile( result.get('mergeFile'), dados_do_script.get('path'))
            dados_do_script['versao'] = result.get('iversion')
            self.update_script(dados_do_script)
            sublime.message_dialog("Operação realizada com sucesso!")
        elif cod == 'SCRIPT_ATUALIZADO':
            dados_do_script['versao'] = result.get('iversion')
            self.update_script(dados_do_script)
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


class CacheLoader(threading.Thread):
    def __init__(self, window):
        self.window = window
        threading.Thread.__init__(self)

    def run(self):
        dados_do_projeto = self.window.project_data()
        if dados_do_projeto is None:
            raise Exception("Nenhum projeto aberto nessa janela!")
        porta = dados_do_projeto['engine_port'] or None
        if porta is None:
            raise Exception("Configure a porta antes de prosseguir!")
        arquivo_projeto = self.window.project_file_name()
        pasta_do_projeto = os.path.dirname(arquivo_projeto)
        nome_da_base = os.path.splitext(os.path.basename(arquivo_projeto))[0]
        pasta_raiz = os.path.join(pasta_do_projeto,"Raiz")
        if os.path.isdir(pasta_raiz):
            shutil.rmtree(pasta_raiz)
        os.mkdir(pasta_raiz)
        dados_do_projeto["folders"] = [{"path": pasta_raiz}]
        self.window.set_project_data(dados_do_projeto)
        resposta_do_engine = send_request(porta, EXPORT_IVFS, {
            'base': nome_da_base,
            'path': pasta_raiz
        })
        cache = CacheManager(pasta_do_projeto)
        cache.initialize()
        cache.reset()
        for linha in resposta_do_engine:
            linha = linha.decode('iso-8859-1')
            dados_do_script = linha.split(';')
            try:
                cache.insert_script(dados_do_script)
            except Exception as e:
                print("Erro ao inserir script no cache: %s; Erro: %s" % (linha, e) )

