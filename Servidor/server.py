"""Smart Library v1.0.15 — biblioteca local do Windows, sem dependências externas."""
from __future__ import annotations
import os, sys, json, sqlite3, threading, mimetypes, subprocess, re, shutil, time, uuid, webbrowser, secrets, hashlib, hmac, http.cookies, functools, ntpath, socket
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote, urlencode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from duplicate_finder import DuplicateFinder

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'Dados'
DB = DATA / 'biblioteca.db'
PRIVATE_SETTINGS=DATA / 'privacidade.json'
THUMBS=DATA / 'Miniaturas'
THUMBS.mkdir(exist_ok=True)

def protect_thumbnail_cache():
 """Esconde somente o cache, sem modificar a coleção original.

 Itens protegidos deixam de gerar miniaturas persistentes. Removemos uma
 vez os thumbnails antigos porque eles podem incluir cenas privadas.
 """
 marker=DATA/'.cache_privado_corrigido_v107'
 if not marker.exists():
  for file in THUMBS.iterdir():
   try:
    if file.is_file() and not file.is_symlink() and file.suffix.casefold() in {'.jpg','.jpeg','.webp','.png'}:
     file.unlink()
   except OSError:pass
  try:marker.write_text('Cache recriado sem imagens de itens protegidos.\n',encoding='utf-8')
  except OSError:pass
 if os.name=='nt':
  try:
   import ctypes
   fn=ctypes.windll.kernel32.GetFileAttributesW
   fn.argtypes=[ctypes.c_wchar_p];fn.restype=ctypes.c_uint32
   flags=fn(str(THUMBS))
   if flags!=0xffffffff:
    set_attrs=ctypes.windll.kernel32.SetFileAttributesW
    set_attrs.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32]
    set_attrs.restype=ctypes.c_int
    # HIDDEN (0x2) + SYSTEM (0x4); atributos já existentes preservados.
    if not set_attrs(str(THUMBS),flags|0x2|0x4):
     print('[AVISO] Não foi possível ocultar a pasta Miniaturas.',flush=True)
  except (OSError,ValueError,AttributeError):pass
SESSIONS={}
PROTECTED_SESSIONS={}
SESS_LOCK=threading.Lock()
ACCESS_LOCK=threading.Lock()
ATTEMPTS={'fail':0,'until':0}
WEBROOT = ROOT / 'Interface'
WEB = WEBROOT / 'index.html'
DATA.mkdir(exist_ok=True)
PORT = int(os.environ.get('SMART_LIBRARY_PORT', '3000'))
HOST = os.environ.get('SMART_LIBRARY_HOST', '0.0.0.0' if SERVICE_MODE else '127.0.0.1') if 'SERVICE_MODE' in globals() else '127.0.0.1'  # inicializado novamente apos SERVICE_MODE
EXT = {
 'Filmes': {'.mp4','.mkv','.avi','.mov','.wmv','.m4v','.webm','.mpg','.mpeg','.ts'},
 'Músicas': {'.mp3','.flac','.wav','.m4a','.aac','.ogg','.wma','.opus'},
 'Imagens': {'.jpg','.jpeg','.png','.webp','.gif','.bmp','.tiff'},
 'Documentos': {'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.md','.csv'},
 'Instaladores': {'.iso','.exe','.msi','.zip','.7z','.rar','.bat'},
}
# Arquivos de suporte de jogos devem existir no disco mas nao poluir a biblioteca.
# A regra preserva pastas de jogos, ISOs de instalacao e fontes de midia pessoais.
MEDIA_FILTERS_FILE = DATA / 'filtros.json'
# Nomes de bibliotecas e diretórios técnicos conhecidos. Não confundir uma pasta
# pessoal com bibliotecas de programas somente por conter a palavra "games".
STEAM_PATH_NAMES = {
 'steam','steamlibrary','steamapps','steam games','steamgames','steamuser',
 'steam client','steam epic','epic games','epicgames','epic games launcher',
 'gog games','goggames','gog galaxy','ubisoft game launcher','ea games',
 'electronic arts','ea app','battle.net','battle net','rockstar games',
 'rockstar games launcher','riot games','xboxgames','xbox games',
 'origin games','origin','ubisoft connect','bethesda.net launcher'
}
GAME_ROOT_NAMES = {'jogos','games','meus jogos','my games','steam games','steamgames',
 'games and jogos','biblioteca de jogos','game library','jogos pc','pc games',
 'jogos instalados','steam epic'}
GAME_ASSET_NAMES = {'assets','asset','resources','resource','textures','texture','sprites','sprite',
 'sound','sounds','sfx','audio','bgm','gameassets','game_assets','streamingassets',
 'sharedassets','game_data','www','engine','content','data','pak','localization',
 'localisation','screenshots','shadercache','compatdata','workshop','steamui',
 'appcache','librarycache','resource','resource2','public','cache','caches',
 'depotcache','package','config','logs','userdata','steamui','store','webcache',
 'binaries','redist','__installer','_commonredist','movies','cutscenes','locales','common'}
GAME_INTERNAL_EXT = (EXT['Imagens'] | EXT['Músicas'] | EXT['Filmes'] | EXT['Documentos'] |
                     EXT['Instaladores'] | {'.jfif','.heic','.avif','.svg','.mp2','.mid','.midi',
                     '.aiff','.ape','.ac3','.wem','.bank','.fsb','.bik','.json','.xml','.ini',
                     '.dll','.pak','.dat','.log','.vdf','.manifest','.vpk','.pck','.dds',
                     '.unity3d','.bundle','.asset','.assets','.cfg','.yml','.yaml','.db','.sqlite'})


def read_media_filters():
 try:
  value=json.loads(MEDIA_FILTERS_FILE.read_text(encoding='utf-8'))
  if isinstance(value,dict) and type(value.get('ocultar_midias_steam')) is bool:
   return {'ocultar_midias_steam':value['ocultar_midias_steam']}
 except (OSError,ValueError):pass
 return {'ocultar_midias_steam':True}


def is_internal_game_media(path,kind='file',enabled=None,source_category='Automático',source_root=''):
 """Oculta APENAS a apresentação de recursos técnicos de jogos/launchers.

 Usa os diretórios conhecidos e as subpastas internas. Mesmo fontes explicitamente
 cadastradas como Imagens não devem fazer fotos do cache Steam/Epic aparecerem.
 Sem alteração física no disco. Não marca itens como 'Protegidos'.
 """
 if enabled is None:enabled=read_media_filters()['ocultar_midias_steam']
 # Pastas tecnicas herdadas dos escaneamentos antigos (inclusive em Protegidos).
 # Elas devem sumir do catalogo normal, mas nao sao apagadas do disco.
 system_dirs={'$recycle.bin','system volume information','.smartlibrary-quarentena'}
 if any(x.casefold().strip() in system_dirs for x in re.split(r'[\\/]+',str(path))):return True
 if kind!='file':return False
 if not enabled:return False
 try:
  pieces=[x.casefold().strip().rstrip(' .') for x in re.split(r'[\\/]+',str(path)) if x.strip()]
  if len(pieces)<2:return False
  ext=Path(pieces[-1]).suffix.casefold()
  # Arquivos desconhecidos não poluem as categorias de mídia; continuam em Outros
  # quando não estiverem associados a jogos.
  dirs=pieces[:-1]
  root_dirs=[x.casefold().strip() for x in re.split(r'[\\/]+',str(source_root)) if x.strip()]
  # Alguns nomes combinados são comuns nas bibliotecas pessoais (ex.: H:\Steam Epic).
  # Identificação por *parte inteira*, não por palavras soltas no nome do arquivo.
  launcher=any((d in STEAM_PATH_NAMES or d.startswith(('steamlibrary','steamapps','epic games launcher')))
               for d in dirs)
  library=any(d in GAME_ROOT_NAMES for d in dirs)
  technical=any((d in GAME_ASSET_NAMES or d.endswith(('_data','_data~','-win64-shipping')))
                for d in dirs)
  if not (launcher or library):return False
  # Evita sumir com jogos e instaladores da raiz de uma pasta cadastrada para Jogos.
  if source_category=='Jogos' and ext in {'.exe','.msi','.iso','.cue','.bin','.img','.nrg','.mdf','.zip','.7z','.rar'}:
   if len(pieces)==len(root_dirs)+1 and pieces[:len(root_dirs)]==root_dirs:return False
  # Respeita fontes pessoais explicitamente separadas, exceto dentro das pastas
  # técnicas reconhecidas do launcher (Steam\appcache, Epic\Cache etc.).
  personal_source=source_category in {'Filmes','Séries','Músicas','Imagens','Documentos'}
  if personal_source and not launcher and not technical:return False
  # Uma biblioteca de jogos/launcher nunca deve despejar áudios, capas, PDFs ou
  # arquivos de engine na biblioteca de mídia. A regra é conservadora e editável.
  return ext in GAME_INTERNAL_EXT or bool(ext)
 except (OSError,ValueError,TypeError):return False


def refresh_media_visibility():
 enabled=read_media_filters()['ocultar_midias_steam']
 with conn() as db:
  rows=db.execute('''SELECT i.id,i.path,i.kind,i.ignored,s.category AS source_category,s.path AS source_root
                     FROM items i JOIN sources s ON i.source_id=s.id''').fetchall()
  changes=[]
  for row in rows:
   val=int(is_internal_game_media(row['path'],row['kind'],enabled,row['source_category'],row['source_root']) or (Path(row['path']).exists() and ignored_hidden_elsewhere(row['path'],row['source_root'])))
   if val!=row['ignored']:changes.append((val,row['id']))
  if changes:db.executemany('UPDATE items SET ignored=? WHERE id=?',changes)
 return len(changes)


def update_media_filters(enabled):
 if type(enabled) is not bool:raise ValueError('Use verdadeiro ou falso.')
 tmp=MEDIA_FILTERS_FILE.with_suffix('.tmp')
 tmp.write_text(json.dumps({'ocultar_midias_steam':enabled},ensure_ascii=False,indent=2),encoding='utf-8')
 tmp.replace(MEDIA_FILTERS_FILE)
 return refresh_media_visibility()

EXCLUDE_DIRS = {'.smartlibrary-quarentena','$recycle.bin','system volume information','windows','program files','program files (x86)','programdata','appdata','.git','node_modules','$windows.~bt'}
CAT = {'Jogos','Filmes','Séries','Músicas','Vídeos','Imagens','Documentos','Instaladores','Outros','Automático'}
LOCK = threading.Lock()
FS_LOCK = threading.RLock()
STATE = {'running':False,'processed':0,'found':0,'current':'','error':'','finished_at':None}
SERVICE_MODE=os.environ.get('SMART_LIBRARY_SERVICE')=='1'
HOST=os.environ.get('SMART_LIBRARY_HOST', '0.0.0.0' if SERVICE_MODE else '127.0.0.1')

def conn():
 c=sqlite3.connect(DB,timeout=30)
 c.row_factory=sqlite3.Row
 c.execute('PRAGMA journal_mode=WAL')
 return c

