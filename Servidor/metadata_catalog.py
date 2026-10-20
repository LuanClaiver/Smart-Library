"""Leitura de nomes locais e pesquisa OPT-IN de metadados públicos.

Não consulta serviços externos durante o escaneamento. Nunca pesquisa itens privados.
Fontes gratuitas: iTunes Search API, Steam Store e MusicBrainz.
Opcional: TMDb com token configurado pelo usuário em Dados/metadados.json.
"""
from __future__ import annotations
import json
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

USER_AGENT = 'SmartLibrary/1.0.17 (personal local media catalog; metadata lookup)'
VIDEO_TAGS = re.compile(r'(?i)\b(?:2160p|1080p|720p|480p|x264|x265|h264|h265|hevc|bluray|blu-ray|brrip|bdrip|webrip|web-dl|dvdrip|hdtv|hdr|dublado|legendado|dual.audio|proper|repack|fitgirl|dodi|codex|multi\d*|yify|rarbg|aac|dts)\b')
EPISODE = re.compile(r'(?i)\bS(\d{1,2})[ ._-]*E(\d{1,3})(?:[ ._-]*E\d{1,3})?\b|\b(\d{1,2})x(\d{1,3})\b')
YEAR = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')


def clean_name(name):
    value = re.sub(r'\.[a-z0-9]{2,5}$', '', str(name).split('\\')[-1].split('/')[-1], flags=re.I)
    value = re.sub(r'\[(?:FitGirl|DODI|CODEX|ElAmigos|Repack)[^]]*\]', ' ', value, flags=re.I)
    value = VIDEO_TAGS.sub(' ', value)
    value = re.sub(r'[._]+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip(' -_[]()')
    return value[:180]


def parse_local(path, category=''):
    """Retorna metadados mínimos sem acessar a rede ou modificar o arquivo."""
    p = str(path).replace('\\', '/')
    stem = p.rsplit('/', 1)[-1]
    clean = clean_name(stem)
    year_match = YEAR.search(clean)
    year = int(year_match.group(1)) if year_match else None
    data = {'title': clean, 'year': year, 'series_title': '', 'season': None, 'episode': None, 'collection': ''}
    match = EPISODE.search(clean)
    if match:
        data['season'] = int(match.group(1) or match.group(3))
        data['episode'] = int(match.group(2) or match.group(4))
        title = clean_name(clean[:match.start()])
        if not title:
            parts = p.split('/')
            title = clean_name(parts[-3] if len(parts)>2 and re.search(r'(?i)temporada|season', parts[-2]) else parts[-2]) if len(parts)>1 else ''
        data['series_title'] = title or 'Série sem título'
        data['title'] = title or clean
    elif category == 'Séries':
        # Temporada 1/Ep 02, ou pastas /Série/Season 01/...
        parent = p.split('/')[-2] if '/' in p else ''
        season_dir = re.search(r'(?i)(?:temporada|season)\s*[._ -]*(\d{1,2})', parent)
        if season_dir:
            data['season'] = int(season_dir.group(1))
            pieces = p.split('/')
            data['series_title'] = clean_name(pieces[-3]) if len(pieces) >= 3 else clean
        else:
            data['series_title'] = clean_name(parent) if parent and not re.search('(?i)filmes|series|séries|videos|vídeos',parent) else clean
    if category == 'Filmes':
        folder = p.split('/')[-2] if '/' in p else ''
        if folder and not re.search(r'(?i)^(?:filmes|movies|videos|vídeos|downloads|media|mídia)$',folder):
            # Pastas de coleção reais, ignorando pastas com nome idêntico ao filme.
            folder_clean = clean_name(folder)
            if folder_clean and folder_clean.casefold() != clean.casefold():
                data['collection'] = folder_clean
    return data


def _norm(text):
    value = unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode().casefold()
    return re.sub('[^a-z0-9]+',' ',value).strip()


def confidence(requested, actual):
    a, b = _norm(requested), _norm(actual)
    if not a or not b:return 0.0
    if a==b:return 1.0
    return round(SequenceMatcher(None,a,b).ratio(),3)


def _get(url):
    # Apenas URLs fixas criadas internamente. Sem URL fornecida pelo navegador.
    req = Request(url, headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    with urlopen(req,timeout=8) as result:
        raw=result.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Resposta de metadados muito grande')
    return json.loads(raw)


def _normal_result(title, cover='', overview='', year=None, genre='', artist='', collection='', provider='', record_id='', url=''):
    if year is not None:
        try:year=int(str(year)[:4])
        except (TypeError,ValueError):year=None
    return {'title':str(title or '')[:180], 'cover':str(cover or '')[:700],
            'overview':str(overview or '')[:1800], 'year':year,
            'genre':str(genre or '')[:120], 'artist':str(artist or '')[:180],
            'collection':str(collection or '')[:180], 'provider':provider,
            'record_id':str(record_id or '')[:100], 'url':str(url or '')[:500]}


def search_itunes(query,category):
    entity={'Filmes':'movie','Séries':'tvSeason','Músicas':'song'}.get(category)
    if not entity:return []
    data=_get('https://itunes.apple.com/search?'+urlencode({'term':query,'entity':entity,'limit':12,'country':'BR','lang':'pt_br'}))
    out=[]
    for r in data.get('results',[]):
        name=r.get('trackName') or r.get('collectionName') or ''
        cover=(r.get('artworkUrl100') or '').replace('100x100bb','600x600bb').replace('100x100','600x600')
        if not name:continue
        out.append(_normal_result(name,cover,r.get('longDescription') or r.get('shortDescription') or '',
                                  r.get('releaseDate','')[:4],r.get('primaryGenreName',''),
                                  r.get('artistName',''),r.get('collectionName','') if category=='Séries' else '',
                                  'iTunes',r.get('trackId') or r.get('collectionId'),r.get('trackViewUrl') or r.get('collectionViewUrl')))
    return out


def search_steam(query):
    data=_get('https://store.steampowered.com/api/storesearch/?'+urlencode({'term':query,'l':'portuguese','cc':'BR'}))
    out=[]
    for r in data.get('items',[])[:12]:
        try:app=int(r['id'])
        except (KeyError,ValueError,TypeError):continue
        out.append(_normal_result(r.get('name',''),f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app}/library_600x900.jpg',
                                  provider='Steam',record_id=app,url=f'https://store.steampowered.com/app/{app}/'))
    return out


def search_musicbrainz(query):
    data=_get('https://musicbrainz.org/ws/2/recording/?'+urlencode({'query':f'recording:"{query}"','fmt':'json','limit':10}))
    out=[]
    for r in data.get('recordings',[])[:10]:
        releases=r.get('releases',[]);release=releases[0] if releases else {}
        credit=r.get('artist-credit',[])
        artist=''.join(x.get('name', '') for x in credit if isinstance(x,dict))
        mbid=str(release.get('id') or '')
        cover=f'https://coverartarchive.org/release/{mbid}/front-250' if mbid else ''
        out.append(_normal_result(r.get('title',''),cover,year=release.get('date','')[:4],artist=artist,
                                  collection=release.get('title',''),provider='MusicBrainz',record_id=r.get('id',''),
                                  url=f'https://musicbrainz.org/recording/{r.get("id","")}'))
    return out


def search_tmdb(query,category,token):
    if not token or category not in ('Filmes','Séries'):return []
    endpoint='movie' if category=='Filmes' else 'tv'
    # Read API v3 key only from local Dados config; never return the key.
    data=_get('https://api.themoviedb.org/3/search/'+endpoint+'?'+urlencode({'api_key':token,'query':query,'language':'pt-BR','include_adult':'false'}))
    out=[]
    for r in data.get('results',[])[:12]:
        title=r.get('title') or r.get('name') or ''
        poster=r.get('poster_path') or ''
        out.append(_normal_result(title,'https://image.tmdb.org/t/p/w500'+poster if poster.startswith('/') else '',
                                  r.get('overview',''),r.get('release_date','')[:4] or r.get('first_air_date','')[:4],
                                  provider='TMDB',record_id=r.get('id'),
                                  url=f'https://www.themoviedb.org/{endpoint}/{r.get("id", "")}'))
    return out


def lookup(query,category,provider='auto',tmdb_key=''):
    """Pesquisa somente quando solicitada pelo Admin; retorna ordenado por semelhança."""
    query=clean_name(query).strip()
    if len(query)<2 or len(query)>180:raise ValueError('Título inválido.')
    if category not in ('Jogos','Filmes','Séries','Músicas'):raise ValueError('Categoria sem pesquisa de metadados.')
    providers={'auto':(['TMDB','iTunes'] if tmdb_key and category in ('Filmes','Séries') else ['iTunes'] if category in ('Filmes','Séries','Músicas') else ['Steam']),
               'steam':['Steam'],'itunes':['iTunes'],'musicbrainz':['MusicBrainz'],'tmdb':['TMDB']}
    if provider not in providers:raise ValueError('Fonte inválida.')
    errors=[]; results=[]
    for source in providers[provider]:
        try:
            if source=='Steam' and category=='Jogos':results.extend(search_steam(query))
            if source=='iTunes' and category in ('Filmes','Séries','Músicas'):results.extend(search_itunes(query,category))
            if source=='MusicBrainz' and category=='Músicas':results.extend(search_musicbrainz(query))
            if source=='TMDB' and category in ('Filmes','Séries'):results.extend(search_tmdb(query,category,tmdb_key))
        except Exception as exc:
            errors.append(source+': '+type(exc).__name__)
    # Se não houve resultados da fonte principal, tentar outra fonte gratuita.
    if not results and provider=='auto' and category in ('Filmes','Séries','Músicas') and 'iTunes' not in providers[provider]:
        try:results.extend(search_itunes(query,category))
        except Exception as exc:errors.append('iTunes: '+type(exc).__name__)
    if not results and provider=='auto' and category=='Músicas':
        try:results.extend(search_musicbrainz(query))
        except Exception as exc:errors.append('MusicBrainz: '+type(exc).__name__)
    for r in results:r['confidence']=confidence(query,r['title'])
    results.sort(key=lambda item:item['confidence'],reverse=True)
    return {'results':results[:12], 'errors':errors, 'query':query}
