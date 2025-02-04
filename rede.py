# -*- coding: utf-8 -*-
"""
Created on set/2020
@author: github rictom/rede-cnpj
"""
#http://pythonclub.com.br/what-the-flask-pt-1-introducao-ao-desenvolvimento-web-com-python.html
from flask import Flask, request, render_template, send_from_directory, send_file, jsonify, Response
from werkzeug.utils import secure_filename
import os, sys, json, secrets
import config, rede_relacionamentos
import pandas as pd

#from requests.utils import unquote
app = Flask("rede")
#https://blog.cambridgespark.com/python-context-manager-3d53a4d6f017
gp = {}
gp['numeroDeEmpresasNaBase'] = rede_relacionamentos.numeroDeEmpresasNaBase()
gp['camadaMaxima'] = 15

#como é usada a tabela tmp_cnpjs no sqlite para todas as consultas, se houver requisições simultâneas ocorre colisão. 
#o lock faz esperar terminar as requisições por ordem.
#no linux, quando se usa nginx e uwsgi, usar lock do uwsgi, senão lock do threading (funciona no linux quando só tem 1 worker)
import contextlib
try:
    import uwsgi #supondo que quando tem uwsgi instalado, está usando linux e nginx
    gUwsgiLock=True
    #rlock = contextlib.nullcontext() #funciona no python3.7
    gLock =  contextlib.suppress() #python <3.7 #context manager que não faz nada
except:
    from threading import Lock
    gUwsgiLock=False
    gLock = Lock() #prevenir erros de requisições seguidas. No servidor faz o esperado colocando só um thread no rede.wsgi.ini