# Somente entradas REALMENTE ocultas dentro da biblioteca registrada.
# Nao verificar a raiz da unidade nem pastas ancestrais fora da fonte:
# o atributo Hidden nessas pastas nao pode esconder toda a colecao.
@functools.lru_cache(maxsize=80000)
def has_hidden_attribute(path):
 p=Path(path)
 if os.name == 'nt':
  try:
   import ctypes
   fn=ctypes.windll.kernel32.GetFileAttributesW
   fn.argtypes=[ctypes.c_wchar_p];fn.restype=ctypes.c_uint32
   attributes=fn(str(p))
   return attributes!=0xFFFFFFFF and bool(attributes & 0x2)
  except (OSError,ValueError):return False
 # Compatibilidade em outros sistemas: arquivos com ponto inicial.
 return p.name.startswith('.') and p.name not in ('.','..')

def is_hidden_path(path, source_root=None):
 p=Path(path)
 if source_root is not None:
  root=Path(source_root)
  try:parts=p.relative_to(root).parts
  except ValueError:return True
  # O atributo da raiz cadastrada também é relevante se ela própria for oculta.
  # Não consultar ancestrais ACIMA da raiz: assim não ocultamos um disco inteiro.
  if has_hidden_attribute(root):return True
  for i in range(1,len(parts)+1):
   if has_hidden_attribute(root.joinpath(*parts[:i])):return True
  return False
 for ancestor in (p,*p.parents):
  if has_hidden_attribute(ancestor):return True
 return False

# ÚNICO diretório confidencial da coleção, definido pelo proprietário. Não
# depende das flags antigas persistidas no SQLite ou da disponibilidade do HD.
PRIVATE_AREA_DEFAULT = ''  # Configure a pasta privada em Dados/area_privada.json
PRIVATE_AREA_SETTINGS = DATA / 'area_privada.json'
def private_media_root():
 try:
  cfg=json.loads(PRIVATE_AREA_SETTINGS.read_text(encoding='utf-8'))
  if isinstance(cfg,dict) and isinstance(cfg.get('pasta'),str) and cfg['pasta'].strip():return cfg['pasta'].strip()
 except (OSError,ValueError):pass
 return PRIVATE_AREA_DEFAULT

def in_private_folder(path):
 # Normalização Windows independente do SO onde os testes são executados.
 a=ntpath.normcase(ntpath.normpath(str(path).replace('/', chr(92)))).rstrip(chr(92))
 configured=private_media_root().strip()
 if not configured:return False
 b=ntpath.normcase(ntpath.normpath(configured.replace('/', chr(92)))).rstrip(chr(92))
 return a==b or a.startswith(b+chr(92))

def hidden_for_item(item_path, source_path):
 # Apenas o caminho configurado como privado vai para Protegidos; nunca usar o bit legado do banco.
 return int(in_private_folder(item_path))

def ignored_hidden_elsewhere(path, source_root):
 # Outros arquivos genuinamente ocultos do Windows não entram no catálogo
 # nem na área Protegidos. A área configurada permanece protegida, mesmo offline.
 if in_private_folder(path):return False
 try:
  root=Path(source_root)
  parts=Path(path).relative_to(root).parts
 except (ValueError,OSError):return has_hidden_attribute(path)
 # Ignorar a flag da raiz cadastrada: drives inteiros cadastrados em fontes
 # antigas podem ter sido marcados hidden e isso nao pode sumir com a colecao.
 for count in range(1,len(parts)+1):
  if has_hidden_attribute(root.joinpath(*parts[:count])):return True
 return False



def private_config():
 try:return json.loads(PRIVATE_SETTINGS.read_text(encoding='utf-8'))
 except (OSError,ValueError):return None

def check_password(password, cfg):
 try:
  calc=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(cfg['salt']),int(cfg['rounds']))
  return hmac.compare_digest(calc.hex(),cfg['hash'])
 except (ValueError,TypeError,KeyError):return False

def current_token(h):
 try:
  jar=http.cookies.SimpleCookie();jar.load(h.headers.get('Cookie',''))
  return jar['sl_admin'].value if 'sl_admin' in jar else ''
 except Exception:return ''

def unlocked(h):
 tok=current_token(h)
 if not tok:return False
 with SESS_LOCK:
  entry=SESSIONS.get(tok,(0,''))
  until, signature = entry if isinstance(entry,tuple) else (0,'')
  cfg=private_config()
  active_signature=cfg.get('hash','') if cfg else ''
  if until<time.time() or signature!=active_signature:
   SESSIONS.pop(tok,None)
   return False
  return True

def grant(h):
 tok=secrets.token_urlsafe(32)
 cfg=private_config()
 with SESS_LOCK:SESSIONS[tok]=(time.time()+1800,cfg.get('hash','') if cfg else '')
 return f'sl_admin={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800'

def local_request(h):
 return h.client_address[0] in ('127.0.0.1', '::1', '::ffff:127.0.0.1')

def windows_system_drive(path):
 # Funciona tambem nos testes em Linux; bloqueia somente a unidade C:.
 try:
  drive, _ = ntpath.splitdrive(ntpath.normpath(str(path).replace('/', chr(92))))
  return drive.casefold() == 'c:'
 except (ValueError, TypeError):return False

def blocked_remote(h, path):
 if local_request(h):return False
 if windows_system_drive(path):return True
 # Também impede acessar C: por uma junção/symlink de outra unidade no Windows.
 try:
  return windows_system_drive(str(Path(path).resolve(strict=False)))
 except (ValueError,OSError,RuntimeError):return False

def private_token(h):
 try:
  jar=http.cookies.SimpleCookie();jar.load(h.headers.get('Cookie',''))
  return jar['sl_protected'].value if 'sl_protected' in jar else ''
 except Exception:return ''

def protected_unlocked(h):
 if not unlocked(h):return False
 token=private_token(h)
 if not token:return False
 with SESS_LOCK:
  entry=PROTECTED_SESSIONS.get(token,(0,''))
  cfg=private_config()
  ok=entry[0]>time.time() and cfg and entry[1]==cfg.get('hash','')
  if not ok:PROTECTED_SESSIONS.pop(token,None)
  return bool(ok)

def grant_protected(h):
 token=secrets.token_urlsafe(32)
 cfg=private_config()
 with SESS_LOCK:
  PROTECTED_SESSIONS[token]=(time.time()+600,cfg.get('hash','') if cfg else '')
 return f'sl_protected={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=600'

def protected_lock(h):
 with SESS_LOCK:PROTECTED_SESSIONS.pop(private_token(h),None)
 return 'sl_protected=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'

def is_allowed(h, item):
 return item is not None and not blocked_remote(h,item['path']) and (not item['hidden'] or protected_unlocked(h))

def guarded_item(h, itemid):
 it=item_by_id(itemid)
 return it if is_allowed(h,it) else None

# Heurísticas conservadoras: o status não garante que um jogo esteja instalado.
GAME_GROUPS={'luta','fps','rpg','ação','acao','aventura','aventuras','corrida','esporte','esportes','estratégia','estrategia','simulador','simulação','simulacao','indie','terror','shooters','racing','fighting','jogos','games'}
INSTALL_EXT={'.iso','.cue','.bin','.img','.nrg','.mdf','.zip','.7z','.rar'}
IGNORE_EXE={'setup','install','uninstall','unins000','update','updater','crashreporter','launcherhelper','vc_redist','dxsetup','unitycrashhandler64','unitycrashhandler32'}
VIDEO_EXT=EXT['Filmes']

def game_probe(folder):
 """Inspeciona poucos níveis para não confundir assets e bibliotecas com jogos."""
 files=[]; subdirs=[]
 try:
  with os.scandir(folder) as it:
   for ent in it:
    try:
     if ent.is_symlink():continue
     if ent.is_file():files.append(ent.name)
     elif ent.is_dir():subdirs.append(ent.name)
    except OSError:continue
 except OSError:return 'Verificar',False
 # Categorias LUTA/FPS são pastas de agrupamento, nunca jogos individuais.
 if folder.name.casefold().strip() in GAME_GROUPS:return '',True
 installer=any(Path(n).suffix.lower() in INSTALL_EXT for n in files)
 installer|=any(n.casefold().startswith(('setup.','install.','autorun.')) for n in files)
 game_exe=any(Path(n).suffix.lower()=='.exe' and not any(Path(n).stem.casefold().startswith(x) for x in IGNORE_EXE) for n in files)
 if not installer and not game_exe:
  # Jogo pode manter o executável em Binaries/Win64; procurar só um segundo nível.
  for dirname in subdirs[:16]:
   if dirname.casefold() in {'binaries','bin','win64','win32','game','x64','x86'}:
    try:
     for f in (folder/dirname).rglob('*.exe'):
      if len(f.relative_to(folder).parts)>4:continue
      if not any(f.stem.casefold().startswith(x) for x in IGNORE_EXE):game_exe=True;break
    except OSError:pass
    if game_exe:break
 # Se é uma subcategoria reconhecida por múltiplas pastas e sem arquivos significativos.
 if not installer and not game_exe and len(subdirs)>=2 and not files:
  # Só agrupa se pelo menos duas subpastas parecem jogos; evita confundir assets.
  candidates=0
  for sub in subdirs[:30]:
   try:
    if any(x.is_file() and (x.suffix.lower() in INSTALL_EXT or x.suffix.lower()=='.exe') for x in (folder/sub).iterdir()):candidates+=1
   except OSError:continue
   if candidates>=2:return '',True
 if installer:return 'Para instalar',False
 if game_exe:return 'Instalados',False
 return 'Verificar',False

def game_entries(root, recursive):
 """Produz jogos reais sem cadastrar pastas agrupadoras como LUTA."""
 try:direct=list(root.iterdir())
 except OSError:return
 def descend(folder, depth):
  status,is_group=game_probe(folder)
  if is_group:
   if depth<4 and recursive:
    try:children=sorted((x for x in folder.iterdir() if x.is_dir() and not x.is_symlink()),key=lambda x:x.name.casefold())
    except OSError:children=[]
    for child in children:yield from descend(child,depth+1)
   return
  yield folder,'folder',status
 for ent in sorted(direct,key=lambda x:x.name.casefold()):
  try:
   if ent.is_symlink():continue
   if ent.is_dir():yield from descend(ent,0)
   elif ent.is_file() and ent.suffix.casefold() in INSTALL_EXT|{'.exe','.msi'}:
    # ISOs e instaladores avulsos também são jogos para instalar.
    yield ent,'file','Para instalar'
  except OSError:continue

