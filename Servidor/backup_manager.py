"""Backups locais consistentes: sem dependências externas.

Cada ZIP contém um snapshot SQLite válido e configurações relevantes.
Nunca inclui a coleção, miniaturas, mídia ou arquivos da quarentena.
Atenção: ZIP não é criptografado; proteja a pasta Dados/Backups no Windows.
"""
import os
import json
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path

class BackupManager:
 def __init__(self,data,db,keep=7):
  self.data=Path(data);self.db=Path(db);self.keep=keep
  self.folder=self.data/'Backups'
  self.lock=threading.Lock()

 def list_backups(self):
  if not self.folder.exists():return []
  return sorted(self.folder.glob('SmartLibrary-backup-*.zip'),reverse=True)

 def status(self):
  saved=self.list_backups()
  if not saved:return {'count':0,'last':None,'name':None}
  latest=saved[0]
  return {'count':len(saved),'last':datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec='seconds'),'name':latest.name}

 def create(self,force=False):
  with self.lock:
   self.folder.mkdir(parents=True,exist_ok=True)
   today=datetime.now().strftime('%Y%m%d')
   saved=self.list_backups()
   if not force and any(x.name.startswith('SmartLibrary-backup-'+today+'-') for x in saved):
    return next(x for x in saved if x.name.startswith('SmartLibrary-backup-'+today+'-'))
   if not self.db.is_file():raise RuntimeError('Banco de dados ainda não existe.')
   timestamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
   target=self.folder/('SmartLibrary-backup-'+timestamp+'.zip')
   temporary=target.with_suffix('.part')
   fd,tempname=tempfile.mkstemp(prefix='sl-snapshot-',suffix='.db',dir=self.folder)
   os.close(fd)
   tempdb=Path(tempname)
   try:
    # Online Backup API captura até transações em WAL sem copiar arquivos abertos.
    with sqlite3.connect(self.db,timeout=60) as origin,sqlite3.connect(tempdb) as dest:
     origin.backup(dest,pages=500,sleep=0.1)
    with sqlite3.connect(tempdb) as check:
     if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
      raise sqlite3.DatabaseError('Snapshot SQLite inválido')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
     z.write(tempdb,'biblioteca.db')
     for fname in ('privacidade.json','area_privada.json','filtros.json'):
      f=self.data/fname
      if f.is_file() and not f.is_symlink():z.write(f,fname)
     z.writestr('LEIA-ME-RESTAURAR.txt',
      'Smart Library: backup local. Pare o servico antes de restaurar.\n'
      'Guarde esta copia em local seguro: pode incluir configuracoes de acesso privado.\n'
      'Nunca publique este ZIP no GitHub.\n')
    with zipfile.ZipFile(temporary) as check:
     if check.testzip() is not None:raise OSError('ZIP não passou na verificação')
    temporary.replace(target)
    for obsolete in self.list_backups()[self.keep:]:
     try:obsolete.unlink()
     except OSError:pass
    return target
   finally:
    tempdb.unlink(missing_ok=True)
    temporary.unlink(missing_ok=True)
