"""Auxiliar interativo do Smart Library: abre o Explorador na sessão do Windows.

NÃO é serviço: precisa rodar no usuário logado. Só escuta loopback (127.0.0.1).
O cliente envia um ID; o caminho real vem do servidor catalogador (não do browser).
"""
from __future__ import annotations
import json
import os
import subprocess
import ipaddress
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlencode

AGENT_PORT = 38765
SERVER_PORT = int(os.getenv('SMART_LIBRARY_PORT', '3000'))
ALLOWED = {f'http://localhost:{SERVER_PORT}', f'http://127.0.0.1:{SERVER_PORT}'}

class Handler(BaseHTTPRequestHandler):
 def log_message(self, fmt, *args):
  pass
 def allowed(self):
  try:
   peer = ipaddress.ip_address(self.client_address[0])
   return peer.is_loopback and self.headers.get('Origin','') in ALLOWED
  except ValueError:
   return False
 def headers_cors(self, status, size=0):
  self.send_response(status)
  self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
  self.send_header('Access-Control-Allow-Credentials','true')
  self.send_header('Access-Control-Allow-Headers','Content-Type')
  self.send_header('Access-Control-Allow-Methods','POST, OPTIONS')
  self.send_header('Vary','Origin')
  self.send_header('Content-Type','application/json; charset=utf-8')
  self.send_header('Cache-Control','no-store')
  self.send_header('Content-Length',str(size))
  self.end_headers()
 def reply(self, status, data):
  raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
  self.headers_cors(status,len(raw))
  self.wfile.write(raw)
 def do_OPTIONS(self):
  if not self.allowed():self.send_error(403);return
  self.headers_cors(204)
 def do_POST(self):
  if not self.allowed() or self.path != '/open':self.send_error(403);return
  if os.name != 'nt':self.reply(400,{'error':'Disponível apenas no Windows.'});return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length<2 or length>1024:self.reply(413,{'error':'Requisição inválida.'});return
   payload=json.loads(self.rfile.read(length))
   itemid=payload.get('id','')
   if not isinstance(itemid,str) or len(itemid)>100 or not itemid:
    self.reply(400,{'error':'Item inválido.'});return
   # Valida o ID e a autorização junto ao servidor, inclusive para privados.
   url='http://127.0.0.1:'+str(SERVER_PORT)+'/api/local-item?'+urlencode({'id':itemid})
   req=Request(url,headers={'Cookie':self.headers.get('Cookie',''),'User-Agent':'SmartLibraryLocalAgent/1.0.15'})
   with urlopen(req,timeout=7) as resp:data=json.load(resp)
   path=data.get('path','')
   if not path or not os.path.exists(path):
    self.reply(404,{'error':'Arquivo ou pasta indisponível.'});return
   if data.get('kind')=='folder':args=['explorer.exe',path]
   else:args=['explorer.exe','/select,',path]
   subprocess.Popen(args)
   self.reply(200,{'ok':True})
  except Exception as exc:
   self.reply(502,{'error':'Não foi possível abrir pelo Auxiliar Local: '+str(exc)[:150]})

def main():
 if os.name!='nt':
  print('O Auxiliar Local é exclusivo do Windows.')
  return
 print('Smart Library - Auxiliar Local ativo na porta',AGENT_PORT,flush=True)
 try:
  with ThreadingHTTPServer(('127.0.0.1',AGENT_PORT),Handler) as server:
   server.serve_forever()
 except OSError as exc:
  # Outro auxiliar já aberto: evitar duas instâncias.
  print('Auxiliar indisponível (talvez já esteja aberto):',exc)

if __name__=='__main__':main()