def local_poster(h,item):
 """Mostra capa existente na pasta, sem baixar ou executar arquivos externos."""
 if not is_allowed(h,item):return json_reply(h,{'error':'Nao encontrado'},404)
 loc=Path(item['path'])
 if not loc.exists():return json_reply(h,{'error':'Arquivo indisponivel'},404)
 if item['kind']=='folder':folder=loc
 else:folder=loc.parent
 names=['cover.jpg','cover.jpeg','cover.png','poster.jpg','poster.png','folder.jpg','folder.png','capa.jpg','capa.png']
 candidates=[folder/n for n in names]
 if item['kind']=='file':candidates.extend(folder/(loc.stem+ext) for ext in ('.jpg','.png','.jpeg','.webp'))
 candidates.extend(folder/n for n in ['cover.webp','poster.webp','folder.webp'])
 match=next((f for f in candidates if f.is_file() and not f.is_symlink()),None)
 if not match:return json_reply(h,{'error':'Sem capa local'},404)
 with conn() as db:
  source=db.execute('SELECT path FROM sources WHERE id=?',(item['source_id'],)).fetchone()
 if not source or is_hidden_path(str(match),source['path']) and not unlocked(h):return json_reply(h,{'error':'Nao encontrado'},404)
 try:
  if match.stat().st_size>8*1024*1024:return json_reply(h,{'error':'Capa muito grande'},400)
  b=match.read_bytes()
 except OSError:return json_reply(h,{'error':'Arquivo nao acessivel'},404)
 typ=mimetypes.guess_type(str(match))[0] or 'image/jpeg'
 h.send_response(200);h.send_header('Content-Type',typ);h.send_header('Cache-Control','no-store' if item['hidden'] else 'private, max-age=300');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Content-Length',str(len(b)));h.end_headers();h.wfile.write(b)

