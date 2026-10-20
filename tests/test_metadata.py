"""Testes de reconhecimento e metadados sem rede e sem arquivos pessoais."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Servidor'))
import server
import metadata_catalog as meta

class ParsingTests(unittest.TestCase):
 def test_episode_name(self):
  result=meta.parse_local('K:/Series/The Last of Us.S02E03.1080p.WEB-DL.mkv','Séries')
  self.assertEqual(result['season'],2)
  self.assertEqual(result['episode'],3)
  self.assertEqual(result['series_title'],'The Last of Us')
 def test_season_folder(self):
  result=meta.parse_local('K:/Séries/Breaking Bad/Temporada 03/Capítulo 09.mkv','Séries')
  self.assertEqual(result['season'],3)
  self.assertEqual(result['series_title'],'Breaking Bad')
 def test_movie_year(self):
  r=meta.parse_local('D:/Filmes/Oppenheimer.2023.2160p.mkv','Filmes')
  self.assertEqual(r['year'],2023)
  self.assertEqual(r['title'],'Oppenheimer 2023')
 def test_match_avoids_wrong_title(self):
  self.assertGreater(meta.confidence('Baldurs Gate 3','Baldur’s Gate 3'),0.8)
  self.assertLess(meta.confidence('Harry Potter','Kung Fu Panda'),0.5)
 def test_fixed_data_sources_only(self):
  with patch.object(meta,'search_steam',return_value=[meta._normal_result('Portal 2',provider='Steam')]):
   results=meta.lookup('Portal 2','Jogos')['results']
   self.assertEqual(results[0]['confidence'],1)
  with self.assertRaises(ValueError):meta.lookup('Portal 2','Documentos')
 def test_reject_untrusted_metadata(self):
  with self.assertRaises(ValueError):server._safe_metadata_choice({'title':'a','provider':'unknown'})
  data=server._safe_metadata_choice({'title':'a','provider':'Steam','cover':'file:///C:/secret.txt'})
  self.assertEqual(data['cover'],'')

class MigrationTests(unittest.TestCase):
 def test_scan_populates_episodes_and_preserves_custom_cover(self):
  with tempfile.TemporaryDirectory() as work:
   root=Path(work);folder=root/'media';folder.mkdir()
   s={k:getattr(server,k) for k in ('DATA','DB','PRIVATE_SETTINGS','PRIVATE_AREA_SETTINGS','MEDIA_FILTERS_FILE')}
   try:
    server.DATA=root;server.DB=root/'database.db';server.PRIVATE_SETTINGS=root/'privacidade.json';server.PRIVATE_AREA_SETTINGS=root/'area_privada.json';server.MEDIA_FILTERS_FILE=root/'filtros.json'
    server.init()
    with server.conn() as db:db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('abc',str(folder),'Séries',1,'2026-01-01'))
    episode=folder/'Super Série.S01E05.mkv';episode.write_bytes(b'video')
    server.scan_worker()
    with server.conn() as db:
     row=dict(db.execute('SELECT * FROM items').fetchone())
     self.assertEqual((row['series_title'],row['season'],row['episode']),('Super Série',1,5))
     self.assertEqual(row['metadata_json'],'')
     db.execute("UPDATE items SET cover='https://example.com/manual.jpg' WHERE id=?",(row['id'],))
    server.scan_worker()
    with server.conn() as db:
     again=dict(db.execute('SELECT * FROM items').fetchone())
     self.assertEqual(again['cover'],'https://example.com/manual.jpg')
     self.assertEqual(again['episode'],5)
   finally:
    for k,v in s.items():setattr(server,k,v)
if __name__=='__main__':unittest.main()

# End-to-end API checks reuse authentication fixtures from test_security.
from test_security import SecurityTests as _ApiFixture
class MetadataApiTests(_ApiFixture):
 def test_private_metadata_not_sent(self):
  self.request('/api/private/unlock',{'password':'senha-teste-123'})
  with patch.object(server,'lookup_metadata') as external:
   code,_=self.request('/api/metadata/search',{'id':'private'})
   self.assertEqual(code,404) # not even exposed before Protegidos confirmation
   self.assertFalse(external.called)
 def test_admin_can_select_metadata_without_replacing_existing_cover(self):
  self.request('/api/private/unlock',{'password':'senha-teste-123'})
  with patch.object(server,'lookup_metadata',return_value={'results':[{'title':'Filme de teste','cover':'https://example.com/image.jpg','confidence':1}], 'query':'Filme de teste','errors':[]}):
   code,data=self.request('/api/metadata/search',{'id':'public','query':'Filme de teste'})
   self.assertEqual(code,200)
   self.assertEqual(data['results'][0]['title'],'Filme de teste')
  with server.conn() as db:db.execute("UPDATE items SET cover='https://example.com/manual.jpg' WHERE id='public'")
  code,data=self.request('/api/metadata/apply',{'id':'public','choice':{'provider':'iTunes','title':'Filme de teste','cover':'https://example.com/new.jpg','year':2024},'replace_cover':False})
  self.assertEqual(code,200)
  with server.conn() as db:
   item=db.execute("SELECT cover,metadata_json FROM items WHERE id='public'").fetchone()
   self.assertEqual(item['cover'],'https://example.com/manual.jpg')
   self.assertEqual(json.loads(item['metadata_json'])['year'],2024)
 def test_visitor_cannot_start_bulk_metadata(self):
  code,_=self.request('/api/metadata/auto',{'limit':1})
  self.assertEqual(code,403)
