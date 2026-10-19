"""Analisador de arquivos duplicados, somente leitura, sem incluir area protegida."""
import hashlib, os, re, threading, time, unicodedata
from collections import defaultdict
from pathlib import Path

class DuplicateFinder:
    def __init__(self, db_factory, is_private):
        self.db_factory = db_factory
        self.is_private = is_private
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.result = self._empty()
        self.worker = None

    @staticmethod
    def _empty():
        return dict(running=False, phase='Aguardando analise', files=0, candidates=0,
                    checked=0, bytes_read=0, started=None, finished=None,
                    exact=[], similar=[], exact_groups=0, similar_groups=0,
                    estimated_savings=0, truncated=False, error='', cancelled=False)

    def snapshot(self):
        with self.lock:
            return {**self.result, 'exact': list(self.result['exact']), 'similar': list(self.result['similar'])}

    def _update(self, **kw):
        with self.lock:
            self.result.update(kw)

    def start(self):
        with self.lock:
            if self.result['running']: return False
            self.result = self._empty()
            self.result.update(running=True, phase='Coletando arquivos...', started=time.strftime('%d/%m/%Y %H:%M:%S'))
            self.stop_event.clear()
            self.worker = threading.Thread(target=self._run, daemon=True, name='smart-library-duplicates')
            self.worker.start()
            return True

    def cancel(self):
        if self.snapshot()['running']:
            self.stop_event.set()
            return True
        return False

    @staticmethod
    def _normal_name(path):
        name = Path(path).stem
        name = unicodedata.normalize('NFKD', name)
        name = ''.join(c for c in name if not unicodedata.combining(c)).lower()
        name = re.sub(r'\s*\((?:copia|copy|\d+)\)\s*$', '', name)
        name = re.sub(r'(?i)[\s._-]*(?:copia|copy)(?:[\s._-]*\d+)?$', '', name)
        name = re.sub(r'[_\-.]+', ' ', name)
        return re.sub(r'\s+', ' ', name).strip()

    def _run(self):
        try:
            with self.db_factory() as db:
                rows = [dict(x) for x in db.execute('''SELECT i.id,i.path,i.name,i.size,i.mtime,i.extension,
                    s.path AS source_path FROM items i JOIN sources s ON s.id=i.source_id
                    WHERE i.kind='file' AND i.available=1 AND i.hidden=0 AND i.ignored=0''')]
            valid = []
            unique_files = set()
            for row in rows:
                if self.stop_event.is_set(): break
                path = Path(row['path'])
                try:
                    if path.is_symlink() or self.is_private(row['path'], row['source_path']): continue
                    st = path.stat()
                    if not path.is_file() or st.st_size != row['size'] or st.st_size < 1: continue
                    inode = (st.st_dev, st.st_ino)
                    if inode in unique_files: continue  # Hard links nao liberam espaco ao apagar uma entrada.
                    unique_files.add(inode)
                    valid.append({**row, 'size': st.st_size, 'stat_mtime': st.st_mtime_ns})
                except (OSError, ValueError): continue
            self._update(files=len(valid))
            # Candidatos por nome normalizado: podem ser versoes diferentes, nunca confirmar como identicos.
            byname = defaultdict(list)
            for row in valid:
                norm = self._normal_name(row['path'])
                if len(norm)>=4:
                    byname[(norm, row['extension'].lower())].append(row)
            similar = [lst for lst in byname.values() if len(lst)>1]
            similar.sort(key=lambda group: (-sum(r['size'] for r in group), group[0]['name']))
            # Agrupar por tamanho e comparar SHA-256 somente entre arquivos do mesmo tamanho.
            bysize = defaultdict(list)
            for row in valid:
                bysize[row['size']].append(row)
            groups = [g for g in bysize.values() if len(g)>1]
            # Comeca com arquivos pequenos para fornecer resultados mais rapidamente.
            groups.sort(key=lambda g:g[0]['size'])
            self._update(candidates=sum(len(g) for g in groups), phase='Comparando conteudo (SHA-256)...')
            hashed = defaultdict(list)
            processed = 0; bytes_read = 0
            for group in groups:
                for row in group:
                    if self.stop_event.is_set(): break
                    path = Path(row['path'])
                    try:
                        digest = hashlib.sha256()
                        with path.open('rb') as f:
                            while True:
                                if self.stop_event.is_set(): break
                                block = f.read(1024*1024)
                                if not block: break
                                digest.update(block)
                                bytes_read += len(block)
                        if self.stop_event.is_set(): break
                        after = path.stat()
                        if after.st_size != row['size'] or after.st_mtime_ns != row['stat_mtime']: continue
                        hashed[(row['size'], digest.hexdigest())].append(row)
                    except (OSError, PermissionError): pass
                    processed += 1
                    if processed%5 == 0:self._update(checked=processed, bytes_read=bytes_read)
                if self.stop_event.is_set():break
            exact_groups = [g for g in hashed.values() if len(g)>1]
            exact_groups.sort(key=lambda g:-(len(g)-1)*g[0]['size'])
            def present(group):
                return {'size':group[0]['size'], 'files':[{'id':r['id'],'name':r['name'], 'path':r['path'],'size':r['size']} for r in group]}
            # Itens idênticos nao precisam aparecer tambem nos grupos de nomes semelhantes.
            exact_sets = {frozenset(r['id'] for r in g) for g in exact_groups}
            similar = [g for g in similar if frozenset(r['id'] for r in g) not in exact_sets]
            self._update(running=False, phase='Analise concluida' if not self.stop_event.is_set() else 'Analise interrompida',
                checked=processed, bytes_read=bytes_read, exact=[present(g) for g in exact_groups[:150]],
                similar=[present(g) for g in similar[:150]], exact_groups=len(exact_groups),
                similar_groups=len(similar), estimated_savings=sum((len(g)-1)*g[0]['size'] for g in exact_groups),
                truncated=len(exact_groups)>150 or len(similar)>150, cancelled=self.stop_event.is_set(),
                finished=time.strftime('%d/%m/%Y %H:%M:%S'))
        except Exception as error:
            self._update(running=False, phase='Erro', error=str(error),finished=time.strftime('%d/%m/%Y %H:%M:%S'))