@app.route("/rede/")
@app.route("/rede/grafico/<int:camada>/<cpfcnpj>")
@app.route("/rede/grafico_no_servidor/<idArquivoServidor>")
def html_pagina(cpfcnpj='', camada=0, idArquivoServidor=''):
    mensagemInicial = ''
    inserirDefault = ''
    listaEntrada = ''
    listaJson = ''
    #camada = config.par.camadaInicial if config.par.camadaInicial else camada
    camada = camada if camada else config.par.camadaInicial
    camada = min(gp['camadaMaxima'], camada)
    #print(list(request.args.keys()))
    #print(request.args.get('mensagem_inicial'))
    # if par.idArquivoServidor:
    #     idArquivoServidor =  par.idArquivoServidor
    #idArquivoServidor = config.par.idArquivoServidor if config.par.idArquivoServidor else idArquivoServidor
    idArquivoServidor = idArquivoServidor if idArquivoServidor else config.par.idArquivoServidor
    if idArquivoServidor:
        idArquivoServidor = secure_filename(idArquivoServidor)
    bBaseFullTextSearch = 1 if config.config['BASE'].get('base_receita_fulltext','') else 0
    listaImagens = rede_relacionamentos.imagensNaPastaF(True)
    if config.par.arquivoEntrada:
        #if os.path.exists(config.par.listaEntrada): checado em config
        extensao = os.path.splitext(config.par.arquivoEntrada)[1].lower()
        if extensao in ['.py','.js']:
            listaEntrada = open(config.par.arquivoEntrada, encoding=config.par.encodingArquivo).read()
            if extensao=='.py': #configura para lista hierarquica
                listaEntrada = '_>p\n' + listaEntrada
            elif extensao=='.js':
                listaEntrada = '_>j\n' + listaEntrada
        elif extensao=='.json':
            listaJson = json.loads(open(config.par.arquivoEntrada, encoding=config.par.encodingArquivo).read())
        elif extensao in ['.csv','.txt']:
            df = pd.read_csv(config.par.arquivoEntrada, sep=config.par.separador, dtype=str, header=None, keep_default_na=False, encoding=config.par.encodingArquivo, skip_blank_lines=False)
        elif extensao in ['.xlsx','xls']:
            #df = pd.read_excel(config.par.arquivoEntrada, sheet_name=config.par.excel_sheet_name, header= config.par.excel_header, dtype=str, keep_default_na=False)
            df = pd.read_excel(config.par.arquivoEntrada, sheet_name=config.par.excel_sheet_name, header= None, dtype=str, keep_default_na=False)
        else:
            print('arquivo em extensão não reconhecida, deve ser csv, txt ou json:' + config.par.arquivoEntrada)
            sys.exit(0)
        if extensao in ['.csv', '.txt', '.xlsx', 'xls']:
            listaEntrada = ''
            for linha in df.values:
                listaEntrada += '\t'.join([i.replace('\t',' ') for i in linha]) + '\n'       
            #print(listaEntrada)
            df = None            
    elif not cpfcnpj and not idArquivoServidor: #define cpfcnpj inicial, só para debugar.
        cpfcnpj = config.par.cpfcnpjInicial
        numeroEmpresas = gp['numeroDeEmpresasNaBase']
        tnumeroEmpresas = format(numeroEmpresas,',').replace(',','.')
        if  config.par.bExibeMensagemInicial:
            if numeroEmpresas>40000000: #no código do template, dois pontos será substituida por .\n
                mensagemInicial = f'''LEIA ANTES DE PROSSEGUIR.\n\nTodos os dados exibidos são públicos, provenientes da página de dados públicos da Secretaria da Receita Federal.\nO autor não se responsibiliza pela utilização desses dados, pelo mau uso das informações ou incorreções.\nA base tem {tnumeroEmpresas} empresas.\n''' + config.referenciaBD
            else:
                #mensagemInicial = f"A base sqlite de TESTE tem {tnumeroEmpresas} empresas fictícias.\nPara inserir um novo elemento digite TESTE (CNPJ REAL NÃO SERÁ LOCALIZADO)"
                mensagemInicial = f"A base sqlite de TESTE tem {tnumeroEmpresas} empresas de pessoas politicamente expostas, conforme dados do Portal da Transparência da CGU.\nPara inserir um novo elemento digite TESTE ou nome do político."
                inserirDefault =' TESTE'        
    
    if config.par.tipo_lista:
        if config.par.tipo_lista.startswith('_>'):
            listaEntrada = config.par.tipo_lista + '\n' + listaEntrada 
        else:
            listaEntrada = config.par.tipo_lista + listaEntrada
            
    paramsInicial = {'cpfcnpj':cpfcnpj, 
                     'camada':camada,
                     'mensagem':mensagemInicial,
                     'bMenuInserirInicial': config.par.bMenuInserirInicial,
                     'inserirDefault':inserirDefault,
                     'idArquivoServidor':idArquivoServidor,
                     'lista':listaEntrada,
                     'json':listaJson,
                     'listaImagens':listaImagens,
                      'bBaseFullTextSearch': bBaseFullTextSearch,
                      'btextoEmbaixoIcone':config.par.btextoEmbaixoIcone,
                      'referenciaBD':config.referenciaBD,
                      'referenciaBDCurto':config.referenciaBD.split(',')[0]}
    config.par.idArquivoServidor='' #apagar para a segunda chamada da url não dar o mesmo resultado.
    config.par.arquivoEntrada=''
    config.par.cpfcnpjInicial=''
    return render_template('rede_template.html', parametros=paramsInicial)
    # return render_template('rede_template.html', cpfcnpjInicial=cpfcnpj, camadaInicial=camada, 
    #                        mensagemInicial=mensagemInicial, inserirDefault=inserirDefault, idArquivoServidor=idArquivoServidor,
    #                        bBaseFullTextSearch = bBaseFullTextSearch, listaImagens=listaImagens)
#.def html_pagina
    
# @app.route('/rede/grafojson/cnpj/<int:camada>/<cpfcnpj>',  methods=['GET','POST'])
# def serve_rede_json_cnpj(cpfcnpj, camada=1):
#     with gLock:
#         camada = min(gp['camadaMaxima'], int(camada))
#         listaIds = request.get_json()
#         if listaIds:
#             cpfcnpj=''
#         if not cpfcnpj:
#             return jsonify(rede_relacionamentos.camadasRede(cpfcnpjIn=cpfcnpj,  listaIds=listaIds, camada=camada, grupo='', bjson=True)) 
#         elif cpfcnpj.startswith('PJ_') or cpfcnpj.startswith('PF_'):
#             return jsonify(rede_relacionamentos.camadasRede(cpfcnpjIn=cpfcnpj, camada=camada, grupo='', bjson=True )) 
#         elif cpfcnpj.startswith('EN_') or cpfcnpj.startswith('EM_') or cpfcnpj.startswith('TE_'):
#             return jsonify(rede_relacionamentos.camadaLink(cpfcnpjIn=cpfcnpj,   listaIds=listaIds, camada=camada, tipoLink='endereco'))
#         return  jsonify(rede_relacionamentos.camadasRede(cpfcnpj, camada=camada))


