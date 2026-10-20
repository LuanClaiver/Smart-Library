"""Regressões de catálogo e backups; não dependem de um disco real do Windows."""
import os
import sys
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Servidor'))
import server
from backup_manager import BackupManager

class BackupTests(unittest.TestCase):
 def test_backup_consistente_sem_midias_e_rotacao(self):
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory);db=folder/'biblioteca.db'
   with sqlite3.connect(db) as c:
    c.execute('CREATE TABLE registros(valor TEXT)')
    c.execute('INSERT INTO registros VALUES (?)',('preservado',))
   (folder/'privacidade.json').write_text('{"exemplo":1}',encoding='utf-8')
   (folder/'Miniaturas').mkdir()
   (folder/'Miniaturas'/'privado.jpg').write_bytes(b'NEVER-EXPORT')
   manager=BackupManager(folder,db,keep=2)
   one=manager.create()
   self.assertEqual(one,manager.create())  # um backup diario
   self.assertEqual(manager.status()['count'],1)
   with zipfile.ZipFile(one) as z:
    self.assertEqual(z.testzip(),None)
    self.assertIn('biblioteca.db',z.namelist())
    self.assertIn('privacidade.json',z.namelist())
    self.assertNotIn('Miniaturas/privado.jpg',z.namelist())
    restored=folder/'restaurado.db'
    restored.write_bytes(z.read('biblioteca.db'))
   with sqlite3.connect(restored) as c:
    self.assertEqual(c.execute('SELECT valor FROM registros').fetchone()[0],'preservado')
   manager.create(force=True);manager.create(force=True)
   self.assertEqual(manager.status()['count'],2)

class ScanTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='sl-scan-')
  self.base=Path(self.temp.name)
  self.folder=self.base/'media';self.folder.mkdir()
  self.saved={name:getattr(server,name) for name in ('DATA','DB','PRIVATE_SETTINGS','PRIVATE_AREA_SETTINGS','MEDIA_FILTERS_FILE')}
  server.DATA=self.base
  server.DB=self.base/'biblioteca.db'
  server.PRIVATE_SETTINGS=self.base/'privacidade.json'
  server.PRIVATE_AREA_SETTINGS=self.base/'area_privada.json'
  server.MEDIA_FILTERS_FILE=self.base/'filtros.json'
  server.init()
  with server.conn() as c:
   c.execute('INSERT INTO sources VALUES (?,?,?,?,?)',('src',str(self.folder),'Automático',1,'2026-10-01'))
  server.STATE.update(running=False,error='',sources_ok=0,sources_failed=0,sources_offline=0,entries_removed=0)
 def tearDown(self):
  for k,v in self.saved.items():setattr(server,k,v)
  self.temp.cleanup()
 def paths(self):
  with server.conn() as c:return {r['path']:dict(r) for r in c.execute('SELECT * FROM items')}
 def test_scan_completo_remove_somente_arquivos_desaparecidos(self):
  first=self.folder/'filme.mp4';first.write_bytes(b'video')
  other=self.folder/'retirado.mp3';other.write_bytes(b'music')
  server.scan_worker()
  self.assertEqual(len(self.paths()),2)
  with server.conn() as c:c.execute('UPDATE items SET category_override=? WHERE path=?',('Vídeos',str(first)))
  other.unlink();server.scan_worker()
  self.assertEqual(list(self.paths()),[str(first)])
  self.assertEqual(self.paths()[str(first)]['category_override'],'Vídeos')
  self.assertEqual(server.STATE['sources_ok'],2)
 def test_fonte_offline_nao_perde_catalogo(self):
  file=self.folder/'musica.mp3';file.write_bytes(b'x')
  server.scan_worker()
  self.folder.rename(self.base/'desconectado')
  server.scan_worker()
  self.assertIn(str(file),self.paths())
  self.assertEqual(self.paths()[str(file)]['available'],0)
  self.assertEqual(server.STATE['sources_offline'],1)
 def test_erro_de_leitura_preserva_itens_anteriores(self):
  first=self.folder/'original.mp4';first.write_bytes(b'x')
  server.scan_worker()
  original_walk=server.os.walk
  def broken_walk(*args,**kwargs):
   onerror=kwargs.get('onerror')
   if onerror:onerror(PermissionError('acesso negado'))
   return iter(())
  with patch.object(server.os,'walk',side_effect=broken_walk):
   server.scan_worker()
  self.assertIn(str(first),self.paths())
  self.assertEqual(server.STATE['sources_failed'],1)

if __name__=='__main__':unittest.main()
