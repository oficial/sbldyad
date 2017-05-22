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
from time import strftime
from urllib.parse import urlencode

IVFS_SCRIPT = -1892814988

def send_request(port, script, data):
    payload = urlencode(data)
    http_request = urllib.request.Request(
        url='http://127.0.0.1:%s/%d'%(port, script),
        data=bytes(payload, encoding="ISO8859-1"),
        headers={
            "User-Agent": "Sublime Dyad"
        })
    http_response = urllib.request.urlopen(http_request)
    return http_response #json.loads(json_resp)

def handle_filename(filename):
    if sublime.platform() == 'linux':
        return filename.replace('Z:','').replace('H:', os.environ.get('HOME')).replace('\\','/').replace('\r\n','')
    return filename

def cache_reader(porta, base, path):
    resp = send_request(porta, IVFS_SCRIPT, {
        'command': 'export-vfs',
        'base': base,
        'path': path
    })
    for line in resp:
        line = line.decode('iso-8859-1')
        line = handle_filename(line)
        field_list = line.split(';')
        yield field_list


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
        self.project_path = None
        self.root_path = None

    def __del__(self):
        if self.conn is not None:
            self.conn.close()

    def initialize(self):
        #
        self.create_tables()

    def create_tables(self):
        self.conn.executescript("""
            create table if not exists VFS (
                TIPO integer,
                CHAVE integer primary key,
                MAE integer,
                VERSAO integer,
                NOME text,
                PATH text,
                ERRO integer,
                LICENCA integer,
                ALTERADO integer
            );
            create table if not exists CACHE_HIST (
                ID INTEGER PRIMARY KEY,
                DATA TEXT,
                HORA TEXT
            );
        """)
        self.conn.commit()

    def register_cache_load(self):
        data = strftime("%d/%m/%Y")
        hora = strftime("%H:%M:%S")
        self.conn.execute("""
            insert into CACHE_HIST (id, data, hora)
            values (NULL, ?, ?)
        """, (data, hora))
        self.conn.commit()

    def get_cache_history(self):
        cur = self.conn.cursor()
        cur.execute("select * from CACHE_HIST order by ID desc")
        return cur.fetchall()

    def reset(self):
        self.conn.execute("delete from VFS")
        self.conn.commit()

    def get_project_data(self, key=None):
        dados_do_projeto = self.window.project_data()
        if dados_do_projeto is None:
            raise Exception("Nenhum projeto aberto nessa janela!")
        if key is not None:
            return dados_do_projeto.get(key, None)
        return dados_do_projeto

    def add_project_data(self, key, value):
        pd = self.get_project_data()
        pd[key] = value
        self.window.set_project_data(pd)

    def get_project_path(self):
        if self.project_path is None:
            pfn = self.window.project_file_name()
            if pfn is None:
                raise Exception("Nenhum projeto aberto nessa janela!")
            self.project_path = os.path.dirname(pfn)
        return self.project_path

    def get_root_path(self):
        if self.root_path is None:
            self.root_path = os.path.join(self.get_project_path(), 'Raiz')
        return self.root_path

    def get_engine_port(self, raise_error=True):
        porta = self.get_project_data('engine_port')
        if porta is None and raise_error:
            raise Exception("Configure a porta antes de prosseguir!")
        return porta

    def get_engine_user(self, raise_error=True):
        user = self.get_project_data('engine_user')
        if user is None and raise_error:
            raise Exception("Configure o usuário antes de prosseguir!")
        return user

    def get_base_name(self):
        arquivo_projeto = self.window.project_file_name()
        if arquivo_projeto is None:
            raise Exception("Não foi possível encontrar um arquivo de projeto!")
        return os.path.splitext(os.path.basename(arquivo_projeto))[0]

    def insert_item(self, valores):
        valores[5] = self.file_path_to_vfs_path(valores[5])
        self.conn.execute("""
            insert into VFS (tipo, chave, mae, versao, nome, path, erro, licenca, alterado)
            values (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, valores)

    def file_path_to_vfs_path(self, filename):
        path_raiz = self.get_root_path()
        return filename.replace(path_raiz, '')

    def file_details(self, file_data):
        if file_data is None:
            return None
        if len(file_data) < 7:
            raise Exception("Dados insuficientes do arquivo!")
        return {
            'tipo':     file_data[0],
            'chave':    file_data[1],
            'mae':      file_data[2],
            'versao':   file_data[3],
            'nome':     file_data[4],
            'path':     file_data[5],
            'erro':     file_data[6],
            'licenca':  file_data[7],
            'alterado': file_data[8],
        }

    def get_script(self, path):
        cur = self.conn.cursor()
        cur.execute("select * from VFS where TIPO = 2 and PATH = ?", (path,))
        return self.file_details(cur.fetchone())

    def get_script_by_key(self, key):
        cur = self.conn.cursor()
        cur.execute("select * from VFS where TIPO = 2 and CHAVE = ?", (key,))
        return self.file_details(cur.fetchone())

    def get_script_or_class(self, key):
        cur = self.conn.cursor()
        cur.execute("""
            select *
            from VFS
            where CHAVE = ?
               or mae = ?
            order by TIPO desc -- scripts primeiro
            limit 1
        """, (key,key,))
        return self.file_details(cur.fetchone())

    def get_local_changes(self):
        cur = self.conn.cursor()
        cur.execute("select * from VFS where alterado > 0")
        return cur.fetchall()

    def get_most_recent_cache_update(self):
        atualizacoes = self.get_cache_history()
        if len(atualizacoes) is 0:
            raise Exception("Impossível determinar a data da última atualização!")

        ultima_atualizacao = atualizacoes[0]
        data = ultima_atualizacao[1]
        hora = ultima_atualizacao[2]
        return (data, hora)

    def update_local_repository(self, passwd):
        base = self.get_base_name()
        porta = self.get_engine_port()
        pasta = self.get_project_path()
        user = self.get_engine_user()

        data, hora = self.get_most_recent_cache_update()

        print("Ultima atualização foi em: %s %s" % (data, hora))

        response = send_request(porta, IVFS_SCRIPT, {
            'command': 'server-changes',
            'base': base,
            'data': data,
            'hora': hora,
            'pasta': pasta,
            'user': user,
            'passwd': passwd
        })
        text = "Tipo;Script;Versão;Path"
        for line in response:
            line = line.decode('iso-8859-1')
            if line.startswith("NENHUM"):
                return "Nenhuma alteração"
            fields = line.split(';')
            file_data = self.get_script_by_key(fields[1])
            if file_data is None:
                print("Inserindo: %s" % line)
                self.insert_item(fields)
                text += "\nINSERT;%s;%s;%s" % (
                    fields[1], fields[3], handle_filename(fields[5])
                )
            else:
                self.update_script({
                    'chave':    fields[1],
                    'mae':      fields[2],
                    'versao':   fields[3],
                    'nome':     fields[4],
                    'path':     handle_filename(fields[5])
                })
                text += "\nUPDATE;%s;%s;%s" % (
                    fields[1], fields[3], handle_filename(fields[5])
                )
        self.conn.commit()
        return text

    def set_file_changed(self, filename):
        filename = self.file_path_to_vfs_path(filename)
        cur = self.conn.cursor()
        cur.execute("""
            update VFS set ALTERADO = 1 where PATH = ?
        """, (filename,))
        self.conn.commit()

    def update_script(self, file_details):
        file_details['path'] = self.file_path_to_vfs_path(file_details.get('path'))
        cur = self.conn.cursor()
        cur.execute("""
            update vfs
            set alterado=0,
                mae=:mae,
                nome=:nome,
                versao=:versao,
                path=:path
            where chave=:chave
        """, file_details)
        self.conn.commit()

    def save_file(self, filename, user, passwd):
        dados_do_script = self.get_script(self.file_path_to_vfs_path(filename))
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
        resposta_do_engine = send_request(porta, IVFS_SCRIPT, {
            'command': 'save-file',
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

    def get_merge_tool(self):
        project_defined_tool = self.get_project_data("mergetool")
        if project_defined_tool is not None:
            return project_defined_tool
        platform = sublime.platform()

        if platform == "windows":
            # TODO - Testar
            if sublime.arch() == "x32":
                return "C:/Program Files/WinMerge/WinMergeU.exe"
            else:
                return "C:/Program Files (x86)/WinMerge/WinMergeU.exe"

        elif platform == "osx":
            # TODO - Testar
            return "/usr/bin/meld"

        else:
            return "/usr/bin/meld"

    def handle_save_result(self, dados_do_script, result):
        cod = result.get('cod')
        if cod == 'CONFLITO_DE_VERSAO':
            if not sublime.ok_cancel_dialog(
                "Conflito de versão!\nVersão local:%d\nVersão no banco:%d\nFazer o merge?"%(dados_do_script['versao'], result.get('iversion'))):
                return

            mergeFile = handle_filename(result.get('mergeFile'))

            # Retira a barra do comeco da IURL, pois ela faz o join retornar somente o segundo parametro
            localFile = os.path.join(self.get_root_path(), dados_do_script['path'][1:])

            print("Invocando o merge entre os arquivos\n%s\n%s" % (localFile, mergeFile))

            ret_code = subprocess.call(["/usr/bin/meld", localFile, mergeFile])
            if ret_code != 0: # 0 = OK!
                print('O merge terminou de forma inesperada! Código de retorno:%d'%(ret_code))
                return
            shutil.copyfile(mergeFile, localFile)
            dados_do_script['versao'] = result.get('iversion')
            self.update_script(dados_do_script)
            sublime.message_dialog("Merge local realizado com sucesso. Agora tente salvar o script novamente no engine.")

        elif cod == 'SCRIPT_ATUALIZADO':
            dados_do_script['versao'] = result.get('iversion')
            self.update_script(dados_do_script)
            sublime.message_dialog("Operação realizada com sucesso!")

        elif cod == 'SCRIPT_NAO_ATUALIZADO':
            sublime.message_dialog("Nenhum registro atualizado!")

        elif cod == 'ARQUIVO_NAO_ENCONTRADO':
            sublime.message_dialog("O arquivo informado não foi encontrado pelo engine!")

        elif cod == 'SCRIPT_NAO_ENCONTRADO':
            sublime.message_dialog("O script informado não foi encontrado na IVFS da base de destino!")

        elif cod == 'PARAMETROS_INSUFICIENTES':
            sublime.message_dialog("Alguma informação obrigatória não foi passada para o engine!")

        elif cod == 'ERRO_AO_ATUALIZAR':
            sublime.message_dialog("Erro ao atualizar o script!\nMensagem: %s" % result.get('msg'))

        else:
            sublime.message_dialog("Retorno inesperado! Verifique o log no console.")

class CacheLoader(threading.Thread):
    def __init__(self, window):
        threading.Thread.__init__(self)
        self.window = window

    def run(self):
        cache = CacheManager(self.window)
        cache.initialize()
        cache.reset()

        path = cache.get_project_path()
        port = cache.get_engine_port()
        base = cache.get_base_name()

        root = os.path.join(path,"Raiz")
        if os.path.isdir(root):
            shutil.rmtree(root)
        os.mkdir(root)
        cache.add_project_data("folders", [{"path": root}])

        print("Iniciando carga do cache as %s" % strftime("%H:%M:%S"))
        c = 0
        for f in cache_reader(port, base, root):
            try:
                c = c + 1
                cache.insert_item(f)
                if c > 100:
                    cache.conn.commit()
                    c = 0
            except Exception as e:
                print("Erro ao inserir script: %s; Erro: %s" % (f, e) )
        cache.conn.commit()
        cache.register_cache_load()
        print("Carga do cache terminou as %s" % strftime("%H:%M:%S"))