@app.route('/rede/grafojson/cnpj/<int:camada>/<cpfcnpj>',  methods=['GET','POST'])
def serve_rede_json_cnpj(cpfcnpj, camada=1):
    camada = min(gp['camadaMaxima'], int(camada))
    listaIds = request.get_json()
    r = None
    if gUwsgiLock:
        uwsgi.lock()
    try:
        with gLock:
            if listaIds:
                cpfcnpj=''
            if not cpfcnpj:
                r = jsonify(rede_relacionamentos.camadasRede(cpfcnpjIn=cpfcnpj,  listaIds=listaIds, camada=camada, grupo='', bjson=True)) 
            elif cpfcnpj.startswith('PJ_') or cpfcnpj.startswith('PF_'):
                r = jsonify(rede_relacionamentos.camadasRede(cpfcnpjIn=cpfcnpj, camada=camada, grupo='', bjson=True )) 
            elif cpfcnpj.startswith('EN_') or cpfcnpj.startswith('EM_') or cpfcnpj.startswith('TE_'):
                r = jsonify(rede_relacionamentos.camadaLink(cpfcnpjIn=cpfcnpj,   listaIds=listaIds, camada=camada, tipoLink='endereco'))
            else:
                r = jsonify(rede_relacionamentos.camadasRede(cpfcnpj, camada=camada))
    finally:
        if gUwsgiLock:
            uwsgi.unlock()
    return r
#.def serve_rede_json_cnpj

@app.route('/rede/grafojson/links/<int:camada>/<int:numeroItens>/<int:valorMinimo>/<int:valorMaximo>/<cpfcnpj>',  methods=['GET','POST'])
def serve_rede_json_links(cpfcnpj='', camada=1, numeroItens=15, valorMinimo=0, valorMaximo=0):
    r = None
    if gUwsgiLock:
        uwsgi.lock()
    try:
        with gLock:
            camada = min(gp['camadaMaxima'], int(camada))
            listaIds = request.get_json()
            if listaIds:
                cpfcnpj=''
            r = jsonify(rede_relacionamentos.camadaLink(cpfcnpjIn=cpfcnpj, listaIds=listaIds, camada=camada, numeroItens=numeroItens, valorMinimo=valorMinimo, valorMaximo=valorMaximo, tipoLink='link'))
    finally:
        if gUwsgiLock:
            uwsgi.unlock()        
    return r
#.def serve_rede_json_links

@app.route('/rede/dadosjson/<cpfcnpj>')
def serve_dados_detalhes(cpfcnpj):
    return jsonify(rede_relacionamentos.jsonDados(cpfcnpj))

#https://www.techcoil.com/blog/serve-static-files-python-3-flask/

static_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static')
@app.route('/rede/static/<path:arquivopath>') #, methods=['GET'])
def serve_dir_directory_index(arquivopath):
    return send_from_directory(static_file_dir, arquivopath)

local_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'arquivos')

@app.route('/rede/arquivos_json/<arquivopath>') #, methods=['GET'])
def serve_arquivos_json(arquivopath):
    filename = secure_filename(arquivopath)
    extensao = os.path.splitext(filename)[1]
    if not extensao:
        filename += '.json'
        return send_from_directory(local_file_dir, filename)
    elif extensao =='.json':
        return send_from_directory(local_file_dir, filename)
    else:
        return Response("Solicitação não autorizada", status=400)

@app.route('/rede/arquivos_json_upload/<nomeArquivo>', methods=['POST'])
def serve_arquivos_json_upload(nomeArquivo):
    filename = secure_filename(nomeArquivo)
    if len(request.get_json())>100000:
        return jsonify({'mensagem':{'lateral':'', 'popup':'O arquivo é muito grande e não foi salvo', 'confirmar':''}})
    nosLigacoes = request.get_json()
    if usuarioLocal():
        cam = nomeArquivoNovo(os.path.join(local_file_dir, filename + '.json'))
        filename = os.path.split(cam)[1]
    else:
        filename += '.'+secrets.token_hex(10) + '.json'
        cam = os.path.join(local_file_dir, filename)  
    with open(cam, 'w') as outfile:
        json.dump(nosLigacoes, outfile)
    return jsonify({'nomeArquivoServidor':filename})