def save_cover_thumbnail(h, item):
 """Gera miniaturas sem gravar no disco quando o vídeo é protegido."""
 if not is_allowed(h,item) or item['kind']!='file' or Path(item['path']).suffix.lower() not in VIDEO_EXT:
  return json_reply(h,{'error':'Não encontrado'},404)
 path=Path(item['path'])
 if not path.is_file():return json_reply(h,{'error':'Mídia indisponível'},404)
 ffmpeg=shutil.which('ffmpeg')
 local=ROOT/'Ferramentas'/'ffmpeg.exe'
 if not ffmpeg and local.exists():ffmpeg=str(local)
 if not ffmpeg:return json_reply(h,{'error':'FFmpeg não encontrado'},404)
 private=bool(item['hidden'])
 try:
  base=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-ss','00:00:02','-i',str(path),'-frames:v','1','-vf','scale=480:-2','-q:v','4']
  if private:
   # PIPE: não grava qualquer quadro sensível em Dados/Miniaturas.
   proc=subprocess.run(base+['-f','image2pipe','-vcodec','mjpeg','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if proc.returncode or not proc.stdout or len(proc.stdout)>5*1024*1024:
    return json_reply(h,{'error':'Não foi possível gerar miniatura'},404)
   data=proc.stdout
  else:
   stat=path.stat()
   key=hashlib.sha256((str(path)+':'+str(stat.st_size)+':'+str(stat.st_mtime_ns)).encode()).hexdigest()
   dest=THUMBS/(key+'.jpg')
   if not dest.exists():
    proc=subprocess.run(base+[str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if proc.returncode or not dest.is_file():return json_reply(h,{'error':'Não foi possível gerar miniatura'},404)
   data=dest.read_bytes()
 except (OSError,subprocess.TimeoutExpired):return json_reply(h,{'error':'Falha na geração da miniatura'},404)
 h.send_response(200)
 h.send_header('Content-Type','image/jpeg')
 h.send_header('Cache-Control','no-store' if private else 'private, max-age=3600')
 h.send_header('X-Content-Type-Options','nosniff')
 h.send_header('Content-Length',str(len(data)))
 h.end_headers();h.wfile.write(data)

def init():
 with conn() as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,path TEXT NOT NULL UNIQUE,category TEXT NOT NULL,recursive INTEGER NOT NULL,created TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,path TEXT NOT NULL UNIQUE,name TEXT NOT NULL,category TEXT NOT NULL,kind TEXT NOT NULL,size INTEGER NOT NULL,mtime REAL NOT NULL,available INTEGER NOT NULL DEFAULT 1,cover TEXT DEFAULT '',launch_path TEXT DEFAULT '',scanned_at TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS ix_items_category ON items(category);
  CREATE INDEX IF NOT EXISTS ix_items_source ON items(source_id);
  CREATE TABLE IF NOT EXISTS quarantine(id TEXT PRIMARY KEY,original_path TEXT NOT NULL,stored_path TEXT NOT NULL,source_id TEXT NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,size INTEGER NOT NULL,created_at TEXT NOT NULL);
  ''')
  cols={r[1] for r in c.execute('PRAGMA table_info(items)')}
  if 'hidden' not in cols:
   c.execute('ALTER TABLE items ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
   # Dados antigos: recalcula atributos do Windows. Arquivos desconectados ficam protegidos.
   for row in c.execute('SELECT id,path FROM items').fetchall():
    hidden=1 if not Path(row['path']).exists() else int(is_hidden_path(row['path']))
    c.execute('UPDATE items SET hidden=? WHERE id=?',(hidden,row['id']))
  if 'game_status' not in cols:c.execute("ALTER TABLE items ADD COLUMN game_status TEXT NOT NULL DEFAULT ''")
  if 'game_status_override' not in cols:c.execute("ALTER TABLE items ADD COLUMN game_status_override TEXT NOT NULL DEFAULT ''")
  if 'extension' not in cols:c.execute("ALTER TABLE items ADD COLUMN extension TEXT NOT NULL DEFAULT ''")
  if 'category_override' not in cols:c.execute("ALTER TABLE items ADD COLUMN category_override TEXT NOT NULL DEFAULT ''")
  if 'ignored' not in cols:c.execute('ALTER TABLE items ADD COLUMN ignored INTEGER NOT NULL DEFAULT 0')
  c.execute('CREATE INDEX IF NOT EXISTS ix_items_extension ON items(extension)')
  # Migra itens legados sem alterar nomes, capas, senhas e caminhos.
  # Apenas a categoria automatica é recalculada; alterações manuais posteriores prevalecem.
  migration=DATA/'.categoria_por_extensao_v106'
  if not migration.exists():
   rows=c.execute("""SELECT i.id,i.path,i.kind,i.category_override,i.category,s.category AS source_category
         FROM items i JOIN sources s ON i.source_id=s.id""").fetchall()
   for row in rows:
    ext=extension_of(row['path'],row['kind'])
    detected=category(row['path'],row['source_category']) if row['kind']=='file' else row['category']
    if row['category_override']:detected=row['category_override']
    c.execute('UPDATE items SET extension=?,category=? WHERE id=?',(ext,detected,row['id']))
   c.commit()
   migration.write_text('1',encoding='utf-8')
  # Migra automaticamente o catalogo v1.0.3, sem pedir recadastro.
  marker=DATA/'.privacidade_corrigida_v104'
  if not marker.exists():
   records=c.execute('''SELECT items.id,items.path,items.hidden,sources.path AS source_root
      FROM items JOIN sources ON items.source_id=sources.id''').fetchall()
   for row in records:
    # Preservar status de disco desconectado; nao confundir offline com oculto.
    if Path(row['path']).exists():
     corrected=hidden_for_item(row['path'],row['source_root'])
     if corrected!=row['hidden']:
      c.execute('UPDATE items SET hidden=? WHERE id=?',(corrected,row['id']))
   marker.write_text('corrigido',encoding='utf-8')

 # Recalcular proteção antiga em CADA inicialização (somente arquivos acessíveis).
 # Em versões antigas, uma migração marcada como concluída podia manter centenas
 # de itens normais sob Protegidos. Uma fonte desconectada não é reclassificada
 # para evitar exposição acidental de conteúdo privado.
 refresh_hidden_visibility()
 refresh_media_visibility()


def refresh_hidden_visibility():
 """Corrige entradas protegidas incorretamente em bancos de versões antigas.

 Não reclassifica caminhos offline. Mantém arquivos explicitamente ocultos no
 Windows na área Admin, sem confiar no bit salvo por versões anteriores.
 """
 has_hidden_attribute.cache_clear()
 with conn() as db:
  entries=db.execute("SELECT i.id,i.path,i.hidden,s.path AS source_root FROM items i JOIN sources s ON s.id=i.source_id").fetchall()
  changes=[]
  for row in entries:
   correct=hidden_for_item(row['path'],row['source_root'])
   if int(row['hidden'])!=correct:changes.append((correct,row['id']))
  if changes:db.executemany('UPDATE items SET hidden=? WHERE id=?',changes)
 return len(changes)


# Classificação tecnica é independente da pasta onde está salvo o arquivo.
# A preferência manual é armazenada separadamente para sobreviver a novas leituras.
def extension_of(path,kind='file'):
 return Path(path).suffix.casefold() if kind=='file' else ''

def category(path, chosen):
 suffix=Path(path).suffix.casefold()
 if suffix in EXT['Imagens']:return 'Imagens'
 if suffix in EXT['Músicas']:return 'Músicas'
 if suffix in EXT['Filmes']:
  return 'Vídeos' if chosen=='Vídeos' else 'Séries' if chosen=='Séries' or (chosen=='Automático' and any('serie' in x.lower() or 'série' in x.lower() or 'season' in x.lower() for x in Path(path).parts)) else 'Filmes'
 if suffix in EXT['Documentos']:return 'Documentos'
 if suffix in EXT['Instaladores']:
  return 'Jogos' if chosen=='Jogos' else 'Instaladores'
 return 'Outros' if chosen=='Automático' else chosen


def valid_path(p):
 if not isinstance(p,str) or not p.strip() or '\x00' in p: return None
 # Windows drive letter paths accepted; normal filesystem Path handles them under Windows
 out=Path(p.strip().strip('"')).expanduser()
 if not out.is_dir(): return None
 return str(out.resolve())

def read_json(handler):
 length=int(handler.headers.get('Content-Length','0'))
 if length>1024*1024: raise ValueError('Solicitação muito grande')
 return json.loads(handler.rfile.read(length) or b'{}')

def json_reply(h,data,code=200):
 body=json.dumps(data,ensure_ascii=False).encode('utf-8')
 h.send_response(code);h.send_header('Content-Type','application/json; charset=utf-8');h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Content-Length',str(len(body)));h.end_headers();h.wfile.write(body)

def scan():
 with LOCK:
  if STATE['running']:return False
  STATE.update(running=True,processed=0,found=0,current='',error='',finished_at=None)
 threading.Thread(target=scan_worker,daemon=True).start()
 return True

def scan_worker():
 try:
  has_hidden_attribute.cache_clear()
  with conn() as db:sources=[dict(r) for r in db.execute('SELECT * FROM sources')]
  hide_game_assets=read_media_filters()['ocultar_midias_steam']
  for source in sources:
   root=Path(source['path']);sid=source['id']
   is_game_library=source['category']=='Jogos' or (source['category']=='Automático' and root.name.casefold() in GAME_GROUPS and root.name.casefold() in {'jogos','games'})
   with LOCK:STATE['current']=str(root) if not is_hidden_path(str(root),source['path']) else 'Área protegida'
   if not root.is_dir():
    with conn() as db:db.execute('UPDATE items SET available=0 WHERE source_id=?',(sid,))
    continue
   now=datetime.now().isoformat(timespec='seconds')
   with conn() as db:db.execute('UPDATE items SET available=0 WHERE source_id=?',(sid,))
   pending=[]
   def push():
    if pending:
     with conn() as db:
      db.executemany('''INSERT INTO items(id,source_id,path,name,category,kind,size,mtime,available,scanned_at,hidden,game_status,extension,ignored)
       VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET source_id=excluded.source_id,name=excluded.name,category=CASE WHEN items.category_override!='' THEN items.category_override ELSE excluded.category END,kind=excluded.kind,size=excluded.size,mtime=excluded.mtime,available=1,scanned_at=excluded.scanned_at,hidden=excluded.hidden,extension=excluded.extension,ignored=excluded.ignored,game_status=CASE WHEN items.game_status_override!='' THEN items.game_status_override WHEN items.launch_path!='' THEN 'Instalados' ELSE excluded.game_status END''',pending)
      pending.clear()
   def add(p, cat, kind, status=''):
    try:st=p.stat()
    except OSError:return
    hidden=hidden_for_item(str(p),source['path'])
    ignored=int(is_internal_game_media(p,kind,hide_game_assets,source['category'],source['path']) or ignored_hidden_elsewhere(str(p),source['path']))
    pending.append((str(uuid.uuid5(uuid.NAMESPACE_URL,str(p).lower())),sid,str(p),p.stem if kind=='file' else p.name,cat,kind,st.st_size if kind=='file' else 0,st.st_mtime,now,hidden,status,extension_of(p,kind),ignored))
    with LOCK:STATE['found']+=1
    if len(pending)>=200:push()
   def index_game_root(game_root):
    for item,kind,status in game_entries(game_root,bool(source['recursive'])):
     with LOCK:STATE['current']=str(item) if not is_hidden_path(str(item),source['path']) else 'Área protegida'
     add(item,'Jogos',kind,status)
   if is_game_library:
    index_game_root(root)
   else:
    def onerror(err):
     with LOCK:STATE['error']=f'Algumas pastas não puderam ser acessadas: {err.__class__.__name__}'
    for dirname,dirs,files in os.walk(root,followlinks=False,onerror=onerror):
     base=Path(dirname)
     with LOCK:STATE['current']=str(base) if not is_hidden_path(str(base),source['path']) else 'Área protegida'
     dirs[:]=[d for d in dirs if d.casefold() not in EXCLUDE_DIRS and not (base/d).is_symlink()]
     # Um disco inteiro também identifica bibliotecas de jogos.
     for d in list(dirs):
      if source['category']=='Automático' and d.casefold() in GAME_ROOT_NAMES:
       index_game_root(base/d);dirs.remove(d)
     for fn in files:
      f=base/fn
      if f.is_symlink():continue
      cat=category(str(f),source['category'])
      game_status='Para instalar' if cat=='Jogos' and f.suffix.lower() in INSTALL_EXT else ''
      add(f,cat,'file',game_status)
     with LOCK:STATE['processed']+=1
     if not source['recursive']:break
   push()
   # Remove cartões antigos fictícios (ex.: LUTA) e arquivos removidos, após scan completo.
   with conn() as db:db.execute('DELETE FROM items WHERE source_id=? AND available=0',(sid,))
 except Exception as exc:
  with LOCK:STATE['error']=str(exc)
 finally:
  with LOCK:STATE['running']=False;STATE['current']='';STATE['finished_at']=datetime.now().isoformat(timespec='seconds')

def browse_directories(raw_path, mode='folder', include_hidden=False, hide_system_drive=False):
 """Lista pastas do PC do servidor local, sem alterar nada em disco."""
 if mode not in ('folder','executable'):
  raise ValueError('Modo inválido')
 if not raw_path:
  if os.name=='nt':
   # Windows: só retorna unidades que realmente existem (inclui USBs conectados).
   import ctypes
   bitmask=ctypes.windll.kernel32.GetLogicalDrives()
   roots=[f'{chr(65+i)}:\\' for i in range(26) if bitmask & (1<<i) and not (hide_system_drive and i==2)]
  else: roots=['/']
  return {'path':'','parent':None,'folders':[{'name':p,'path':p,'kind':'drive'} for p in roots], 'files':[]}
 if hide_system_drive and windows_system_drive(raw_path):raise ValueError('A unidade C: não está disponível pelo acesso remoto.')
 p=Path(raw_path).expanduser()
 if not p.is_dir():raise ValueError('Pasta inexistente ou inacessível')
 p=p.resolve()
 if hide_system_drive and windows_system_drive(str(p)):raise ValueError('A unidade C: não está disponível pelo acesso remoto.')
 directories=[];files=[]
 try:
  with os.scandir(p) as entries:
   for entry in entries:
    try:
     if entry.is_symlink() or (not include_hidden and (is_hidden_path(entry.path) or in_private_folder(entry.path))):continue
     if entry.is_dir(follow_symlinks=False):
      directories.append({'name':entry.name,'path':entry.path,'kind':'folder'})
     elif mode=='executable' and entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in {'.exe','.bat','.cmd','.lnk'}:
      files.append({'name':entry.name,'path':entry.path,'kind':'executable'})
    except (OSError,PermissionError):continue
 except (OSError,PermissionError) as e:raise ValueError('Não foi possível acessar essa pasta: '+str(e))
 directories.sort(key=lambda it:it['name'].casefold());files.sort(key=lambda it:it['name'].casefold())
 # No Windows a pasta raiz da unidade volta à lista de unidades.
 parent=str(p.parent) if p.parent != p else ''
 if os.name=='nt' and p.parent==p:parent=''
 return {'path':str(p),'parent':parent,'folders':directories,'files':files}

def item_by_id(i):
 with conn() as db:
  r=db.execute('SELECT * FROM items WHERE id=?',(i,)).fetchone()
  return dict(r) if r and not r['ignored'] else None

def file_stream(h,p,private=False,download=False):
 try:
  if not p.is_file():return json_reply(h,{'error':'Arquivo indisponível'},404)
  total=p.stat().st_size; rg=h.headers.get('Range','');start=0;end=total-1;partial=False
  if rg:
   m=re.fullmatch(r'bytes=(\d*)-(\d*)',rg.strip())
   if not m:return json_reply(h,{'error':'Range inválido'},416)
   a,b=m.groups()
   if a:start=int(a);end=int(b) if b else total-1
   elif b:start=max(total-int(b),0)
   if start>=total or end<start:return json_reply(h,{'error':'Range inválido'},416)
   end=min(end,total-1);partial=True
  length=max(0,end-start+1)
  typ=mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
  h.send_response(206 if partial else 200)
  h.send_header('Content-Type',typ);h.send_header('Accept-Ranges','bytes');h.send_header('Content-Length',str(length))
  h.send_header('Cache-Control','no-store' if private else 'private, max-age=300')
  h.send_header('X-Content-Type-Options','nosniff');h.send_header('Content-Disposition',('attachment' if download else 'inline')+"; filename*=UTF-8''"+quote(p.name))
  if partial:h.send_header('Content-Range',f'bytes {start}-{end}/{total}')
  h.end_headers()
  with p.open('rb') as f:
   f.seek(start)
   while length:
    chunk=f.read(min(length,1024*512))
    if not chunk:break
    try:h.wfile.write(chunk)
    except (BrokenPipeError,ConnectionResetError):break
    length-=len(chunk)
 except OSError as e:
  try:json_reply(h,{'error':str(e)},500)
  except Exception:pass

def same_or_child(path,root):
 try:
  a=os.path.normcase(os.path.normpath(str(path)))
  b=os.path.normcase(os.path.normpath(str(root)))
  return os.path.commonpath([a,b])==b
 except (ValueError,OSError):return False

def validate_filename(name,kind,original):
 if not isinstance(name,str):raise ValueError('Nome invalido')
 name=name.strip()
 if not name or name in {'.','..'} or len(name)>240 or any(c in name for c in '<>:"/\\|?*\0\r\n') or name.endswith(('.', ' ')):
  raise ValueError('Nome invalido para o Windows')
 if os.name=='nt' and name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
  raise ValueError('Nome reservado do Windows')
 if kind=='file' and Path(name).suffix.casefold()!=Path(original).suffix.casefold():
  raise ValueError('Mantenha a extensao original do arquivo')
 return name

def search_game_art(h,body):
 """Busca capas sob demanda no Wikimedia Commons para todos os tipos de mídia;
 Steam opcional para jogos. Nunca transmite nome de arquivo protegido.
 """
 iid=str(body.get('id',''))
 it=guarded_item(h,iid)
 if not it:return json_reply(h,{'error':'Item não encontrado.'},404)
 if it['hidden']:return json_reply(h,{'error':'Pesquisas externas estão desativadas para itens protegidos.'},403)
 provider=str(body.get('provider','commons'))
 if provider not in ('commons','steam'):return json_reply(h,{'error':'Fonte de imagens inválida.'},400)
 if provider=='steam' and it['category']!='Jogos':return json_reply(h,{'error':'A Steam só pode ser consultada para Jogos.'},400)
 query=str(body.get('query',it['name']))[:140].strip()
 if provider=='steam':
  query=re.split(r'\s*[\[(](?:fitgirl|dodi|codex|elamigos|repack|steamverde|multi)',query,flags=re.I)[0]
  query=re.sub(r'(?i)\s+(?:fitgirl|dodi|codex|repack)$','',query).strip(' -_.')
 if len(query)<2:return json_reply(h,{'error':'Digite ao menos 2 caracteres.'},400)
 try:
  from urllib.request import Request,urlopen
  from difflib import SequenceMatcher
  headers={'User-Agent':'SmartLibrary/1.0.15 (local media catalog; image search)','Accept':'application/json'}
  if provider=='steam':
   url='https://store.steampowered.com/api/storesearch/?'+urlencode({'term':query,'l':'portuguese','cc':'BR'})
   with urlopen(Request(url,headers=headers),timeout=10) as resp:raw=resp.read(1024*1024)
   results=json.loads(raw).get('items',[])[:25]
   norm=lambda v:re.sub(r'[^a-z0-9]','',v.casefold())
   results=sorted(results,key=lambda r:SequenceMatcher(None,norm(query),norm(r.get('name',''))).ratio(),reverse=True)[:10]
   choices=[{'name':str(r.get('name',''))[:120],'cover':f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{int(r["id"])}/library_600x900.jpg','source':'Steam'} for r in results if r.get('id')]
  else:
   url='https://commons.wikimedia.org/w/api.php?'+urlencode({'action':'query','generator':'search','gsrsearch':query,'gsrnamespace':'6','gsrlimit':'18','prop':'imageinfo','iiprop':'url|mime','iiurlwidth':'500','format':'json','formatversion':'2'})
   with urlopen(Request(url,headers=headers),timeout=10) as resp:raw=resp.read(2*1024*1024)
   pages=json.loads(raw).get('query',{}).get('pages',[])
   choices=[]
   for page in pages:
    info=(page.get('imageinfo') or [{}])[0]
    if not info.get('mime','').startswith('image/'):continue
    cover=info.get('thumburl') or info.get('url')
    if cover and cover.startswith('https://'):
     choices.append({'name':str(page.get('title','')).removeprefix('File:')[:120], 'cover':cover,'source':'Wikimedia Commons'})
   choices=choices[:12]
  return json_reply(h,{'results':choices,'searched':query,'provider':provider})
 except Exception:
  return json_reply(h,{'error':'Não foi possível buscar imagens. Verifique a internet ou informe a URL manualmente.'},502)

def recycle_item(path):
 """Somente Lixeira do Windows; NUNCA exclusao permanente."""
 if os.name!='nt':
  raise ValueError('Enviar para a Lixeira requer Windows')
 import ctypes
 from ctypes import wintypes
 # Proteção adicional: nao permitir fallback silencioso para exclusao
 # permanente em locais sem Lixeira (p.ex. unidade de rede / dispositivo USB).
 volume=Path(path).anchor
 if not re.fullmatch(r'[A-Za-z]:\\',volume):
  raise ValueError('Lixeira indisponível para este tipo de localização.')
 get_drive=ctypes.windll.kernel32.GetDriveTypeW
 get_drive.argtypes=[ctypes.c_wchar_p];get_drive.restype=wintypes.UINT
 drive_type=get_drive(volume)
 if drive_type!=3:  # DRIVE_FIXED; outros tipos não oferecem garantias suficientes.
  raise ValueError('Lixeira não confirmada nesta unidade. Nada foi apagado.')
 class SHQUERYRBINFO(ctypes.Structure):
  _fields_=[('cbSize',wintypes.DWORD),('i64Size',ctypes.c_longlong),('i64NumItems',ctypes.c_longlong)]
 info=SHQUERYRBINFO();info.cbSize=ctypes.sizeof(SHQUERYRBINFO)
 query=ctypes.windll.shell32.SHQueryRecycleBinW
 query.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(SHQUERYRBINFO)]
 query.restype=ctypes.c_long
 if query(volume,ctypes.byref(info))!=0:
  raise ValueError('A Lixeira do Windows não está disponível nesta unidade. Nada foi apagado.')
 class SHFILEOPSTRUCTW(ctypes.Structure):
  _fields_=[('hwnd',wintypes.HWND),('wFunc',wintypes.UINT),('pFrom',wintypes.LPCWSTR),('pTo',wintypes.LPCWSTR),('fFlags',wintypes.WORD),('fAnyOperationsAborted',wintypes.BOOL),('hNameMappings',wintypes.LPVOID),('lpszProgressTitle',wintypes.LPCWSTR)]
 op=SHFILEOPSTRUCTW();op.wFunc=3;op.pFrom=str(path)+'\0\0';op.fFlags=0x40|0x10|0x04|0x400
 shell=ctypes.windll.shell32.SHFileOperationW
 shell.argtypes=[ctypes.POINTER(SHFILEOPSTRUCTW)];shell.restype=ctypes.c_int
 result=shell(ctypes.byref(op))
 if result or op.fAnyOperationsAborted:
  raise ValueError('Nao foi possivel enviar para a Lixeira (codigo %s)'%result)

# Em modo serviço não há Lixeira interativa confiável. Movemos o arquivo para
# uma Quarentena no MESMO volume, dentro da fonte cadastrada. Não libera espaço
# até o administrador escolher esvaziar, e evita exclusão irreversível acidental.
QUARANTINE_NAME='.SmartLibrary-Quarentena'

def quarantine_item(db, path, source):
 root=Path(source['path']); src=Path(path)
 if not same_or_child(src,root) or not src.exists() or src.is_symlink():
  raise ValueError('Arquivo fora da fonte cadastrada, inacessível ou atalho.')
 store_dir=root/QUARANTINE_NAME
 if same_or_child(src,store_dir):raise ValueError('Item já está na quarentena.')
 store_dir.mkdir(exist_ok=True)
 if store_dir.is_symlink():raise ValueError('Quarentena inválida.')
 if os.name=='nt':
  try:
   import ctypes
   attr=ctypes.windll.kernel32.GetFileAttributesW(str(store_dir))
   if attr != 0xFFFFFFFF:ctypes.windll.kernel32.SetFileAttributesW(str(store_dir),attr | 0x2 | 0x4)
  except (OSError,AttributeError):pass
 token=uuid.uuid4().hex
 stored=store_dir/(token+'_'+src.name)
 if stored.exists():raise ValueError('Conflito inesperado na quarentena.')
 # os.rename evita qualquer cópia entre unidades, dando resposta imediata.
 os.rename(str(src),str(stored))
 try:
  db.execute('INSERT INTO quarantine(id,original_path,stored_path,source_id,name,kind,size,created_at) VALUES(?,?,?,?,?,?,?,?)',
             (token,str(src),str(stored),source['id'],src.name,'folder' if stored.is_dir() else 'file',stored.stat().st_size if stored.is_file() else 0,datetime.now().isoformat(timespec='seconds')))
  prefix=str(src)+os.sep
  db.execute('DELETE FROM items WHERE path=? OR substr(path,1,?)=?',(str(src),len(prefix),prefix))
 except Exception:
  os.rename(str(stored),str(src))
  raise
 return token

def quarantine_manage(handler,body):
 action=body.get('action');ident=str(body.get('id',''))
 if action not in ('restore','purge') or not re.fullmatch('[a-f0-9]{32}',ident):return json_reply(handler,{'error':'Operação inválida.'},400)
 if action=='purge' and body.get('confirmation')!='APAGAR DEFINITIVAMENTE':
  return json_reply(handler,{'error':'Confirme APAGAR DEFINITIVAMENTE antes de excluir.'},400)
 with FS_LOCK:
  with conn() as db:
   rec=db.execute('SELECT * FROM quarantine WHERE id=?',(ident,)).fetchone()
   if not rec:return json_reply(handler,{'error':'Item não encontrado na quarentena.'},404)
   srcrow=db.execute('SELECT * FROM sources WHERE id=?',(rec['source_id'],)).fetchone()
   if not srcrow:return json_reply(handler,{'error':'Fonte cadastrada não encontrada.'},409)
   root=Path(srcrow['path']);stored=Path(rec['stored_path']);original=Path(rec['original_path']);root_store=root/QUARANTINE_NAME
   if blocked_remote(handler,str(original)):return json_reply(handler,{'error':'Acesso remoto à unidade C: bloqueado.'},403)
   if in_private_folder(str(original)) and not protected_unlocked(handler):return json_reply(handler,{'error':'Confirme a senha de Protegidos.'},403)
   if (not same_or_child(stored,root_store) or not stored.exists() or stored.is_symlink()
       or not same_or_child(original,root) or same_or_child(original,root_store)):
    return json_reply(handler,{'error':'Caminho inconsistente ou arquivo indisponível.'},409)
   if action=='restore':
    if original.exists() or not original.parent.is_dir() or original.parent.is_symlink():
     return json_reply(handler,{'error':'A pasta original não existe mais ou já há um item nesse caminho.'},409)
    os.rename(str(stored),str(original))
    db.execute('DELETE FROM quarantine WHERE id=?',(ident,))
    scan()
    return json_reply(handler,{'ok':True,'restored':True})
   # Exclusão permanente só após autenticação e frase exata.
   if stored.is_dir():shutil.rmtree(stored)
   else:stored.unlink()
   db.execute('DELETE FROM quarantine WHERE id=?',(ident,))
   return json_reply(handler,{'ok':True,'purged':True})

def operate_on_item(handler,body):
 action=body.get('action');iid=str(body.get('id',''))
 if action not in ('rename','move','trash'):return json_reply(handler,{'error':'Acao invalida'},400)
 with FS_LOCK:
  with LOCK:
   if STATE['running']:return json_reply(handler,{'error':'Aguarde o fim do escaneamento antes de alterar arquivos.'},409)
  item=guarded_item(handler,iid)
  if not item:return json_reply(handler,{'error':'Item nao encontrado'},404)
  src=Path(item['path'])
  if src.is_symlink() or not src.exists():return json_reply(handler,{'error':'Arquivo ou pasta indisponivel.'},404)
  if str(body.get('expected_path',''))!=str(src):return json_reply(handler,{'error':'Item foi alterado. Atualize a biblioteca.'},409)
  with conn() as db:
   sources=[dict(r) for r in db.execute('SELECT * FROM sources')]
  owning=next((r for r in sources if r['id']==item['source_id']),None)
  if not owning or not same_or_child(src,owning['path']):return json_reply(handler,{'error':'Caminho fora da biblioteca'},403)
  if os.path.normcase(os.path.normpath(str(src)))==os.path.normcase(os.path.normpath(owning['path'])):
   return json_reply(handler,{'error':'Nao e permitido alterar a raiz cadastrada'},403)
  if action=='rename':
   filename=validate_filename(body.get('name'),item['kind'],src.name)
   dest=src.with_name(filename)
  elif action=='move':
   destination=Path(str(body.get('destination','')).strip())
   if not destination.is_dir() or destination.is_symlink():return json_reply(handler,{'error':'Selecione uma pasta de destino existente.'},400)
   dest=destination/src.name
  else:dest=None
  if action!='trash':
   if blocked_remote(handler,str(dest)):return json_reply(handler,{'error':'Unidade C: indisponível remotamente.'},403)
   if same_or_child(dest,src) and src.is_dir():return json_reply(handler,{'error':'Nao e permitido mover uma pasta para dentro dela propria.'},400)
   if dest.exists() and dest!=src:return json_reply(handler,{'error':'Ja existe um arquivo ou pasta com esse nome no destino.'},409)
   if str(dest)==str(src):return json_reply(handler,{'ok':True,'path':str(src)})
   # Manter arquivos na biblioteca: destino deve estar dentro de um local ja cadastrado.
   targets=[r for r in sources if same_or_child(dest,r['path'])]
   if not targets:return json_reply(handler,{'error':'Cadastre primeiro a pasta/disco de destino em Locais.'},400)
   target=max(targets,key=lambda r:len(r['path']))
   if in_private_folder(str(dest)) and not protected_unlocked(handler):
    return json_reply(handler,{'error':'Desbloqueie a area protegida para mover para esta pasta.'},403)
   if any(p.is_symlink() for p in (dest.parent,*dest.parent.parents) if same_or_child(p,target['path'])):
    return json_reply(handler,{'error':'Destinos com atalhos de pasta nao sao permitidos'},400)
  if action=='trash':
   if SERVICE_MODE:
    with conn() as db:quarantine_item(db,src,owning)
    return json_reply(handler,{'ok':True,'quarantined':True})
   recycle_item(src)
   with conn() as db:
    prefix=str(src)+os.sep
    db.execute('DELETE FROM items WHERE path=? OR substr(path,1,?)=?',(str(src),len(prefix),prefix))
   return json_reply(handler,{'ok':True,'recycled':True})
  # rename/move fisico primeiro; depois atualiza caminhos e ids sem perder capas.
  # os.rename bloqueia mov. entre unidades para evitar copia gigante e riscos; usa shutil.move entre discos.
  shutil.move(str(src),str(dest))
  try:
   with conn() as db:
    prefix=str(src)+os.sep
    records=db.execute('SELECT * FROM items WHERE path=? OR substr(path,1,?)=?',(str(src),len(prefix),prefix)).fetchall()
    for rec in records:
     path=rec['path']
     updated=str(dest)+path[len(str(src)):]
     oldlaunch=rec['launch_path'] or ''
     if oldlaunch and same_or_child(oldlaunch,src):oldlaunch=str(dest)+oldlaunch[len(str(src)):]
     newname=(Path(updated).stem if rec['kind']=='file' else Path(updated).name) if rec['id']==iid and action=='rename' else rec['name']
     newhidden=hidden_for_item(updated,target['path'])
     db.execute('UPDATE items SET path=?,source_id=?,hidden=?,name=?,launch_path=?,extension=? WHERE id=?',(updated,target['id'],newhidden,newname,oldlaunch,extension_of(updated,rec['kind']),rec['id']))
  except Exception:
   try:shutil.move(str(dest),str(src))
   except Exception:pass
   raise
  return json_reply(handler,{'ok':True,'path':str(dest)})


def bulk_recycle_items(handler,body):
 """Envia uma seleção explícita à Lixeira, nunca exclui por título semelhante."""
 requests=body.get('items')
 if body.get('confirmation')!='EXCLUIR':return json_reply(handler,{'error':'Confirmação obrigatória.'},400)
 if not isinstance(requests,list) or not (1<=len(requests)<=100):
  return json_reply(handler,{'error':'Selecione entre 1 e 100 itens por operação.'},400)
 if os.name!='nt' and not SERVICE_MODE:return json_reply(handler,{'error':'Lixeira disponível somente no Windows.'},400)
 with FS_LOCK:
  with LOCK:
   if STATE['running']:return json_reply(handler,{'error':'Aguarde o fim do escaneamento.'},409)
  with conn() as db:
   source_rows={r['id']:dict(r) for r in db.execute('SELECT * FROM sources')}
   validated=[];seen=set()
   # Preflight: nenhuma exclusão é feita se qualquer item falhar na validação.
   for req in requests:
    if not isinstance(req,dict):return json_reply(handler,{'error':'Seleção inválida.'},400)
    iid=req.get('id','');expected=req.get('expected_path','')
    if not isinstance(iid,str) or not isinstance(expected,str) or len(iid)>100 or len(expected)>4096 or iid in seen:
     return json_reply(handler,{'error':'Seleção duplicada ou inválida.'},400)
    seen.add(iid)
    rec=db.execute('SELECT * FROM items WHERE id=? AND ignored=0',(iid,)).fetchone()
    if not rec:return json_reply(handler,{'error':'Um item não está mais no catálogo. Atualize a página.'},409)
    item=dict(rec)
    if not is_allowed(handler,item):return json_reply(handler,{'error':'Desbloqueie a área protegida para alterar estes itens.'},403)
    original=Path(item['path'])
    owning=source_rows.get(item['source_id'])
    if (expected!=item['path'] or not original.exists() or original.is_symlink() or
     not owning or not same_or_child(original,owning['path']) or
     os.path.normcase(os.path.normpath(str(original)))==os.path.normcase(os.path.normpath(owning['path']))):
     return json_reply(handler,{'error':'Item modificado, indisponível ou fora da biblioteca. Atualize a seleção.'},409)
    validated.append(item)
  # Se uma pasta selecionada inclui outro item, só enviamos a pasta.
  validated.sort(key=lambda x:len(Path(x['path']).parts))
  filtered=[];skipped=[]
  for rec in validated:
   if any(parent['kind']=='folder' and same_or_child(rec['path'],parent['path']) for parent in filtered):
    skipped.append(rec['id'])
   else:filtered.append(rec)
  deleted=[];failed=[]
  for rec in filtered:
   src=Path(rec['path'])
   try:
    if SERVICE_MODE:
     with conn() as db:quarantine_item(db,src,source_rows[rec['source_id']])
    else:
     recycle_item(src)
     with conn() as db:
      prefix=str(src)+os.sep
      db.execute('DELETE FROM items WHERE path=? OR substr(path,1,?)=?',(str(src),len(prefix),prefix))
   except Exception:
    failed.append({'id':rec['id'],'reason':'Não foi possível mover o item para a Quarentena ou Lixeira.'})
    continue
   deleted.append(rec['id'])
  return json_reply(handler,{'ok':not failed,'deleted_count':len(deleted),'deleted_ids':deleted,
    'ignored_nested':len(skipped),'failed':failed,'quarantined':SERVICE_MODE})

DUPLICATES=DuplicateFinder(conn, lambda path, source: bool(in_private_folder(path) or is_hidden_path(path, source)))

# Envio remoto: somente administrador; grava arquivos sem sobrescrever arquivos
# existentes e sem aceitar pastas de sistema. A conta do serviço precisa de ACL.
UPLOAD_MAX=2*1024*1024*1024  # 2 GiB por arquivo, streaming em blocos.
UPLOAD_BLOCK=1024*512
UPLOAD_DENY={'windows','program files','program files (x86)','programdata',
             'system volume information','$recycle.bin','appdata','.git',
             'node_modules','.smartlibrary-quarentena','dados','servidor'}
def upload_destination(raw):
 if not isinstance(raw,str) or not raw.strip() or len(raw)>2048 or '\x00' in raw:
  raise ValueError('Escolha uma pasta de destino válida.')
 folder=Path(raw).expanduser()
 if not folder.is_dir():raise ValueError('A pasta selecionada não está acessível.')
 # Não escrever em links simbólicos/reparse points ou diretórios de sistema.
 for ancestor in (folder,*folder.parents):
  if ancestor.is_symlink():raise ValueError('Destino com link simbólico não permitido.')
 folder=folder.resolve(strict=True)
 if any(x.casefold() in UPLOAD_DENY for x in folder.parts):
  raise ValueError('Escolha uma pasta de arquivos pessoais, não uma pasta de sistema ou aplicativo.')
 if folder==Path(folder.anchor):raise ValueError('Entre em uma pasta do disco; não envie diretamente à raiz.')
 if same_or_child(folder,ROOT):raise ValueError('Não é permitido enviar arquivos para a pasta do próprio Smart Library.')
 return folder

def receive_upload(h,raw_destination):
 if not unlocked(h):return json_reply(h,{'error':'Somente o Admin pode enviar arquivos.'},403)
 # File-Name é codificado em UTF-8 com encodeURIComponent no navegador.
 filename=unquote(h.headers.get('X-File-Name',''))
 if not filename or len(filename)>240 or any(x in filename for x in ('/','\\','\x00','\r','\n')):
  return json_reply(h,{'error':'Nome de arquivo inválido.'},400)
 try:
  validate_filename(filename,'file',filename)
  n=int(h.headers.get('Content-Length','-1'))
  if n<=0 or n>UPLOAD_MAX:raise ValueError('Tamanho não permitido (máximo 2 GB por arquivo).')
  folder=upload_destination(raw_destination)
  if blocked_remote(h,str(folder)):return json_reply(h,{'error':'Não é permitido enviar arquivos para C: remotamente.'},403)
  if in_private_folder(str(folder)) and not protected_unlocked(h):return json_reply(h,{'error':'Desbloqueie Protegidos antes de enviar arquivos para esta pasta.'},403)
 except (OSError,ValueError) as e:return json_reply(h,{'error':str(e)},400)
 target=folder/filename
 if target.exists():return json_reply(h,{'error':'Já existe arquivo com esse nome na pasta. Renomeie antes de enviar.'},409)
 temporary=folder/('.smartlibrary-upload-'+uuid.uuid4().hex+'.part')
 try:
  with temporary.open('xb') as dst:
   remaining=n
   while remaining:
    data=h.rfile.read(min(remaining,UPLOAD_BLOCK))
    if not data:raise OSError('O envio foi interrompido antes de terminar.')
    dst.write(data);remaining-=len(data)
  # Windows: link atômico falha se destino existir e preserva o conteúdo existente.
  try:
   os.link(str(temporary),str(target))
  except OSError as link_error:
   if isinstance(link_error, FileExistsError):raise
   # FAT/exFAT e alguns compartilhamentos não permitem hardlinks.
   # Criação exclusiva impede sobrescrever um arquivo existente.
   created=False
   try:
    with target.open('xb') as final:
     created=True
     with temporary.open('rb') as temp:shutil.copyfileobj(temp,final,UPLOAD_BLOCK)
   except Exception:
    if created:
     try:target.unlink(missing_ok=True)
     except OSError:pass
    raise
  temporary.unlink()
  return json_reply(h,{'ok':True,'name':filename,'destination':str(target),'bytes':n})
 except FileExistsError:return json_reply(h,{'error':'O arquivo já existe no destino; nada foi sobrescrito.'},409)
 except (OSError,ValueError) as e:return json_reply(h,{'error':'Falha ao salvar: '+str(e)},500)
 finally:
  try:temporary.unlink(missing_ok=True)
  except OSError:pass

class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):print('[HTTP]',fmt%args)
 def do_GET(self):
  u=urlparse(self.path);q=parse_qs(u.query)
  if u.path in ('/', '/app.css', '/app.js', '/favicon.svg'):
   name={'/':'index.html', '/app.css':'app.css','/app.js':'app.js','/favicon.svg':'favicon.svg'}[u.path]
   body=(WEBROOT/name).read_bytes()
   kind={'/':'text/html; charset=utf-8','/app.css':'text/css; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/favicon.svg':'image/svg+xml'}[u.path]
   self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
  if u.path=='/api/quarantine':
   if not unlocked(self):return json_reply(self,{'error':'Acesso exclusivo do administrador'},403)
   with conn() as db:rows=[dict(r) for r in db.execute('SELECT * FROM quarantine ORDER BY created_at DESC LIMIT 1000') if not blocked_remote(self,r['original_path']) and (not in_private_folder(r['original_path']) or protected_unlocked(self))]
   return json_reply(self,{'items':rows})
  if u.path=='/api/media/folders':
   if q.get('category',[''])[0] not in ('Filmes','Séries'):
    return json_reply(self,{'error':'Categoria inválida.'},400)
   cat=q['category'][0];source=q.get('source',[''])[0];folder=q.get('folder',[''])[0]
   with conn() as db:
    sources=[dict(r) for r in db.execute('SELECT * FROM sources')]
    rows=[dict(r) for r in db.execute('SELECT id,source_id,path,name,hidden FROM items WHERE category=? AND kind=? AND hidden=0 AND ignored=0 ORDER BY path',(cat,'file')) if not blocked_remote(self,r['path'])]
   roots={r['id']:r for r in sources}
   if source and source not in roots:return json_reply(self,{'error':'Fonte inválida.'},400)
   if source and blocked_remote(self,roots[source]['path']):return json_reply(self,{'error':'Unidade indisponível no acesso remoto.'},403)
   if not source:
    grouped={}
    for r in rows:
     sid=r['source_id']
     if sid not in roots:continue
     if sid not in grouped:grouped[sid]={'name':Path(roots[sid]['path']).name or roots[sid]['path'],'path':roots[sid]['path'],'source_id':sid,'count':0,'cover_id':r['id']}
     grouped[sid]['count']+=1
    return json_reply(self,{'level':'sources','folders':sorted(grouped.values(),key=lambda x:x['name'].casefold()),'files':0,'parent':None})
   root=Path(roots[source]['path']);here=Path(folder) if folder else root
   if not same_or_child(here,root) or (here.exists() and here.is_symlink()):
    return json_reply(self,{'error':'Pasta fora do local cadastrado.'},403)
   children={};direct=0
   for it in rows:
    if it['source_id']!=source or not same_or_child(it['path'],here):continue
    try:parts=Path(it['path']).relative_to(here).parts
    except ValueError:continue
    if len(parts)==1:direct+=1;continue
    sub=parts[0];node=children.setdefault(sub,{'name':sub,'path':str(here/sub),'source_id':source,'count':0,'cover_id':it['id']});node['count']+=1
   parent=None if here==root else str(here.parent)
   return json_reply(self,{'level':'folder','name':here.name,'folder':str(here),'source':source,'root':str(root),'parent':parent,'folders':sorted(children.values(),key=lambda x:x['name'].casefold()),'files':direct})
  if u.path=='/api/duplicates':
   if not unlocked(self):return json_reply(self,{'error':'Acesso exclusivo do administrador'},403)
   if not local_request(self):return json_reply(self,{'error':'A análise de duplicados é exclusiva do PC servidor.'},403)
   return json_reply(self,DUPLICATES.snapshot())
  if u.path=='/api/private/status':
   return json_reply(self,{'configured':private_config() is not None,'unlocked':unlocked(self),'protected_unlocked':protected_unlocked(self)})
  if u.path.startswith('/api/art/'):
   return local_poster(self,guarded_item(self,u.path.rsplit('/',1)[-1]))
  if u.path.startswith('/api/thumb/'):
   return save_cover_thumbnail(self,guarded_item(self,u.path.rsplit('/',1)[-1]))
  if u.path=='/api/music/queue':
   iid=q.get('item_id',[''])[0][:80]
   it=guarded_item(self,iid)
   if not it or it['category']!='Músicas' or it['kind']!='file':return json_reply(self,{'error':'Música não encontrada'},404)
   hidden=int(it['hidden'])
   source=q.get('source',[''])[0][:80]
   sql='SELECT id,name,path,available FROM items WHERE category=? AND kind=? AND hidden=? AND ignored=0'
   args=['Músicas','file',hidden]
   if not local_request(self):sql+=" AND UPPER(SUBSTR(path,1,2))!='C:'"
   if source:
    # Só aplica o filtro da fonte se a faixa atual também estiver nela.
    if source==it['source_id']:sql+=' AND source_id=?';args.append(source)
   sql+=' ORDER BY name COLLATE NOCASE,id LIMIT 20000'
   with conn() as db:items=[dict(r) for r in db.execute(sql,args)]
   return json_reply(self,{'items':items,'private':bool(hidden)})
  if u.path=='/api/local-item':
   if not local_request(self):return json_reply(self,{'error':'Somente localhost.'},403)
   it=guarded_item(self,q.get('id',[''])[0][:100])
   return json_reply(self,{'path':it['path'],'kind':it['kind']}) if it else json_reply(self,{'error':'Item indisponível.'},404)
  if u.path=='/api/fs/list':
   if not unlocked(self):return json_reply(self,{'error':'Explorador disponivel somente para admin.'},403)
   if in_private_folder(q.get('path',[''])[0]) and not protected_unlocked(self):return json_reply(self,{'error':'Entre em Protegidos com a senha para acessar esta pasta.'},403)
   if len(q.get('path',[''])[0])>2048:return json_reply(self,{'error':'Caminho muito longo'},400)
   if is_hidden_path(q.get('path',[''])[0]) and q.get('path',[''])[0] and not protected_unlocked(self):return json_reply(self,{'error':'Área protegida'},403)
   try:return json_reply(self,browse_directories(q.get('path',[''])[0],q.get('mode',['folder'])[0],protected_unlocked(self),not local_request(self)))
   except Exception as exc:return json_reply(self,{'error':str(exc)},400)
  if u.path=='/api/status':
   with LOCK:state=STATE.copy()
   if not local_request(self) and windows_system_drive(state.get('current','')):state['current']='Verificando arquivos locais'
   with conn() as db:
    condition=' WHERE hidden=0 AND ignored=0' + ('' if local_request(self) else " AND UPPER(SUBSTR(path,1,2))!='C:'")
    stats=[dict(r) for r in db.execute('SELECT category, COUNT(*) n FROM items'+condition+' GROUP BY category')]
    total=db.execute('SELECT COUNT(*) FROM items'+condition).fetchone()[0]
    ignored_count=db.execute('SELECT COUNT(*) FROM items WHERE ignored=1' + ('' if unlocked(self) else ' AND hidden=0')).fetchone()[0]
    sources=[dict(r) for r in db.execute('SELECT * FROM sources ORDER BY created')]
   if not unlocked(self):sources=[x for x in sources if not is_hidden_path(x['path'],x['path'])]
   if not local_request(self):sources=[x for x in sources if not windows_system_drive(x['path'])]
   for s in sources:s['online']=Path(s['path']).is_dir()
   return json_reply(self,{'status':state,'stats':stats,'total':total,'sources':sources,'service_mode':SERVICE_MODE,'can_locate':local_request(self),'media_filters':read_media_filters(),'ignored_media_count':ignored_count})
  if u.path=='/api/filters':
   scope=q.get('category',['Todos'])[0]
   subcat=q.get('subcategory',[''])[0]
   if scope not in CAT | {'Todos','Protegidos'}:return json_reply(self,{'error':'Categoria inválida'},400)
   if subcat and subcat not in CAT-{'Automático'}:return json_reply(self,{'error':'Subcategoria inválida'},400)
   if scope=='Protegidos' and not protected_unlocked(self):return json_reply(self,{'error':'Área protegida'},403)
   condition='hidden=? AND ignored=0';args=[1 if scope=='Protegidos' else 0]
   if not local_request(self):condition+=" AND UPPER(SUBSTR(path,1,2))!='C:'"
   if scope not in {'Todos','Protegidos'}:condition+=' AND category=?';args.append(scope)
   with conn() as db:
    cats=[{'name':r[0],'count':r[1]} for r in db.execute('SELECT category,COUNT(*) FROM items WHERE '+condition+' GROUP BY category ORDER BY category',args)]
    if scope in ('Protegidos','Todos') and subcat:condition+=' AND category=?';args.append(subcat)
    formats=[{'ext':(r[0] or '[sem extensão]') if r[1]=='file' else '[pasta]','count':r[2]} for r in db.execute('SELECT extension,kind,COUNT(*) FROM items WHERE '+condition+' GROUP BY extension,kind ORDER BY kind,COUNT(*) DESC,extension LIMIT 250',args)]
   return json_reply(self,{'categories':cats,'formats':formats})
  if u.path=='/api/items':
   search=q.get('q',[''])[0][:200];cat=q.get('category',['Todos'])[0];source=q.get('source',[''])[0];page=max(1,min(int(q.get('page',['1'])[0]),100000));where=[];args=[]
   if cat=='Protegidos':
    if not protected_unlocked(self):return json_reply(self,{'error':'Digite a senha para entrar em Protegidos.'},403)
    where.append('hidden=1 AND ignored=0')
   else:
    where.append('hidden=0 AND ignored=0')
    if cat!='Todos':where.append('category=?');args.append(cat)
   subcat=q.get('subcategory',[''])[0];ext=q.get('extension',[''])[0]
   if cat in ('Protegidos','Todos') and subcat:
    if subcat not in CAT-{'Automático'}:return json_reply(self,{'error':'Categoria inválida'},400)
    where.append('category=?');args.append(subcat)
   if ext:
    if ext=='[pasta]':where.append('kind=?');args.append('folder')
    elif re.fullmatch(r'\.[a-z0-9]{1,16}',ext,flags=re.I):
     where.append('kind=? AND extension=?');args.extend(['file',ext.casefold()])
    elif ext=='[sem extensão]':where.append("kind='file' AND extension=''")
    else:return json_reply(self,{'error':'Extensão inválida'},400)
   game=q.get('game_status',[''])[0]
   if cat=='Jogos' and game in {'Instalados','Para instalar','Verificar'}:
    where.append('game_status=?');args.append(game)
   folder=q.get('folder',[''])[0]
   if folder:
    with conn() as db:source_entry=db.execute('SELECT path FROM sources WHERE id=?',(source,)).fetchone() if source else None
    if not source_entry or not same_or_child(folder,source_entry['path']):
     return json_reply(self,{'error':'Pasta fora da fonte cadastrada.'},403)
    # Exibe SOMENTE os arquivos diretamente dentro da pasta selecionada.
    # Banco possui 1000s de itens: filtro no SQL pela pasta pai usando substr.
    direct_paths=True
   else:direct_paths=False
   if not local_request(self):where.append("UPPER(SUBSTR(path,1,2))!='C:'")
   if source:where.append('source_id=?');args.append(source)
   if search:where.append('(name LIKE ? OR path LIKE ?)');args.extend([f'%{search}%',f'%{search}%'])
   clause=(' WHERE '+' AND '.join(where)) if where else ''
   with conn() as db:
    if direct_paths:
     # Consulta caminhos catalogados, sem caminhar no disco. Usado só nas coleções.
     candidates=[dict(r) for r in db.execute('SELECT * FROM items'+clause+' ORDER BY available DESC,name COLLATE NOCASE',args)]
     candidates=[it for it in candidates if os.path.normcase(os.path.normpath(str(Path(it['path']).parent)))==os.path.normcase(os.path.normpath(folder))]
     total=len(candidates);items=candidates[(page-1)*60:page*60]
    else:
     total=db.execute('SELECT count(*) FROM items'+clause,args).fetchone()[0]
     items=[dict(r) for r in db.execute('SELECT * FROM items'+clause+' ORDER BY available DESC,name COLLATE NOCASE LIMIT 60 OFFSET ?',args+[(page-1)*60])]
   return json_reply(self,{'total':total,'page':page,'items':items})
  if u.path.startswith('/api/download/'):
   it=guarded_item(self,u.path.rsplit('/',1)[-1]);return file_stream(self,Path(it['path']),bool(it['hidden']),download=True) if it and it['kind']=='file' else json_reply(self,{'error':'Não encontrado'},404)
  if u.path.startswith('/api/stream/'):
   it=guarded_item(self,u.path.rsplit('/',1)[-1]);return file_stream(self,Path(it['path']),bool(it['hidden'])) if it and it['kind']=='file' else json_reply(self,{'error':'Não encontrado'},404)
  return json_reply(self,{'error':'Rota desconhecida'},404)
 def do_POST(self):
  u=urlparse(self.path)
  try:
   # Requisicoes POST so sao aceitas pela origem exata. Cookie SameSite=Strict.
   origin=self.headers.get('Origin','')
   if origin and origin != f'http://{self.headers.get("Host", "")}' :
    return json_reply(self,{'error':'Origem nao autorizada'},403)
   if u.path=='/api/upload':
    if self.headers.get('Content-Type','').lower()!='application/octet-stream':return json_reply(self,{'error':'Tipo de envio inválido.'},415)
    return receive_upload(self,parse_qs(u.query).get('destination',[''])[0])
   if 'application/json' not in self.headers.get('Content-Type',''):
    return json_reply(self,{'error':'Envie dados JSON'},415)
   body=read_json(self)
   # Todos os visitantes consultam/reproduzem o conteudo publico. Escrita e exploracao somente admin.
   if u.path not in ('/api/private/unlock','/api/private/lock','/api/protected/unlock','/api/protected/lock') and not unlocked(self):
    if u.path=='/api/open' and body.get('mode') in ('folder','locate'):
     pass  # apenas solicita a abertura local; no servico a acao nunca sera executada
    else:return json_reply(self,{'error':'Entre como administrador para realizar alteracoes.'},403)
   if u.path=='/api/quarantine/manage':return quarantine_manage(self,body)
   if u.path=='/api/duplicates/scan' and not local_request(self):return json_reply(self,{'error':'Exclusivo do PC servidor.'},403)
   if u.path=='/api/duplicates/scan':return json_reply(self,{'started':DUPLICATES.start(),'status':DUPLICATES.snapshot()})
   if u.path=='/api/duplicates/cancel' and not local_request(self):return json_reply(self,{'error':'Exclusivo do PC servidor.'},403)
   if u.path=='/api/duplicates/cancel':return json_reply(self,{'cancel_requested':DUPLICATES.cancel()})
   if u.path=='/api/file-operation':return operate_on_item(self,body)
   if u.path=='/api/bulk-trash':return bulk_recycle_items(self,body)
   if u.path=='/api/cover-search':return search_game_art(self,body)
   if u.path=='/api/private/setup':return json_reply(self,{'error':'Defina a senha com Alterar Senha Admin.bat no proprio computador.'},403)
   if u.path in ('/api/private/unlock','/api/protected/unlock'):
    if u.path=='/api/protected/unlock' and not unlocked(self):return json_reply(self,{'error':'Entre como Admin antes de acessar Protegidos.'},403)
    with ACCESS_LOCK:
     if time.time()<ATTEMPTS['until']:return json_reply(self,{'error':'Aguarde antes de tentar novamente.'},429)
     cfg=private_config()
     if cfg is None:return json_reply(self,{'error':'Cadastre uma senha primeiro.'},400)
     if not check_password(str(body.get('password','')),cfg):
      ATTEMPTS['fail']+=1
      if ATTEMPTS['fail']>=5:ATTEMPTS['until']=time.time()+60;ATTEMPTS['fail']=0
      return json_reply(self,{'error':'Senha incorreta.'},403)
     ATTEMPTS.update(fail=0,until=0)
     cookie=grant(self) if u.path=='/api/private/unlock' else grant_protected(self);data=json.dumps({'ok':True}).encode()
     self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie',cookie);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
   if u.path=='/api/protected/lock':
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie',protected_lock(self));self.end_headers();self.wfile.write(b'{"ok":true}');return
   if u.path=='/api/private/lock':
    with SESS_LOCK:SESSIONS.pop(current_token(self),None)
    pcookie=protected_lock(self)
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie','sl_admin=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');self.send_header('Set-Cookie',pcookie);self.end_headers();self.wfile.write(b'{"ok":true}');return
   if u.path=='/api/media-filters':
    enabled=body.get('ocultar_midias_steam')
    if type(enabled) is not bool:return json_reply(self,{'error':'Valor de filtro inválido'},400)
    with LOCK:
     if STATE['running']:return json_reply(self,{'error':'Aguarde o escaneamento terminar.'},409)
     changed=update_media_filters(enabled)
    return json_reply(self,{'ok':True,'updated':changed,'filters':read_media_filters()})
   if u.path=='/api/sources':
    p=valid_path(body.get('path',''));cat=body.get('category','Automático');rec=int(bool(body.get('recursive',True)))
    if not p:return json_reply(self,{'error':'Pasta ou unidade inválida ou inacessível'},400)
    if cat not in CAT:return json_reply(self,{'error':'Categoria inválida'},400)
    if blocked_remote(self,p):return json_reply(self,{'error':'Não é permitido cadastrar a unidade C: remotamente.'},403)
    if in_private_folder(p) and not protected_unlocked(self):return json_reply(self,{'error':'Desbloqueie a área protegida para adicionar essa pasta.'},403)
    with conn() as db:
     if db.execute('SELECT 1 FROM sources WHERE path=?',(p,)).fetchone():return json_reply(self,{'error':'Esse local já está cadastrado'},409)
     db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',(str(uuid.uuid4()),p,cat,rec,datetime.now().isoformat()))
    return json_reply(self,{'ok':True})
   if u.path=='/api/scan':return json_reply(self,{'ok':scan()},200)
   if u.path=='/api/remove-source':
    sid=str(body.get('id',''))
    with conn() as db:
     r=db.execute('SELECT path FROM sources WHERE id=?',(sid,)).fetchone()
     if r and blocked_remote(self,r['path']):return json_reply(self,{'error':'Unidade C: indisponível remotamente.'},403)
     if r and in_private_folder(r['path']) and not protected_unlocked(self):return json_reply(self,{'error':'Área protegida'},403)
     db.execute('DELETE FROM items WHERE source_id=?',(sid,));db.execute('DELETE FROM sources WHERE id=?',(sid,))
    return json_reply(self,{'ok':True})
   if u.path=='/api/open':
    it=guarded_item(self,str(body.get('id','')))
    if not it or not Path(it['path']).exists():return json_reply(self,{'error':'Item indisponível'},404)
    if os.name!='nt':return json_reply(self,{'error':'Abrir arquivos requer Windows'},400)
    if SERVICE_MODE or not local_request(self):return json_reply(self,{'error':'O Servico Windows nao pode abrir programas ou o Explorador na sessao do usuario. Use o modo interativo para essa acao.'},409)
    mode=body.get('mode','folder')
    if mode=='folder':subprocess.Popen(['explorer.exe','/select,',it['path']] if it['kind']=='file' else ['explorer.exe',it['path']])
    elif mode=='locate':
     # Abre o Explorador no local EXATO, com o arquivo ou pasta destacado.
     target=Path(it['path'])
     if target.parent==target:subprocess.Popen(['explorer.exe',str(target)])
     else:subprocess.Popen(['explorer.exe','/select,',str(target)])
    elif mode=='launch':
     target=Path(it['launch_path'] or it['path'])
     if target.suffix.lower() not in ('.exe','.bat','.cmd','.lnk') or not target.is_file():return json_reply(self,{'error':'Configure um executável (.exe, .bat, .cmd ou .lnk) para iniciar.'},400)
     os.startfile(str(target))
    else:return json_reply(self,{'error':'Ação inválida'},400)
    return json_reply(self,{'ok':True})
   if u.path=='/api/edit':
    iid=str(body.get('id',''));cover=str(body.get('cover',''))[:2048];launch=str(body.get('launch_path',''))[:2048];name=str(body.get('name','')).strip()[:300]
    override=str(body.get('game_status_override',''))
    category_override=str(body.get('category_override',''))
    if override not in ('','Instalados','Para instalar','Verificar'):return json_reply(self,{'error':'Status inválido'},400)
    if category_override not in CAT-{'Automático'} and category_override!='':return json_reply(self,{'error':'Categoria inválida'},400)
    if cover and not (cover.startswith('https://') or cover.startswith('http://')):return json_reply(self,{'error':'A capa deve ser um link HTTP ou HTTPS'},400)
    with conn() as db:
     item=guarded_item(self,iid)
     if not item:return json_reply(self,{'error':'Item não encontrado'},404)
     row=db.execute('SELECT category FROM sources WHERE id=?',(item['source_id'],)).fetchone()
     if not row:return json_reply(self,{'error':'Local não encontrado'},404)
     detected=category(item['path'],row['category']) if item['kind']=='file' else item['category']
     cat=category_override or detected
     db.execute("UPDATE items SET cover=?,launch_path=?,name=COALESCE(NULLIF(?,''),name),game_status_override=?,game_status=CASE WHEN ?!='' THEN ? WHEN ?!='' THEN 'Instalados' ELSE game_status END,category=?,category_override=? WHERE id=?",(cover,launch,name,override,override,override,launch,cat,category_override,iid))
    return json_reply(self,{'ok':True})
   return json_reply(self,{'error':'Rota desconhecida'},404)
  except Exception as e:return json_reply(self,{'error':str(e)},400)

def main(stop_event=None, service_mode=False):
 global HOST,SERVICE_MODE
 if service_mode:
  SERVICE_MODE=True
  HOST=os.environ.get('SMART_LIBRARY_HOST','0.0.0.0')
 init()
 protect_thumbnail_cache()
 # Cada versão tem sua porta; se estiver ocupada, escolhe outra na sequência.
 ports = [PORT] if (os.getenv('SMART_LIBRARY_PORT') or service_mode) else range(PORT, PORT + 6)
 httpd = None
 for port in ports:
  try:
   httpd = ThreadingHTTPServer((HOST, port), Handler)
   break
  except OSError as exc:
   # Apenas conflitos de porta devem ser contornados.
   if getattr(exc, 'winerror', None) != 10048 and getattr(exc, 'errno', None) not in (48, 98, 10048):
    raise
 if httpd is None:
  raise OSError('Todas as portas disponíveis para o Smart Library estão ocupadas.')
 url = f'http://127.0.0.1:{httpd.server_port}' if HOST in ('0.0.0.0','::') else f'http://{HOST}:{httpd.server_port}'
 print('\n' + '=' * 55, flush=True)
 print(' SMART LIBRARY v1.0.15 -  SERVIDOR INICIADO', flush=True)
 print(' Acesse: ' + url, flush=True)
 print(' Para acesso pela rede, use http://IP-DO-PC:'+str(httpd.server_port), flush=True)
 print(' Mantenha esta janela aberta durante o uso.' if not service_mode else ' Executando como servico Windows.', flush=True)
 print(' Para encerrar: Ctrl+C ou feche esta janela.', flush=True)
 print('=' * 55 + '\n', flush=True)
 # Não abre páginas antigas: navegador é iniciado APÓS a porta estar ativa.
 if os.name == 'nt' and not service_mode and '--no-browser' not in sys.argv:
  threading.Timer(0.6, lambda: webbrowser.open(url)).start()
 if stop_event is not None:
  def wait_stop():
   stop_event.wait()
   httpd.shutdown()
  threading.Thread(target=wait_stop,daemon=True).start()
 try:
  httpd.serve_forever()
 except KeyboardInterrupt:
  print('\nSmart Library encerrado.', flush=True)
 finally:
  httpd.server_close()

if __name__=='__main__':
 try:main()
 except Exception as exc:
  print(f'\nERRO AO INICIAR SMART LIBRARY: {exc}', file=sys.stderr, flush=True)
  sys.exit(1)
