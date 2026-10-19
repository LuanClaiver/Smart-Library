"""Testes sem alterar a biblioteca real. Rodar: python -m unittest discover -s tests -v"""
import hashlib
import http.cookiejar
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Servidor'))
import server

class FakeBrowser:
 def __init__(self,address):
  self.client_address=(address,54321)
  self.headers={}

class SecurityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='smart-library-tests-')
  cls.tmp=Path(cls.temp.name)
  cls.saved={key:getattr(server,key) for key in ('DATA','DB','PRIVATE_SETTINGS','PRIVATE_AREA_SETTINGS','MEDIA_FILTERS_FILE')}
  server.DATA=cls.tmp
  server.DB=cls.tmp/'catalog.db'
  server.PRIVATE_SETTINGS=cls.tmp/'privacidade.json'
  server.PRIVATE_AREA_SETTINGS=cls.tmp/'area_privada.json'
  server.MEDIA_FILTERS_FILE=cls.tmp/'filtros.json'
  server.PRIVATE_AREA_SETTINGS.write_text(json.dumps({'pasta':r'K:\Privado'}),encoding='utf-8')
  salt=b'0123456789abcdef';password='senha-teste-123'
  server.PRIVATE_SETTINGS.write_text(json.dumps({'salt':salt.hex(),'rounds':1000,
    'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,1000).hex()}),encoding='utf-8')
  server.init()
  with server.conn() as db:
   db.execute("INSERT INTO sources VALUES('s1',?,'Automático',1,'2026-01-01')",('K:\\',))
   db.execute("INSERT INTO sources VALUES('s2',?,'Automático',1,'2026-01-01')",('C:\\',))
   for ident,path,hidden,cat,sid in [
    ('public',r'K:\Videos\filme.mkv',0,'Filmes','s1'),
    ('private',r'K:\Privado\video.mkv',1,'Filmes','s1'),
    ('cfile',r'C:\Users\User\foto.jpg',0,'Imagens','s2')]:
    db.execute('''INSERT INTO items (id,source_id,path,name,category,kind,size,mtime,available,cover,launch_path,scanned_at,hidden,extension,ignored)
                  VALUES (?,?,?,?,?,'file',100,1,1,'','','2026-01-01',?,?,0)''',
                  (ident,sid,path,Path(path).name,cat,hidden,Path(path).suffix))
  cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
  cls.thread.start()
  cls.base='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):
  cls.http.shutdown();cls.http.server_close();cls.thread.join(3)
  for key,val in cls.saved.items():setattr(server,key,val)
  cls.temp.cleanup()
 def setUp(self):
  self.jar=http.cookiejar.CookieJar()
  self.opener=build_opener(HTTPCookieProcessor(self.jar))
  with server.SESS_LOCK:
   server.SESSIONS.clear();server.PROTECTED_SESSIONS.clear()
  with server.ACCESS_LOCK:server.ATTEMPTS.update(fail=0,until=0)
 def request(self,path,payload=None):
  data=json.dumps(payload).encode() if payload is not None else None
  req=Request(self.base+path,data=data,headers={'Content-Type':'application/json'} if data else {})
  try:
   with self.opener.open(req,timeout=4) as r:return r.status,json.load(r)
  except HTTPError as e:return e.code,json.load(e)
 def test_c_drive_restricted_only_to_remote(self):
  self.assertTrue(server.blocked_remote(FakeBrowser('192.168.0.90'),r'C:\Users\a.txt'))
  self.assertFalse(server.blocked_remote(FakeBrowser('127.0.0.1'),r'C:\Users\a.txt'))
  self.assertFalse(server.blocked_remote(FakeBrowser('192.168.0.90'),r'K:\Videos\a.mp4'))
  self.assertTrue(server.windows_system_drive('c:/windows/system32'))
 def test_admin_does_not_auto_unlock_private_area(self):
  code,data=self.request('/api/private/unlock',{'password':'senha-teste-123'})
  self.assertEqual(code,200)
  _,status=self.request('/api/private/status')
  self.assertTrue(status['unlocked'])
  self.assertFalse(status['protected_unlocked'])
  code,_=self.request('/api/items?category=Protegidos')
  self.assertEqual(code,403)
  code,_=self.request('/api/protected/unlock',{'password':'senha-teste-123'})
  self.assertEqual(code,200)
  code,data=self.request('/api/items?category=Protegidos')
  self.assertEqual(code,200)
  self.assertEqual(data['total'],1)
  code,_=self.request('/api/protected/lock',{})
  self.assertEqual(code,200)
  _,status=self.request('/api/private/status')
  self.assertTrue(status['unlocked'])
  self.assertFalse(status['protected_unlocked'])
  code,_=self.request('/api/items?category=Protegidos')
  self.assertEqual(code,403)
 def test_visitor_cannot_access_private_file(self):
  code,_=self.request('/api/local-item?id=private')
  self.assertEqual(code,404)
  code,_=self.request('/api/stream/private')
  self.assertEqual(code,404)
 def test_remote_catalog_does_not_expose_c_drive(self):
  with patch.object(server,'local_request',return_value=False):
   code,data=self.request('/api/items?category=Todos')
   self.assertEqual(code,200)
   self.assertEqual(data['total'],1)
   self.assertEqual(data['items'][0]['id'],'public')
   _,status=self.request('/api/status')
   self.assertEqual(status['total'],1)
   self.assertEqual(len(status['sources']),1)
   self.assertTrue(all(not str(i['path']).lower().startswith('c:') for i in status['sources']))
 def test_protected_requires_admin_first(self):
  code,_=self.request('/api/protected/unlock',{'password':'senha-teste-123'})
  self.assertEqual(code,403)

if __name__=='__main__':unittest.main()