# @app.route('/rede/arquivos_download/<path:arquivopath>') #, methods=['GET'])
# def serve_arquivos_download(arquivopath):
#     if not config.par.bArquivosDownload:
#         return Response("Solicitação não autorizada", status=400)
#     pedacos = os.path.split(arquivopath)  
#     #print(f'{arquivopath=}')
#     #print(f'{pedacos=}')
#     if not pedacos[0]:
#         return send_from_directory(local_file_dir, pedacos[1]) #, as_attachment=True)
#     if not usuarioLocal():
#         return Response("Solicitação não autorizada", status=400)
#     else:
#         return send_file(arquivopath) #, as_attachment=True)

      
@app.route('/rede/dadosemarquivo/<formato>', methods = ['GET', 'POST'])
def serve_dadosEmArquivo(formato='xlsx'):
    dados = json.loads(request.form['dadosJSON'])
    return send_file(rede_relacionamentos.dadosParaExportar(dados), attachment_filename="rede_dados_cnpj.xlsx", as_attachment=True)

@app.route('/rede/formdownload.html', methods = ['GET','POST'])
def serve_form_download(): #formato='pdf'):
    return '''
        <html>
          <head></head>
          <body>
            <form id='formDownload' action="" method="POST">
              <textarea name="dadosJSON"></textarea>
            </form>
          </body>
        </html>
    '''
    
@app.route('/rede/abrir_arquivo/', methods = ['POST'])
#def serve_abrirArquivoLocal(nomeArquivo=''):
def serve_abrirArquivoLocal():
    if not config.par.bArquivosDownload:
        return Response("Solicitação não autorizada", status=400)
   # print('remote addr', request.remote_addr)
    #print('host url', request.host_url)
    lista = request.get_json()
    #print(lista)
    nomeArquivo = lista[0]
    #print(f'{nomeArquivo=}')
    if not usuarioLocal():
        print(f'serve_abrirArquivoLocal: {nomeArquivo}')
        print('operação negada.', f'{request.remote_addr}')
        return jsonify({'retorno':False, 'mensagem':'Operação não autorizada,'})
    #arquivoParaAbrir = nomeArquivo #secure_filename(nomeArquivo) 
    #if '/' not in nomeArquivo: #windows usa \
    nomeSplit = os.path.split(nomeArquivo)
    if not nomeSplit[0]: #sem caminho inteiro
        nomeArquivo = os.path.join(local_file_dir, nomeArquivo)
    extensao = os.path.splitext(nomeArquivo)[1].lower()
    print(f'serve_abrirArquivoLocal: {nomeArquivo}')
    if not os.path.exists(nomeArquivo):
        if nomeSplit[0]:
            return jsonify({'retorno':False, 'mensagem':'Arquivo não localizado,'})
        else:
            return jsonify({'retorno':False, 'mensagem':'Não foi localizado na pasta arquivos do projeto.'})
    if (extensao in ['.xls','.xlsx','.txt','.docx','.doc','.pdf', '.ppt', '.pptx', '.csv','.html','.htm','.jpg','.jpeg','.png', '.svg']) and os.path.exists(nomeArquivo):
        os.startfile(nomeArquivo)
        #return HttpResponse(json.dumps({'retorno':True}), content_type="application/json")
        return jsonify({'retorno':True, 'mensagem':'Arquivo aberto,'})
    else:
        return jsonify({'retorno':False, 'mensagem':'Extensão de arquivo não autorizada,'})

def usuarioLocal():
    return request.remote_addr ==  '127.0.0.1'

def nomeArquivoNovo(nome):
    k=1
    pedacos = os.path.splitext(nome)
    novonome = nome
    while True:
        if not os.path.exists(novonome):
            return novonome
        novonome = pedacos[0] + f"{k:04d}" +  pedacos[1]
        k += 1
        if k>100:
            print('algo errado em nomeArquivoNovo')
            break
    return nome

def removeAcentos(data):
  import unicodedata, string
  if data is None:
    return ''
  return ''.join(x for x in unicodedata.normalize('NFKD', data) if x in string.printable)

if __name__ == '__main__':
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000/rede', new=0, autoraise=True) 
    app.run(host='0.0.0.0',debug=True, use_reloader=False)
