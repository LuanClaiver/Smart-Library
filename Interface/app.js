'use strict';
const $ = id => document.getElementById(id);
const ico = name => `<svg aria-hidden="true"><use href="#i-${name}"></use></svg>`;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const categories = [
 ['Todos','grid'],['Jogos','game'],['Filmes','movie'],['Séries','tv'],['Vídeos','movie'],['Músicas','music'],
 ['Imagens','image'],['Documentos','file'],['Instaladores','package'],['Outros','folder'],['Transferências','drive'],['Duplicados','copy'],['Quarentena','trash'],['Locais','drive'],['Protegidos','lock']
];
let currentCategory='Todos', page=1, editId=null, searchTimeout=null, lastStatus=null, wasScanning=false, itemsMap={},viewMode='grid';
let isAdmin=false,serviceMode=false,canLocate=false,mediaView='folders',mediaSource='',mediaFolder='',mediaCollection='',folderQuerySequence=0;
let metadataTaskActive=false,metadataResults=[],metadataSearchBusy=false;
let gameFilter='', privateReady=false,privateIsOpen=false,subcategoryFilter='',extensionFilter='',filtersRequest=0;
let browseData=null,browseMode='folder',browseTarget='addPath',selectedExecutable=null,browseRequest=0;
let currentTrack=null,musicQueue=[],musicQueueIndex=-1,musicQueuePrivate=false,viewerItemId=null,musicMinimized=false,queueReady=Promise.resolve();
let duplicateResults={},duplicateItemMap={};
let multiMode=false,multiTrashOpen=false;
const multiSelected=new Map(); // {id, expected_path, name}; persiste ao mudar de página.
function syncMulti(){
 const count=multiSelected.size;
 $('multiToolbar').classList.toggle('hidden',!isAdmin||['Locais','Duplicados','Quarentena','Transferências'].includes(currentCategory));
 $('multiActions').classList.toggle('hidden',!multiMode);
 $('toggleMulti').setAttribute('aria-pressed',String(multiMode));
 $('toggleMulti').innerHTML=ico('check')+(multiMode?' Sair da seleção':' Selecionar vários');
 $('multiCount').textContent=count+' '+(count===1?'selecionado':'selecionados');
 $('multiTrash').innerHTML=ico('trash')+(serviceMode?' Quarentena (':' Lixeira (')+count+')';
 $('multiTrash').disabled=count===0;
 $('items').classList.toggle('select-mode',multiMode);
 document.querySelectorAll('#items .media-card').forEach(card=>{
  const input=card.querySelector('[data-select]');if(!input)return;
  input.checked=multiSelected.has(input.dataset.select);
  card.classList.toggle('selected',input.checked);
 });
}
function resetMulti(){multiMode=false;multiTrashOpen=false;multiSelected.clear();syncMulti();}
function setMultiSelected(id,checked){
 const item=itemsMap[id];
 if(checked){
  if(!item)return;
  if(multiSelected.size>=100&&!multiSelected.has(id)){toast('Limite de 100 itens por operação.','error');syncMulti();return;}
  multiSelected.set(id,{id:item.id,expected_path:item.path,name:item.name,hidden:item.hidden});
 }else multiSelected.delete(id);
 syncMulti();
}
function selectMultiPage(){
 for(const item of Object.values(itemsMap)){
  if(multiSelected.size>=100)break;
  multiSelected.set(item.id,{id:item.id,expected_path:item.path,name:item.name,hidden:item.hidden});
 }
 syncMulti();
 if(multiSelected.size>=100)toast('Até 100 itens por operação.');
}
function openMultiTrash(){
 if(!multiSelected.size)return;
 multiTrashOpen=true;
 const examples=[...multiSelected.values()].slice(0,4).map(x=>'• '+x.name).join('\n');
 $('trashDescription').textContent=`Você selecionou ${multiSelected.size} ${multiSelected.size===1?'item':'itens'} para ${serviceMode?'mover à Quarentena do Smart Library':'enviar à Lixeira do Windows'}.\n\n${examples}${multiSelected.size>4?'\n• E outros '+(multiSelected.size-4)+' itens':''}\n\nRevise a seleção. Pastas incluem todo seu conteúdo. ${serviceMode?'Você poderá restaurar ou excluir definitivamente na aba Quarentena.':'A operação altera os arquivos originais.'}`;
 $('trashConfirmation').value='';showDialog('trashDialog');
}
async function performMultiTrash(){
 const chosen=[...multiSelected.values()];
 const button=$('trashForm').querySelector('[type="submit"]');button.disabled=true;
 try{
  const result=await api('/api/bulk-trash','POST',{confirmation:'EXCLUIR',items:chosen});
  closeDialog('trashDialog');multiTrashOpen=false;
  if(currentTrack&&chosen.some(x=>x.id===currentTrack.id))stopMusic();
  const finished=result.deleted_count||0;
  resetMulti();
  await refreshTypeFilters();await refresh();await loadItems();
  const failures=(result.failed||[]).length;
  const nested=result.ignored_nested||0;
  const text=finished+' '+(finished===1?'item enviado':'itens enviados')+(result.quarantined?' à Quarentena.':' à Lixeira.')+
   (nested?' '+nested+' selecionado(s) já estavam dentro de uma pasta excluída.':'')+
   (failures?' '+failures+' não puderam ser enviados e permanecem no disco.':'');
  if(failures)await message('Operação parcialmente concluída',text,{kind:'error'});
  else toast(text,'success');
 }catch(error){await message('Não foi possível enviar à Lixeira',error.message,{kind:'error'});}
 finally{button.disabled=false;}
}

async function api(url,method='GET',payload){
 const options={method};
 if(method!=='GET'){options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(payload??{});}
 let response;
 try{response=await fetch(url,options);}catch(_){throw new Error('Não foi possível conectar ao Smart Library. Verifique se a janela do servidor está aberta.');}
 let data;
 try{data=await response.json();}catch(_){throw new Error('O servidor retornou uma resposta inesperada.');}
 if(!response.ok)throw new Error(data.error||'Não foi possível concluir a operação.');
 return data;
}
function toast(message,kind='info'){
 const node=document.createElement('div');node.className='toast '+kind;node.innerHTML=ico(kind==='error'?'alert':kind==='success'?'check':'info');
 const span=document.createElement('span');span.textContent=message;node.appendChild(span);$('toasts').appendChild(node);
 setTimeout(()=>node.remove(),4700);
}
function message(title,description,{confirm=false,confirmLabel='Entendi',kind='info'}={}){
 return new Promise(resolve=>{
  const d=$('messageDialog');
  // Evita empilhar alertas nativos; sempre usa o tema atual.
  if(d.open)d.close();
  $('messageTitle').textContent=title;$('messageText').textContent=description;
  $('messageSymbol').innerHTML=ico(kind==='error'?'alert':kind==='success'?'check':'info');
  $('messageCancel').classList.toggle('hidden',!confirm);
  $('messageAccept').textContent=confirmLabel;
  let accepted=false;
  $('messageAccept').onclick=()=>{accepted=true;d.close();};
  $('messageCancel').onclick=()=>d.close();
  $('messageClose').onclick=()=>d.close();
  d.onclose=()=>{d.onclose=null;resolve(accepted);};
  d.showModal();
 });
}
function showDialog(id){const d=$(id);if(!d.open)d.showModal();}
function closeDialog(id){const d=$(id);if(d.open)d.close();}
const formatTitles={'.jpg':'JPG · Imagem','.jpeg':'JPEG · Imagem','.png':'PNG · Imagem','.webp':'WebP · Imagem','.gif':'GIF · Imagem','.bmp':'BMP · Imagem','.mp3':'MP3 · Áudio','.flac':'FLAC · Áudio','.wav':'WAV · Áudio','.m4a':'M4A · Áudio','.ogg':'OGG · Áudio','.mp4':'MP4 · Vídeo','.mkv':'MKV · Vídeo','.avi':'AVI · Vídeo','.mov':'MOV · Vídeo','.webm':'WebM · Vídeo','.pdf':'PDF · Documento','.iso':'ISO · Imagem de disco','.exe':'EXE · Aplicativo','.zip':'ZIP · Compactado'};
function formatLabel(ext){return ext==='[pasta]'?'Pastas':ext==='[sem extensão]'?'Sem extensão':formatTitles[ext]||(ext.replace(/^\./,'').toUpperCase()+' · Arquivo');}
async function refreshTypeFilters(){
 if(['Locais','Duplicados','Quarentena','Transferências'].includes(currentCategory))return;
 const seq=++filtersRequest;
 const requestCategory=currentCategory,requestedSub=subcategoryFilter;
 try{
  const result=await api('/api/filters?'+new URLSearchParams({category:requestCategory,subcategory:requestedSub}));
  if(seq!==filtersRequest||currentCategory!==requestCategory||subcategoryFilter!==requestedSub)return;
  $('subCategoryWrap').classList.toggle('hidden',!['Protegidos','Todos'].includes(requestCategory));
  const choices=result.categories.map(x=>`<option value="${escapeHTML(x.name)}">${escapeHTML(x.name)} (${x.count})</option>`).join('');
  $('categoryFilter').innerHTML='<option value="">Todas as categorias</option>'+choices;
  $('categoryFilter').value=Array.from($('categoryFilter').options).some(o=>o.value===subcategoryFilter)?subcategoryFilter:'';
  const options=result.formats.map(x=>`<option value="${escapeHTML(x.ext)}">${escapeHTML(formatLabel(x.ext))} (${x.count})</option>`).join('');
  $('extensionFilter').innerHTML='<option value="">Todos os formatos</option>'+options;
  if(!Array.from($('extensionFilter').options).some(o=>o.value===extensionFilter))extensionFilter='';
  $('extensionFilter').value=extensionFilter;
  $('filterHint').textContent=extensionFilter?formatLabel(extensionFilter):'Formatos reais detectados nos arquivos';
 }catch(e){if(seq===filtersRequest)$('filterHint').textContent='Filtros indisponíveis: '+e.message;}
}
function renderNav(){
 const counts=Object.fromEntries((lastStatus?.stats||[]).map(s=>[s.category,s.n]));
 $('nav').innerHTML=categories.filter(([name])=>isAdmin||!['Protegidos','Duplicados','Locais','Quarentena','Transferências'].includes(name)).map(([name,icon])=>`<button class="side-link ${currentCategory===name?'active':''}" data-category="${name}" type="button">${ico(icon)}<span>${name}</span>${counts[name]?`<span class="side-count">${counts[name]}</span>`:''}</button>`).join('');
 $('nav').querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>changeCategory(button.dataset.category)));
}
async function changeCategory(category,verifiedProtected=false){
 if(category!==currentCategory){mediaCollection='';mediaFolder='';}
 if(!isAdmin&&['Protegidos','Duplicados','Locais','Quarentena','Transferências'].includes(category)){openPrivateDialog(true);return;}
 if(category==='Protegidos'&&!verifiedProtected){
  if(!isAdmin){openPrivateDialog(true);return;}
  try{await api('/api/protected/lock','POST');}catch(e){}
  $('protectedPassword').value='';showDialog('protectedDialog');$('protectedPassword').focus();return;
 }
 if(currentCategory==='Protegidos'&&category!=='Protegidos'){
  try{await api('/api/protected/lock','POST');}catch(e){}
  privateIsOpen=false;if(musicQueuePrivate)stopMusic();itemsMap={};
 }
 resetMulti();
 currentCategory=category;page=1;subcategoryFilter='';extensionFilter='';mediaView='folders';mediaSource='';mediaFolder='';renderNav();refreshTypeFilters();syncMulti();
 $('privateLock').classList.toggle('hidden',!isAdmin||category!=='Protegidos');
 $('gameFilters').classList.toggle('hidden',category!=='Jogos');
 if(category!=='Jogos')gameFilter='';
 renderGameFilters();
 $('breadcrumb').textContent=category==='Todos'?'Todos os itens':category==='Locais'?'Armazenamento':category;
 const all=category==='Todos',locations=category==='Locais',isPrivate=category==='Protegidos';
 $('heading').innerHTML=all?'Tudo que é seu,<br><em>em um só lugar.</em>':locations?'Seus discos e pastas,<br><em>sob controle.</em>':isPrivate?'Sua coleção privada,<br><em>acesso protegido.</em>':`${escapeHTML(category)}<br><em>em um só lugar.</em>`;
 $('subtitle').textContent=isPrivate?'Conteúdo privado acessível somente após confirmação da senha.':locations?'Gerencie os locais indexados sem modificar seus arquivos.':all?'Seus jogos, filmes, músicas e arquivos organizados. Você sabe exatamente onde cada um está.':`Explore seus conteúdos em ${category.toLowerCase()}, com acesso ao local original.`;
 const duplicates=category==='Duplicados',quarantine=category==='Quarentena',transfers=category==='Transferências';
 $('library').classList.toggle('hidden',locations||duplicates||quarantine||transfers);$('sources').classList.toggle('hidden',!locations);$('duplicatesSection').classList.toggle('hidden',!duplicates);$('quarantineSection').classList.toggle('hidden',!quarantine);$('transfersSection').classList.toggle('hidden',!transfers);
 if(duplicates)refreshDuplicates();if(quarantine)refreshQuarantine();
 document.querySelector('.hero').classList.toggle('compact-hero',!all);$('stats').classList.toggle('compact-hide',!all);
 $('collectionTitle').childNodes[0].textContent=all?'Minha coleção ':category+' ';
 if(!locations&&!duplicates&&!quarantine&&!transfers)loadItems();
}
function renderStats(data){
 const byName=Object.fromEntries(data.stats.map(x=>[x.category,x.n]));
 const entries=[
 ['Itens catalogados',data.total,'grid','Conteúdo indexado'],
 ['Pastas e discos',data.sources.length,'drive','Fontes cadastradas'],
 ['Jogos',byName.Jogos||0,'game','Sua coleção gamer'],
 ['Filmes, séries e músicas',(byName.Filmes||0)+(byName.Séries||0)+(byName.Músicas||0),'movie','Mídia disponível']
 ];
 $('stats').innerHTML=entries.map(([title,value,icon,hint])=>`<article class="stat"><div class="stat-top"><span>${title}</span><span class="stat-ico">${ico(icon)}</span></div><div class="stat-num">${Number(value).toLocaleString('pt-BR')}</div><div class="stat-note">${hint}</div></article>`).join('');
}
function renderSources(sources){
 $('sourceList').innerHTML=sources.length?sources.map(s=>`<div class="source-row"><div><div class="source-path">${ico('folder')} ${escapeHTML(s.path)}</div><div class="source-tags"><span class="tag">${escapeHTML(s.category)}</span><span class="tag ${s.online?'online':'offline'}">${s.online?'● Disponível':'○ Desconectado'}</span><span class="tag">${s.recursive?'Com subpastas':'Apenas pasta principal'}</span></div></div><button type="button" class="btn btn-muted" data-remove="${escapeHTML(s.id)}">${ico('trash')} Remover catálogo</button></div>`).join(''):`<div class="empty-state">${ico('drive')}<strong>Nenhum local cadastrado</strong><span>Adicione um disco inteiro ou uma pasta específica para começar.</span></div>`;
 $('sourceList').querySelectorAll('[data-remove]').forEach(b=>b.addEventListener('click',()=>removeSource(b.dataset.remove)));
 $('sourceList').querySelectorAll('[data-remove]').forEach(b=>b.classList.toggle('hidden',!isAdmin));
}
async function refresh(){
 try{
  const response=await api('/api/status');lastStatus=response;serviceMode=Boolean(response.service_mode);canLocate=['localhost','127.0.0.1','[::1]'].includes(location.hostname.toLowerCase());document.body.classList.toggle('remote-view',!canLocate);['viewerLocate','editLocate','musicLocate'].forEach(id=>$(id)?.classList.toggle('hidden',!canLocate));
  const auth=await api('/api/private/status');privateIsOpen=Boolean(auth.protected_unlocked);if(isAdmin&&!auth.unlocked){isAdmin=false;privateIsOpen=false;refreshAdminUI();resetMulti();if(musicQueuePrivate)stopMusic();if(['Protegidos','Transferências','Quarentena','Duplicados','Locais'].includes(currentCategory))await changeCategory('Todos');}else if(!isAdmin&&auth.unlocked){isAdmin=true;refreshAdminUI();renderNav();}
  if(musicQueuePrivate&&currentTrack&&!auth.protected_unlocked)stopMusic();
  renderStats(response);renderSources(response.sources);renderNav();
  const filterSettings=response.media_filters||{ocultar_midias_steam:true};
  $('ignoreSteamMedia').checked=Boolean(filterSettings.ocultar_midias_steam);
  $('ignoreSteamMedia').disabled=!isAdmin;
  $('ignoredSteamCount').textContent=Number(response.ignored_media_count||0).toLocaleString('pt-BR')+' arquivo(s) interno(s) de jogos ocultado(s) do catálogo';
  if($('backupSummary'))$('backupSummary').textContent=response.backup?.last?'Último backup: '+response.backup.last.replace('T',' ')+' · '+response.backup.count+' cópia(s)':'Backup automático ainda não criado';
  const f=$('sourceFilter'),old=f.value;
  f.innerHTML='<option value="">Todos os locais</option>'+response.sources.map(s=>`<option value="${escapeHTML(s.id)}">${escapeHTML(s.path)}</option>`).join('');
  f.value=response.sources.some(s=>s.id===old)?old:'';
  if(response.status.running){$('status').innerHTML=`<div class="status-note">${ico('refresh')} Escaneando... ${response.status.found.toLocaleString('pt-BR')} itens identificados. Pasta: ${escapeHTML(response.status.current)}</div>`;}
  else if(response.status.error){$('status').innerHTML=`<div class="status-note warn">${ico('alert')} ${escapeHTML(response.status.error)}</div>`;}
  else $('status').innerHTML='';
  if(wasScanning&&!response.status.running){toast('Escaneamento concluído!','success');refreshTypeFilters();loadItems();}
  wasScanning=response.status.running;
  if(currentCategory==='Duplicados')refreshDuplicates();
 }catch(error){$('status').innerHTML=`<div class="status-note warn">${ico('alert')} ${escapeHTML(error.message)}</div>`;}
}
function isMediaCategory(){return currentCategory==='Filmes'||currentCategory==='Séries';}
function mediaFolderCard(f){
 const cover=f.cover_id?`<img loading="lazy" alt="" src="/api/thumb/${encodeURIComponent(f.cover_id)}" onerror="this.hidden=true">`:'';
 return `<button type="button" class="media-directory" data-media-source="${escapeHTML(f.source_id)}" data-media-folder="${escapeHTML(f.path)}"><div class="media-directory-cover">${ico('folder')}${cover}</div><div class="media-directory-name" title="${escapeHTML(f.name)}">${escapeHTML(f.name)}</div><div class="media-directory-sub">${f.count.toLocaleString('pt-BR')} ${f.count===1?'vídeo':'vídeos'}</div></button>`;
}
function renderMediaFolderNav(data){
 const bar=$('mediaFolderBar');bar.classList.remove('hidden');
 bar.querySelectorAll('[data-media-view]').forEach(b=>b.classList.toggle('active',b.dataset.mediaView===mediaView));
 const crumbs=[`<button type="button" data-media-reset>Biblioteca de ${escapeHTML(currentCategory)}</button>`];
 if(mediaSource && data.root){
  const root=data.root,here=data.folder||root,separator=root.includes('\\')?'\\':'/';
  const rootName=root.split(/[\\/]/).filter(Boolean).pop()||root;
  crumbs.push(`<span>›</span><button type="button" data-media-go="${escapeHTML(root)}">${escapeHTML(rootName)}</button>`);
  let p=root;
  for(const segment of here.slice(root.length).split(/[\\/]/).filter(Boolean)){
   p+=((p.endsWith(separator))?'':separator)+segment;
   crumbs.push(`<span>›</span><button type="button" data-media-go="${escapeHTML(p)}">${escapeHTML(segment)}</button>`);
  }
 }
 $('mediaFolderPath').innerHTML=crumbs.join('');
}
async function openMediaDirectory(source,folder){mediaSource=source;mediaFolder=folder;mediaCollection='';page=1;resetMulti();await loadItems();}
async function openMediaCollection(name){mediaCollection=name;page=1;resetMulti();await loadItems();}
function mediaCollectionCard(f){
 return `<button type="button" class="media-directory" data-media-collection="${escapeHTML(f.name)}"><div class="media-directory-cover">${ico('folder')}${f.cover_id?`<img loading="lazy" alt="" src="/api/thumb/${encodeURIComponent(f.cover_id)}" onerror="this.hidden=true">`:''}</div><div class="media-directory-name" title="${escapeHTML(f.name)}">${escapeHTML(f.name)}</div><div class="media-directory-sub">${f.count} ${f.count===1?'item':'itens'}</div></button>`;
}
async function refreshQuarantine(){
 if(!isAdmin)return;
 const node=$('quarantineList');node.innerHTML='<p class="modal-desc">Consultando a Quarentena…</p>';
 try{
  const res=await api('/api/quarantine');
  node.innerHTML=res.items.length?res.items.map(x=>`<article class="quarantine-row"><div><strong>${escapeHTML(x.name)}</strong><div class="media-path" title="${escapeHTML(x.original_path)}">${escapeHTML(x.original_path)}</div><small>${escapeHTML(x.created_at)} · ${humanBytes(x.size)}</small></div><div class="quarantine-row-actions"><button type="button" class="btn btn-muted btn-small" data-q-action="restore" data-q-id="${escapeHTML(x.id)}">Restaurar</button><button type="button" class="btn btn-danger btn-small" data-q-action="purge" data-q-id="${escapeHTML(x.id)}">Excluir definitivamente</button></div></article>`).join(''):'<div class="empty-state">Nenhum arquivo aguardando restauração ou exclusão.</div>';
  node.querySelectorAll('[data-q-action]').forEach(b=>b.addEventListener('click',()=>manageQuarantine(b.dataset.qAction,b.dataset.qId)));
 }catch(e){node.textContent=e.message;}
}
function askPurgePhrase(){return new Promise(resolve=>{
 const d=$('purgeDialog');$('purgePhrase').value='';const form=$('purgeForm');
 const submit=e=>{e.preventDefault();if($('purgePhrase').value.trim()!=='APAGAR DEFINITIVAMENTE'){toast('Digite a frase exata para confirmar.','error');return;}d.close();};
 const close=()=>{form.removeEventListener('submit',submit);d.removeEventListener('close',close);resolve($('purgePhrase').value.trim());};
 form.addEventListener('submit',submit);d.addEventListener('close',close);showDialog('purgeDialog');
 });}
async function manageQuarantine(action,id){
 let confirmation='';
 if(action==='purge'){
  if(!await message('Exclusão definitiva','Atenção: este item será apagado PERMANENTEMENTE do disco, sem passar pela Lixeira. Isso não poderá ser desfeito.',{confirm:true,confirmLabel:'Continuar'}))return;
  const typed=await askPurgePhrase();
  if(typed!=='APAGAR DEFINITIVAMENTE')return;
  confirmation=typed;
 }else if(!await message('Restaurar arquivo','Restaurar este item ao caminho original?',{confirm:true,confirmLabel:'Restaurar'}))return;
 try{await api('/api/quarantine/manage','POST',{action,id,confirmation});toast(action==='restore'?'Restauração solicitada.':'Item excluído permanentemente.','success');await refreshQuarantine();await refresh();}
 catch(e){await message('Não foi possível concluir',e.message,{kind:'error'});}
}
async function loadItems(){
 if(['Locais','Duplicados','Quarentena','Transferências'].includes(currentCategory))return;
 const requestedCat=currentCategory,requestedPage=page,requestedQuery=$('query').value,requestedSub=subcategoryFilter,requestedExt=extensionFilter;
 let folderPrefix='',inFolders=isMediaCategory()&&mediaView==='folders'&&!requestedQuery&&!requestedExt;
 const inCollections=isMediaCategory()&&mediaView==='collections'&&!requestedQuery&&!requestedExt;
 $('mediaFolderBar').classList.toggle('hidden',!isMediaCategory());
 try{
  if(inCollections){
   $('mediaFolderBar').classList.remove('hidden');
   const bar=$('mediaFolderBar');bar.querySelectorAll('[data-media-view]').forEach(b=>b.classList.toggle('active',b.dataset.mediaView===mediaView));
   $('mediaFolderPath').innerHTML=`<button type="button" data-media-reset>${escapeHTML(currentCategory)}</button>${mediaCollection?`<span>›</span><strong>${escapeHTML(mediaCollection)}</strong>`:''}`;
   if(!mediaCollection){
    const nav=await api('/api/media/collections?'+new URLSearchParams({category:requestedCat}));
    if(requestedCat!==currentCategory)return;
    const dirs=nav.collections||[];
    $('items').innerHTML=dirs.length?dirs.map(mediaCollectionCard).join(''):'<div class="empty-state">Nenhuma série ou coleção identificada. Experimente visualizar por pastas ou todos os arquivos.</div>';
    $('pages').innerHTML='';$('resultCount').textContent=dirs.reduce((n,f)=>n+f.count,0).toLocaleString('pt-BR');
    syncMulti();return;
   }
  }
  if(inFolders){
   if(!mediaSource && $('sourceFilter').value){mediaSource=$('sourceFilter').value;mediaFolder='';}
   const nav=await api('/api/media/folders?'+new URLSearchParams({category:requestedCat,source:mediaSource,folder:mediaFolder}));
   if(requestedCat!==currentCategory||mediaView!=='folders')return;
   renderMediaFolderNav(nav);
   folderPrefix=(nav.folders||[]).map(mediaFolderCard).join('');
   if(!mediaSource){
    $('items').innerHTML=folderPrefix||'<div class="empty-state">Nenhuma coleção de vídeos encontrada.</div>';
    $('pages').innerHTML='';$('resultCount').textContent=(nav.folders||[]).reduce((n,f)=>n+f.count,0).toLocaleString('pt-BR');
    syncMulti();return;
   }
   mediaFolder=nav.folder;
  }else if(isMediaCategory())renderMediaFolderNav({});
  const params=new URLSearchParams({category:requestedCat,page:String(requestedPage),q:requestedQuery,source:inFolders?mediaSource:$('sourceFilter').value,game_status:gameFilter,subcategory:requestedSub,extension:requestedExt});
  if(inFolders)params.set('folder',mediaFolder);
  if(inCollections&&mediaCollection)params.set('collection',mediaCollection);

  const res=await api('/api/items?'+params);
  if(currentCategory!==requestedCat||page!==requestedPage||$('query').value!==requestedQuery||subcategoryFilter!==requestedSub||extensionFilter!==requestedExt)return;
  itemsMap=Object.fromEntries(res.items.map(item=>[item.id,item]));
  $('resultCount').textContent=res.total.toLocaleString('pt-BR');
  $('items').innerHTML=folderPrefix+(res.items.length?res.items.map(renderCard).join(''):`<div class="empty-state">${ico('folder')}<strong>Nenhum item encontrado</strong><span>${(requestedQuery||requestedExt||requestedSub||$('sourceFilter').value)?'Verifique a busca, o formato ou o local. Use Limpar filtros para mostrar tudo.':'Nenhum arquivo nesta categoria. Confira Locais e a ultima atualizacao do catalogo.'}</span><button type="button" class="btn btn-primary ${isAdmin?'':'hidden'}" id="emptyAdd">${ico('plus')} Adicionar local</button></div>`);
  activateVideoPreviews();
  $('items').querySelectorAll('[data-select]').forEach(input=>input.addEventListener('change',()=>setMultiSelected(input.dataset.select,input.checked)));
  $('items').querySelectorAll('.media-card').forEach(card=>card.addEventListener('click',event=>{
   if(!multiMode||event.target.closest('button,label,input,a'))return;
   const box=card.querySelector('[data-select]');if(box)setMultiSelected(box.dataset.select,!box.checked);
  }));
  syncMulti();
  $('items').querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>openItem(b.dataset.open)));
  $('items').querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>editItem(b.dataset.edit)));
  $('items').querySelectorAll('[data-locate]').forEach(b=>b.addEventListener('click',()=>locateItem(b.dataset.locate)));
  syncMusicCardButtons();
  $('emptyAdd')?.addEventListener('click',openSource);
  const pages=Math.ceil(res.total/60);
  $('pages').innerHTML=pages>1?`<button type="button" class="btn btn-muted" id="prevPage" ${page<=1?'disabled':''}>Anterior</button><span>${page} de ${pages}</span><button type="button" class="btn btn-muted" id="nextPage" ${page>=pages?'disabled':''}>Próxima</button>`:'';
  $('prevPage')?.addEventListener('click',()=>{page--;loadItems();});$('nextPage')?.addEventListener('click',()=>{page++;loadItems();});
 }catch(error){$('items').innerHTML=`<div class="empty-state">${ico('alert')}<strong>Não foi possível carregar a biblioteca</strong><span>${escapeHTML(error.message)}</span></div>`;}
}
function renderCard(item){
 const catInfo=categories.find(x=>x[0]===item.category),glyph=catInfo?.[1]||'folder';
 const playable=['Filmes','Séries','Vídeos','Músicas','Imagens'].includes(item.category)&&item.kind==='file';
 const isVideo=item.kind==='file'&&/\.(mp4|webm|mkv|avi|mov|m4v|wmv|mpg|mpeg|ts)$/i.test(item.path);
 const isGame=item.category==='Jogos';
 const needsInstall=isGame&&item.game_status==='Para instalar';
 const primary=item.category==='Músicas'&&/\.(mp3|flac|wav|m4a|aac|ogg|wma|opus)$/i.test(item.path)?(currentTrack?.id===item.id?($('musicAudio')?.paused?'Continuar':'Pausar'):'Ouvir'):playable?'Reproduzir':isGame?(needsInstall?'Ver arquivos':item.launch_path?'Jogar':'Abrir'):'Abrir';
 const localArt=!item.cover?`<img class="local-poster" loading="lazy" alt="" src="/api/art/${encodeURIComponent(item.id)}" onerror="this.hidden=true">`:'';
 const thumb=isVideo&&!item.cover?`<img class="video-thumb" loading="lazy" alt="Miniatura do vídeo" src="/api/thumb/${encodeURIComponent(item.id)}" onerror="this.hidden=true">`:'';
 const preview=isVideo&&/\.(mp4|webm|m4v)$/i.test(item.path)?`<video class="hover-preview" aria-hidden="true" muted playsinline loop preload="none" data-preview="/api/stream/${encodeURIComponent(item.id)}"></video>`:'';
 const mediaMeta=item.metadata||{};
 const metaParts=[];
 if(item.category==='Séries'&&item.season!==null&&item.season!==undefined&&item.episode!==null&&item.episode!==undefined)metaParts.push(`T${String(item.season).padStart(2,'0')} · E${String(item.episode).padStart(2,'0')}`);
 if(mediaMeta.artist)metaParts.push(mediaMeta.artist);
 if(mediaMeta.genre)metaParts.push(mediaMeta.genre);
 if(item.media_year||mediaMeta.year)metaParts.push(String(item.media_year||mediaMeta.year));
 const extraMeta=metaParts.length?`<div class="media-metadata" title="${escapeHTML(metaParts.join(' · '))}">${escapeHTML(metaParts.join(' · '))}</div>`:'';
 const status=isGame&&item.game_status?`<span class="item-status ${needsInstall?'install':item.game_status==='Instalados'?'installed':'review'}">${escapeHTML(item.game_status)}</span>`:'';
 return `<article class="media-card ${multiSelected.has(item.id)?'selected':''}"><div class="poster"><label class="selection-box" title="Selecionar item"><input type="checkbox" data-select="${escapeHTML(item.id)}" aria-label="Selecionar ${escapeHTML(item.name)}" ${multiSelected.has(item.id)?'checked':''}></label>${ico(glyph)}${localArt}${thumb}${item.cover?`<img loading="lazy" alt="" src="${escapeHTML(item.cover)}" onerror="this.hidden=true">`:''}${preview}<span class="category-sticker">${escapeHTML(item.category)}</span>${item.available?'':'<span class="unavailable">Desconectado</span>'}</div><div class="media-details"><div>${status}<div class="media-title" title="${escapeHTML(item.name)}">${escapeHTML(item.name)}</div>${extraMeta}${item.kind==='file'?`<div class="file-format-label">${escapeHTML(formatLabel(item.extension||'[sem extensão]'))}</div>`:''}<div class="media-path" title="${escapeHTML(item.path)}">${escapeHTML(item.path)}</div></div><div class="media-actions">${(canLocate||playable)?`<button class="mini-action" type="button" data-open="${escapeHTML(item.id)}">${primary}</button>`:''}${canLocate?`<button class="mini-action mini-locate" type="button" data-locate="${escapeHTML(item.id)}" title="Abrir local do arquivo no Explorador" aria-label="Abrir local do arquivo ${escapeHTML(item.name)}">${ico('folder')}<span>Local</span></button>`:''}${item.kind==='file'?`<a class="mini-action mini-download" href="/api/download/${encodeURIComponent(item.id)}" download title="Baixar arquivo">${ico('drive')}<span>Baixar</span></a>`:''}${isAdmin?`<button class="mini-action" type="button" data-edit="${escapeHTML(item.id)}">Editar</button>`:''}</div></div></article>`;
}
function renderGameFilters(){
 $('gameFilters').querySelectorAll('[data-game-filter]').forEach(el=>el.classList.toggle('active',el.dataset.gameFilter===gameFilter));
}
function activateVideoPreviews(){
 // Sem FFmpeg: tenta gerar uma miniatura local no navegador para MP4/WebM compatíveis.
 $('items').querySelectorAll('img.video-thumb').forEach(img=>img.addEventListener('error',()=>{
  img.hidden=true;
  const card=img.closest('.media-card'),preview=card?.querySelector('video.hover-preview');
  if(!preview)return;
  const v=document.createElement('video');v.muted=true;v.preload='metadata';v.playsInline=true;v.crossOrigin='anonymous';
  const stop=()=>{v.removeAttribute('src');v.load();};
  const save=()=>{
   try{
    if(!v.videoWidth)return;
    const canvas=document.createElement('canvas');canvas.width=320;canvas.height=Math.max(1,Math.round(v.videoHeight*320/v.videoWidth));
    canvas.getContext('2d').drawImage(v,0,0,canvas.width,canvas.height);
    img.src=canvas.toDataURL('image/jpeg',.78);img.hidden=false;
   }catch(_){}finally{stop();}
  };
  v.addEventListener('loadedmetadata',()=>{
   try{v.currentTime=Math.min(2,Math.max(0,v.duration/2));}catch(_){stop();}
  },{once:true});
  v.addEventListener('seeked',save,{once:true});
  v.addEventListener('error',stop,{once:true});
  v.src=preview.dataset.preview;
 },{once:true}));
 $('items').querySelectorAll('.media-card').forEach(card=>{
  const video=card.querySelector('video.hover-preview');if(!video)return;
  card.addEventListener('mouseenter',()=>{
   if(!video.src)video.src=video.dataset.preview;
   video.play().then(()=>video.classList.add('playing')).catch(()=>{});
  });
  card.addEventListener('mouseleave',()=>{video.pause();video.classList.remove('playing');});
 });
}
function openPrivateDialog(configured){
 privateReady=configured;
 $('privateDialogTitle').textContent='Entrar como administrador';
 $('privateDialogDesc').textContent='Use sua senha de administrador. Para criar ou alterar a senha, execute Alterar Senha Admin.bat no PC servidor.';
 $('privateConfirmWrap').classList.add('hidden');
 $('privatePassword').value='';$('privateConfirm').value='';
 $('privateSave').textContent='Entrar';
 showDialog('privateDialog');$('privatePassword').focus();
}
async function handlePrivate(event){
 event.preventDefault();const pass=$('privatePassword').value;

 if(pass.length<8){await message('Senha curta','Escolha uma senha de pelo menos 8 caracteres.');return;}
 const b=$('privateSave');b.disabled=true;
 try{
  await api('/api/private/unlock','POST',{password:pass});
  privateReady=true;privateIsOpen=true;isAdmin=true;closeDialog('privateDialog');$('privatePassword').value='';$('privateConfirm').value='';
  toast('Administrador conectado.','success');refreshAdminUI();await changeCategory('Todos');await refresh();
 }catch(err){await message('Não foi possível desbloquear',err.message,{kind:'error'});}
 finally{b.disabled=false;}
}
async function handleProtected(event){
 event.preventDefault();
 const confirm=$('protectedConfirm');confirm.disabled=true;
 try{
  await api('/api/protected/unlock','POST',{password:$('protectedPassword').value});
  $('protectedPassword').value='';closeDialog('protectedDialog');privateIsOpen=true;
  await changeCategory('Protegidos',true);
  toast('Área Protegidos desbloqueada.','success');
 }catch(e){await message('Protegidos',e.message,{kind:'error'});}
 finally{confirm.disabled=false;}
}
async function lockPrivate(){
 try{await api('/api/private/lock','POST');resetMulti();if(musicQueuePrivate)stopMusic();privateIsOpen=false;itemsMap={};$('items').replaceChildren();await changeCategory('Todos');await refresh();toast('Área protegida bloqueada.','success');}
 catch(e){await message('Erro ao bloquear',e.message,{kind:'error'});}
}

function openSource(){if(!isAdmin)return;showDialog('sourceDialog');}
async function saveSource(event){
 event.preventDefault();const submit=$('sourceForm').querySelector('[type="submit"]');submit.disabled=true;
 try{
  await api('/api/sources','POST',{path:$('addPath').value.trim(),category:$('addCat').value,recursive:$('recursive').checked});
  closeDialog('sourceDialog');$('addPath').value='';toast('Local adicionado ao catálogo.','success');await refreshTypeFilters();await refresh();
  if(await message('Local cadastrado','Deseja iniciar o escaneamento agora?',{confirm:true,confirmLabel:'Escanear agora'}))await scan();
 }catch(error){await message('Não foi possível adicionar',error.message,{kind:'error'});}finally{submit.disabled=false;}
}
async function scan(){
 try{const result=await api('/api/scan','POST');if(!result.ok)toast('O escaneamento já está em andamento.');else toast('Escaneamento iniciado.','success');await refresh();}
 catch(error){await message('Erro ao escanear',error.message,{kind:'error'});}
}
async function removeSource(id){
 if(!await message('Remover local do catálogo?','Os registros deste local serão removidos da biblioteca. Os arquivos originais do computador NÃO serão apagados.',{confirm:true,confirmLabel:'Remover do catálogo'}))return;
 try{await api('/api/remove-source','POST',{id});toast('Local removido do catálogo.','success');await refreshTypeFilters();await refresh();loadItems();}
 catch(e){await message('Erro ao remover',e.message,{kind:'error'});}
}
function updateEditGameFields(){
 const it=itemsMap[editId], selected=$('editCategory').value;
 const isGame=(selected || it?.category)==='Jogos';
 $('gameStatusWrap').classList.toggle('hidden',!isGame);
 $('gameLaunchWrap').classList.toggle('hidden',!isGame);
 $('coverProvider').querySelector('option[value="steam"]').disabled=!isGame;
 if(!isGame&&$('coverProvider').value==='steam')$('coverProvider').value='commons';
}
function editItem(id){
 const item=itemsMap[id];if(!item)return;
 editId=id;$('editName').value=item.name;$('editCover').value=item.cover||'';
 $('editCategory').value=item.category_override||'';$('editTypeHint').textContent='Formato real: '+(item.kind==='folder'?'Pasta':formatLabel(item.extension||'[sem extensão]'))+'. Alterar a categoria não modifica o arquivo no Windows.';
 $('coverSearchOpen').classList.toggle('hidden',Boolean(item.hidden));
 $('editLaunch').value=item.launch_path||'';$('editGameStatus').value=item.game_status_override||'';updateEditGameFields();
 const meta=item.metadata||{};
 $('metadataSummary').textContent=meta.title?`Identificado: ${meta.title}${meta.year?' ('+meta.year+')':''}${meta.genre?' · '+meta.genre:''}${meta.artist?' · '+meta.artist:''}${meta.provider?' · '+meta.provider:''}`:'Sem informações externas. Você pode buscar e confirmar a identificação.';
 $('metadataEditor').classList.toggle('hidden',!['Jogos','Filmes','Séries','Músicas'].includes(item.category)||Boolean(item.hidden));
 $('editPath').textContent='Local original: '+item.path;showDialog('editDialog');
}
function openMetadataSearch(){
 const item=itemsMap[editId];if(!item||item.hidden)return;
 $('metadataQuery').value=item.series_title||item.name;
 $('metadataProvider').value='auto';$('metadataResults').innerHTML='<p class="modal-desc">Escolha uma fonte e clique em Pesquisar.</p>';
 showDialog('metadataDialog');
}
async function searchMetadata(){
 if(metadataSearchBusy)return;
 const item=itemsMap[editId];if(!item)return;
 metadataSearchBusy=true;$('metadataSearch').disabled=true;
 $('metadataResults').innerHTML='<p class="modal-desc">Consultando a base de dados…</p>';
 try{
  const res=await api('/api/metadata/search','POST',{id:item.id,provider:$('metadataProvider').value,query:$('metadataQuery').value.trim()});
  metadataResults=res.results||[];
  $('metadataResults').innerHTML=metadataResults.length?metadataResults.map((r,i)=>`<article class="metadata-result"><div class="metadata-result-cover">${r.cover?`<img loading="lazy" src="${escapeHTML(r.cover)}" alt="" onerror="this.hidden=true">`:ico('image')}</div><div class="metadata-result-body"><strong>${escapeHTML(r.title)}</strong><small>${escapeHTML([r.year,r.artist,r.genre,r.provider].filter(Boolean).join(' · '))}</small><p>${escapeHTML((r.overview||'').slice(0,230))}</p><small>Correspondência: ${Math.round((r.confidence||0)*100)}%</small></div><button type="button" class="btn btn-primary btn-small" data-pick-metadata="${i}">Usar</button></article>`).join(''):'<p class="modal-desc">Nenhum resultado. Confira o título, ou experimente outra fonte. '+escapeHTML((res.errors||[]).join(' · '))+'</p>';
  $('metadataResults').querySelectorAll('[data-pick-metadata]').forEach(b=>b.addEventListener('click',()=>applyMetadata(Number(b.dataset.pickMetadata))));
 }catch(e){$('metadataResults').textContent='Falha na pesquisa: '+e.message;}
 finally{metadataSearchBusy=false;$('metadataSearch').disabled=false;}
}
async function applyMetadata(index){
 const choice=metadataResults[index];const item=itemsMap[editId];if(!choice||!item)return;
 const replaceCover=Boolean(item.cover)?await message('Substituir capa existente?',`O item já tem capa. Deseja substituir pela capa de ${choice.provider}?`,{confirm:true,confirmLabel:'Substituir capa'}):true;
 try{
  await api('/api/metadata/apply','POST',{id:item.id,choice,replace_cover:replaceCover});
  closeDialog('metadataDialog');closeDialog('editDialog');toast('Informações aplicadas.','success');await loadItems();
 }catch(e){await message('Erro ao aplicar informações',e.message,{kind:'error'});}
}
async function startAutoMetadata(){
 if(!isAdmin)return;
 if(!await message('Identificar até 25 itens?', 'O Smart Library enviará os nomes de até 25 arquivos públicos sem capa para serviços externos (iTunes, Steam ou TMDb, se configurado). Arquivos protegidos não serão enviados. Resultados de baixa confiança serão ignorados. As capas já escolhidas serão preservadas.',{confirm:true,confirmLabel:'Iniciar identificação'}))return;
 try{
  await api('/api/metadata/auto','POST',{limit:25,category:['Jogos','Filmes','Séries','Músicas'].includes(currentCategory)?currentCategory:''});
  toast('Identificação iniciada em segundo plano.','success');metadataTaskActive=true;pollMetadata();
 }catch(e){await message('Identificação indisponível',e.message,{kind:'error'});}
}
async function pollMetadata(){
 if(!isAdmin)return;
 try{
  const s=(await api('/api/metadata/status')).task;
  $('metadataProgress').textContent=s.running?`${s.processed} analisados · ${s.updated} capas · em andamento`:(s.finished_at?`Concluído: ${s.updated} capas · ${s.skipped} revisões pendentes`:'');
  if(metadataTaskActive&&!s.running){metadataTaskActive=false;loadItems();}
 }catch(_){}
}
function openCoverSearch(){
 const item=selectedDiskItem();if(!item||item.hidden)return;
 $('coverQuery').value=item.name; $('coverProvider').value='commons';updateEditGameFields();
 $('coverResults').innerHTML='<p class="modal-desc">Pesquise para ver as capas disponíveis.</p>';
 showDialog('coverDialog');runCoverSearch();
}
async function runCoverSearch(){
 $('coverResults').innerHTML='<p class="modal-desc">Pesquisando imagens…</p>';
 try{
  const res=await api('/api/cover-search','POST',{id:editId,query:$('coverQuery').value,provider:$('coverProvider').value});
  $('coverResults').innerHTML=res.results.length?res.results.map((a,i)=>`<button class="cover-choice" data-cover-index="${i}" type="button"><img src="${escapeHTML(a.cover)}" alt="" loading="lazy" onerror="this.hidden=true"><span>${escapeHTML(a.name)}</span></button>`).join(''):'<p class="modal-desc">Nenhuma capa encontrada. Você pode continuar usando um link de imagem manualmente.</p>';
  $('coverResults').querySelectorAll('[data-cover-index]').forEach(b=>b.addEventListener('click',()=>{
    $('editCover').value=res.results[Number(b.dataset.coverIndex)].cover;
    closeDialog('coverDialog');toast('Capa selecionada. Clique em Salvar alterações.','success');
  }));
 }catch(e){$('coverResults').innerHTML=`<p class="modal-desc">${escapeHTML(e.message)}</p>`;}
}
function selectedDiskItem(){return itemsMap[editId];}
function openRename(){
 const item=selectedDiskItem();if(!item)return;
 $('diskNewName').value=item.path.replace(/^.*[\\/]/,'');
 showDialog('renameDialog');$('diskNewName').focus();
}
function openMove(){
 if(!selectedDiskItem())return;
 $('moveDestination').value='';showDialog('moveDialog');
}
function openTrash(){
 multiTrashOpen=false;
 const item=selectedDiskItem();if(!item)return;
 $('trashConfirmation').value='';
 $('trashDescription').textContent=`O item "${item.name}" será ${serviceMode?'movido para a Quarentena do Smart Library, podendo ser restaurado':'enviado para a Lixeira do Windows'}. Se for uma pasta, TODO o conteúdo será incluído.`;
 showDialog('trashDialog');
}
async function performDiskOp(action,args={}){
 const item=selectedDiskItem();if(!item)return;
 if(currentTrack?.id===item.id)stopMusic();
 const payload={id:item.id,expected_path:item.path,action,...args};
 const r=await api('/api/file-operation','POST',payload);
 for(const name of ['editDialog','renameDialog','moveDialog','trashDialog'])closeDialog(name);
 editId=null;
 toast(action==='trash'?(r.quarantined?'Enviado para Quarentena.':'Enviado para a Lixeira do Windows.'):action==='move'?'Item movido e catálogo atualizado.':'Item renomeado e catálogo atualizado.','success');
 await refreshTypeFilters();await refresh();await loadItems();return r;
}
async function handleRename(e){
 e.preventDefault();const name=$('diskNewName').value.trim();
 if(!name)return;
 try{await performDiskOp('rename',{name});}
 catch(e){await message('Não foi possível renomear',e.message,{kind:'error'});}
}
async function handleMove(e){
 e.preventDefault();const destination=$('moveDestination').value.trim();
 if(!destination)return;
 const item=selectedDiskItem();
 if(!await message('Confirmar movimentação',`Mover "${item.name}" para ${destination}? O arquivo original mudará de localização.`,{confirm:true,confirmLabel:'Mover agora'}))return;
 try{await performDiskOp('move',{destination});}
 catch(e){await message('Não foi possível mover',e.message,{kind:'error'});}
}
async function handleTrash(e){
 e.preventDefault();
 if($('trashConfirmation').value.trim()!=='EXCLUIR'){
  await message('Confirmação necessária','Digite EXCLUIR exatamente como solicitado.');return;
 }
 if(multiTrashOpen){await performMultiTrash();return;}
 try{await performDiskOp('trash');}
 catch(e){await message('Não foi possível enviar para a Lixeira',e.message,{kind:'error'});}
}
async function saveEdit(event){
 event.preventDefault();try{
  await api('/api/edit','POST',{id:editId,name:$('editName').value,cover:$('editCover').value,launch_path:($('editCategory').value||itemsMap[editId]?.category)==='Jogos'?$('editLaunch').value:'',game_status_override:($('editCategory').value||itemsMap[editId]?.category)==='Jogos'?$('editGameStatus').value:'',category_override:$('editCategory').value});
  closeDialog('editDialog');toast('Alterações salvas.','success');await refreshTypeFilters();await refresh();await loadItems();
 }catch(e){await message('Não foi possível salvar',e.message,{kind:'error'});}
}
async function action(id,mode){try{await api('/api/open','POST',{id,mode});}catch(error){await message('Não foi possível abrir',error.message,{kind:'error'});}}
async function locateItem(id){
 if(!canLocate)return;
 try{
  if(!serviceMode){await api('/api/open','POST',{id,mode:'locate'});return;}
  // O auxiliar usa apenas localhost e abre o Explorador na sessão do Windows.
  // Necessário ao executar o servidor como Serviço Windows.
  const helper='http://'+location.hostname+':38765/open';
  const response=await fetch(helper,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const info=await response.json();if(!response.ok)throw new Error(info.error||'Auxiliar local não disponível.');
 }catch(error){
  const item=itemsMap[id]||duplicateItemMap[id];
  await message('Abrir local', 'Para abrir no Explorador enquanto o Serviço Windows está ativo, execute "Abrir Smart Library.bat" no PC servidor. Esse atalho inicia o Auxiliar Local.\n\n'+error.message+(item?.path?'\n\nCaminho: '+item.path:''),{kind:'error'});
 }
}
function GenCopyPath(path){try{navigator.clipboard?.writeText(path).catch(()=>{});}catch(_){}}
async function openItem(id){
 const item=itemsMap[id];if(!item)return;
 if(!item.available){await message('Item indisponível','O arquivo ou disco não está conectado neste momento.');return;}
 if(item.category==='Músicas'&&item.kind==='file'){
  if(currentTrack?.id===id){const a=$('musicAudio');if(a.paused)await resumeMusic();else a.pause();return;}
  await playMusic(item);return;
 }
 if(['Filmes','Séries','Vídeos','Imagens'].includes(item.category)&&item.kind==='file'){
  // Vídeo e áudio tocando juntos prejudicam a experiência.
  $('musicAudio').pause();
  viewerItemId=id;
  const ext=item.path.split('.').pop().toLowerCase();let view;const src='/api/stream/'+encodeURIComponent(id);
  if(['mp4','webm','mov','m4v','mkv','avi','wmv','ts','mpeg','mpg'].includes(ext))view=`<video src="${src}" controls autoplay preload="metadata"></video>`;
  else if(['jpg','jpeg','png','gif','webp','bmp','tiff'].includes(ext))view=`<img src="${src}" alt="Imagem selecionada">`;
  else view=`<audio src="${src}" controls autoplay></audio>`;
  $('viewerTitle').textContent=item.name;$('viewerBody').innerHTML=view;showDialog('viewerDialog');return;
 }
 if(item.category==='Jogos'){
  if(item.game_status==='Para instalar'){await action(id,'folder');return;}
  if(item.launch_path){await action(id,'launch');return;}
  if(await message('Executável não configurado','Você ainda não selecionou o executável deste jogo. Deseja abrir a pasta onde ele está armazenado?',{confirm:true,confirmLabel:'Abrir pasta'}))await action(id,'folder');
  return;
 }
 await action(id,'folder');
}
function closeViewer(){closeDialog('viewerDialog');$('viewerBody').replaceChildren();viewerItemId=null;}

// O áudio fica fixo na página, fora da grade e dos modais.
function humanBytes(n){
 const units=['B','KB','MB','GB','TB'];let i=0;let x=Math.max(0,Number(n)||0);
 while(x>=1024&&i<4){x/=1024;i++;}
 return x.toLocaleString('pt-BR',{maximumFractionDigits:i?1:0})+' '+units[i];
}
async function startDuplicates(){
 if(!isAdmin)return;
 try{await api('/api/duplicates/scan','POST');toast('Análise iniciada. Você pode navegar pelo sistema enquanto ela acontece.','success');await refreshDuplicates();}
 catch(e){await message('Não foi possível analisar',e.message,{kind:'error'});}
}
async function stopDuplicates(){
 try{await api('/api/duplicates/cancel','POST');toast('A análise será interrompida após o bloco atual.');}
 catch(e){toast(e.message,'error');}
}
async function refreshDuplicates(){
 if(currentCategory!=='Duplicados')return;
 try{
  const d=await api('/api/duplicates');duplicateResults=d;duplicateItemMap={};
  $('duplicatesStart').disabled=d.running;
  $('duplicatesStop').classList.toggle('hidden',!d.running);
  const progress=d.running?`${d.phase} · ${d.checked} de ${d.candidates} candidatos · ${humanBytes(d.bytes_read)} lidos`:
    d.error?'Erro: '+d.error:d.finished?`${d.phase} · Finalizado em ${d.finished}`:'Execute uma análise quando desejar.';
  $('duplicatesProgress').textContent=progress;
  $('duplicatesSummary').innerHTML=`<div class="dup-stat"><span>Arquivos avaliados</span><strong>${Number(d.files||0).toLocaleString('pt-BR')}</strong></div><div class="dup-stat"><span>Grupos idênticos</span><strong>${d.exact_groups||0}</strong></div><div class="dup-stat"><span>Possível economia</span><strong>${humanBytes(d.estimated_savings)}</strong></div><div class="dup-stat"><span>Nomes semelhantes</span><strong>${d.similar_groups||0}</strong></div>`;
  const renderSection=(groups,title,desc,confirmed)=>{
   if(!groups?.length)return `<div class="dup-empty">${confirmed?'Nenhuma cópia idêntica encontrada até agora.':'Nenhum nome semelhante encontrado até agora.'}</div>`;
   return groups.map((g,i)=>`<article class="dup-group"><div class="dup-group-header"><strong>${confirmed?'SHA-256 confirmado':'Possíveis versões/cópias'} · ${g.files.length} arquivos</strong><span>${confirmed?'Economia potencial: '+humanBytes(g.size*(g.files.length-1)):'Conferir antes de excluir'}</span></div>${g.files.map(f=>{
     duplicateItemMap[f.id]=f;
     return `<div class="dup-entry"><div class="dup-file"><strong title="${escapeHTML(f.name)}">${escapeHTML(f.name)}</strong><span title="${escapeHTML(f.path)}">${escapeHTML(f.path)}</span></div><small>${humanBytes(f.size)}</small><button class="btn btn-muted btn-small" type="button" data-dup-locate="${escapeHTML(f.id)}">Local</button><button class="btn btn-muted btn-small" type="button" data-dup-select="${escapeHTML(f.id)}">Selecionar</button></div>`;
    }).join('')}</article>`).join('');
  };
  $('duplicatesList').innerHTML=`<h3>Arquivos idênticos <span class="dup-tag">Confirmados por hash</span></h3>${renderSection(d.exact,'', '',true)}<h3>Nomes semelhantes <span class="dup-tag">Revisão manual</span></h3>${renderSection(d.similar,'','',false)}${d.truncated?'<p class="duplicates-hint">Exibindo até 150 grupos de cada tipo. Refine a organização da biblioteca para revisão adicional.</p>':''}`;
  $('duplicatesList').querySelectorAll('[data-dup-locate]').forEach(b=>b.addEventListener('click',()=>locateItem(b.dataset.dupLocate)));
  $('duplicatesList').querySelectorAll('[data-dup-select]').forEach(b=>b.addEventListener('click',async()=>{
    const item=duplicateItemMap[b.dataset.dupSelect];if(!item)return;
    await changeCategory('Todos');multiMode=true;
    if(multiSelected.size>=100){toast('Limite de 100 itens por operação.','error');return;}
    multiSelected.set(item.id,{id:item.id,expected_path:item.path,name:item.name,hidden:0});
    syncMulti();toast('Arquivo selecionado. Revise a seleção antes de enviar à Lixeira.','success');
  }));
 }catch(e){$('duplicatesProgress').textContent=e.message;}
}
function musicClock(seconds){if(!Number.isFinite(seconds)||seconds<0)return '0:00';const t=Math.floor(seconds);return `${Math.floor(t/60)}:${String(t%60).padStart(2,'0')}`;}
function syncMusicCardButtons(){
 document.querySelectorAll('#items [data-open]').forEach(btn=>{
  const item=itemsMap[btn.dataset.open];if(item?.category!=='Músicas')return;
  btn.textContent=currentTrack?.id===item.id?($('musicAudio').paused?'Continuar':'Pausar'):'Ouvir';
  btn.closest('.media-card')?.classList.toggle('music-active',currentTrack?.id===item.id);
 });
}
function updateMusicUI(){
 const a=$('musicAudio');if(!a)return;
 $('musicDock').classList.toggle('hidden',!currentTrack);
 $('musicDock').classList.toggle('minimized',musicMinimized);
 $('musicMinimize').textContent=musicMinimized?'▢':'−';
 $('musicMinimize').title=musicMinimized?'Expandir player':'Minimizar player';
 $('musicMinimize').setAttribute('aria-label',musicMinimized?'Expandir player':'Minimizar player');
 $('musicMiniToggle').textContent=currentTrack&&!a.paused?'Ⅱ':'▶';
 $('musicMiniToggle').setAttribute('aria-label',currentTrack&&!a.paused?'Pausar':'Reproduzir');
 document.body.classList.toggle('has-music',Boolean(currentTrack));
 document.body.classList.toggle('music-minimized',Boolean(currentTrack&&musicMinimized));
 const isPlaying=Boolean(currentTrack&&!a.paused);
 $('musicToggle').innerHTML=ico(isPlaying?'pause':'play');
 $('musicToggle').setAttribute('aria-label',isPlaying?'Pausar':'Reproduzir');
 $('musicCaption').textContent=isPlaying?'REPRODUZINDO AGORA':'REPRODUÇÃO PAUSADA';
 const duration=Number.isFinite(a.duration)?a.duration:0;
 $('musicCurrent').textContent=musicClock(a.currentTime);
 $('musicDuration').textContent=musicClock(duration);
 $('musicSeek').disabled=!duration;
 $('musicSeek').value=duration?Math.round((a.currentTime/duration)*1000):0;
 $('musicVolume').value=Math.round(a.volume*100);
 $('musicMute').innerHTML=ico(a.muted||a.volume===0?'muted':'volume');
 $('musicMute').setAttribute('aria-label',a.muted?'Ativar som':'Silenciar');
 $('musicPrev').disabled=musicQueue.length<2;
 $('musicNext').disabled=musicQueue.length<2;
 syncMusicCardButtons();
}
async function buildMusicQueue(item){
 try{
  const source=$('sourceFilter').value;
  const data=await api('/api/music/queue?'+new URLSearchParams({item_id:item.id,source}));
  if(currentTrack?.id!==item.id)return;
  musicQueue=data.items||[];
  musicQueueIndex=musicQueue.findIndex(t=>t.id===item.id);
  musicQueuePrivate=Boolean(data.private);
 }catch(e){
  if(currentTrack?.id!==item.id)return;
  musicQueue=[{id:item.id,name:item.name,available:item.available}];musicQueueIndex=0;
  musicQueuePrivate=Boolean(item.hidden);
  toast('Não foi possível carregar a fila. A música selecionada ainda pode ser reproduzida.','info');
 }
 if(musicQueueIndex<0){musicQueue=[{id:item.id,name:item.name,available:item.available},...musicQueue];musicQueueIndex=0;}
}
async function playMusic(item,{reuseQueue=false}={}){
 if(!item.available){toast('O disco que contém essa música está desconectado.','error');return;}
 if(!reuseQueue){
  musicQueue=[{id:item.id,name:item.name,available:item.available}];
  musicQueueIndex=0;musicQueuePrivate=Boolean(item.hidden);
 }
 const audio=$('musicAudio');audio.pause();
 currentTrack={id:item.id,name:item.name,path:item.path||'',hidden:!!item.hidden};
 $('musicTitle').textContent=item.name;$('musicTitle').title=item.name;
 $('musicSubtitle').textContent=item.path||'Música da biblioteca';
 $('musicArtwork').innerHTML=ico('music');
 const img=new Image();img.onload=()=>{if(currentTrack?.id===item.id){$('musicArtwork').replaceChildren(img);}};
 img.src='/api/art/'+encodeURIComponent(item.id);
 audio.src='/api/stream/'+encodeURIComponent(item.id);
 audio.load();updateMusicUI();
 // Inicia áudio ainda no clique: a fila carrega em paralelo para não bloquear autoplay.
 const playback=resumeMusic();
 if(!reuseQueue)queueReady=buildMusicQueue(item).then(updateMusicUI);
 await playback;
}
async function resumeMusic(){
 const a=$('musicAudio');if(!currentTrack)return;
 try{await a.play();}catch(error){
  if(error?.name==='AbortError')return;
  toast('Este áudio não pôde ser reproduzido. Verifique o formato do arquivo.','error');
 }
 updateMusicUI();
}
async function stepMusic(step,{automatic=false}={}){
 if(!musicQueue.length)return;
 if(automatic&&musicQueueIndex>=musicQueue.length-1){updateMusicUI();return;}
 if(musicQueue.length<2){updateMusicUI();return;}
 let index=musicQueueIndex;
 // Pula discos ausentes, preservando a ordem da biblioteca.
 for(let i=0;i<musicQueue.length;i++){
  index=(index+step+musicQueue.length)%musicQueue.length;
  if(automatic&&index<=musicQueueIndex){updateMusicUI();return;}
  const song=musicQueue[index];if(!song.available)continue;
  musicQueueIndex=index;
  await playMusic({...song,path:song.path||'',hidden:musicQueuePrivate},{reuseQueue:true});return;
 }
 toast('Não há outras músicas disponíveis na fila.');
}
function stopMusic(){
 const a=$('musicAudio');a.pause();a.removeAttribute('src');a.load();
 currentTrack=null;musicQueue=[];musicQueueIndex=-1;musicQueuePrivate=false;musicMinimized=false;
 $('musicArtwork').innerHTML=ico('music');updateMusicUI();
}
function setupMusic(){
 const a=$('musicAudio');
 let volume=.75;try{const saved=Number(localStorage.getItem('smart-library-volume'));if(Number.isFinite(saved)&&saved>=0&&saved<=1)volume=saved;}catch(_){}
 a.volume=volume;
 ['play','pause','timeupdate','durationchange','loadedmetadata','volumechange'].forEach(name=>a.addEventListener(name,updateMusicUI));
 a.addEventListener('ended',async()=>{await queueReady;if(currentTrack)await stepMusic(1,{automatic:true});});
 a.addEventListener('error',()=>{if(currentTrack)toast('Não foi possível reproduzir esta música. Formato não suportado ou arquivo indisponível.','error');updateMusicUI();});
 $('musicToggle').addEventListener('click',()=>a.paused?resumeMusic():a.pause());
 $('musicPrev').addEventListener('click',()=>{if(a.currentTime>3){a.currentTime=0;}else stepMusic(-1);});
 $('musicNext').addEventListener('click',()=>stepMusic(1));
 $('musicClose').addEventListener('click',stopMusic);
 $('musicMinimize').addEventListener('click',()=>{musicMinimized=!musicMinimized;updateMusicUI();});
 $('musicMiniToggle').addEventListener('click',()=>a.paused?resumeMusic():a.pause());
 $('musicLocate').addEventListener('click',()=>{if(currentTrack)locateItem(currentTrack.id);});
 $('musicSeek').addEventListener('input',e=>{if(Number.isFinite(a.duration)&&a.duration>0)a.currentTime=a.duration*Number(e.target.value)/1000;});
 $('musicVolume').addEventListener('input',e=>{a.volume=Number(e.target.value)/100;a.muted=false;try{localStorage.setItem('smart-library-volume',String(a.volume));}catch(_){}});
 $('musicMute').addEventListener('click',()=>{a.muted=!a.muted;updateMusicUI();});
 updateMusicUI();
}
// Esc fecha o modal superior; clique no fundo escuro fecha o modal,
// mas o mini-player nao é um modal e permanece tocando.
function setupModalDismiss(){
 document.querySelectorAll('dialog.modal').forEach(dialog=>{
  dialog.addEventListener('click',event=>{
   if(event.target!==dialog)return;
   const r=dialog.getBoundingClientRect();
   if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();
  });
 });
 document.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  const open=[...document.querySelectorAll('dialog.modal[open]')];
  if(!open.length)return;
  event.preventDefault();
  const top=open[open.length-1];top.close();
 });
}

function changeTheme(){
 const allowed=['hydra','purple','midnight','graphite','light'];
 const theme=allowed.includes($('themeSelect').value)?$('themeSelect').value:'hydra';
 document.body.dataset.theme=theme;
 try{localStorage.setItem('smart-library-theme',theme);}catch(_){}
}
async function browseStart(target,mode){
 browseTarget=target;browseMode=mode;selectedExecutable=null;
 $('browseTitle').textContent=mode==='folder'?'Selecionar pasta ou disco':'Selecionar executável';
 $('browseDescription').textContent=mode==='folder'?(target==='uploadDestination'?'Escolha o disco e a pasta do computador para receber os arquivos. O Admin pode navegar por K:, outras unidades e subpastas.':'Escolha um disco inteiro ou navegue até a pasta que deseja catalogar.'):'Navegue até a pasta do jogo e selecione o executável (.exe, .bat, .cmd ou .lnk).';
 $('browseChoose').innerHTML=ico('check')+(mode==='folder'?' Selecionar pasta':' Selecionar arquivo');
 $('browseSearch').value='';showDialog('browseDialog');
 let initial='';
 if($(target).value.trim()){
  const p=$(target).value.trim();
  if(mode==='executable'){
   // Se o campo contém um executável, abre primeiro o disco para evitar caminhos inválidos.
   const pos=Math.max(p.lastIndexOf('\\'),p.lastIndexOf('/'));initial=pos>=0?p.slice(0,pos+1):'';
  }else initial=p;
 }
 try{await browseNavigate(initial);}catch(_){await browseNavigate('');}
}
async function browseNavigate(path){
 const seq=++browseRequest;
 $('browseList').innerHTML='<div class="browser-empty">Carregando pastas...</div>';
 const params=new URLSearchParams({path,mode:browseMode});
 try{
  const result=await api('/api/fs/list?'+params);
  if(seq!==browseRequest)return;
  browseData=result;selectedExecutable=null;$('browseSearch').value='';renderBrowser();
 }catch(error){
  if(seq!==browseRequest)return;
  $('browseList').innerHTML=`<div class="browser-empty">${escapeHTML(error.message)}</div>`;
  $('browseChoose').disabled=true;
  toast(error.message,'error');throw error;
 }
}
function renderBrowser(){
 if(!browseData)return;
 $('browseAddress').textContent=browseData.path||'Este computador';
 $('browseBack').disabled=browseData.parent===null;
 $('browseSelected').textContent=selectedExecutable||browseData.path||'Selecione uma unidade ou pasta';
 $('browseChoose').disabled=browseMode==='folder'?!browseData.path:!selectedExecutable;
 const search=$('browseSearch').value.trim().toLocaleLowerCase('pt-BR');
 const rows=[...browseData.folders.map((x,i)=>({...x,listIndex:i,isFile:false})),...browseData.files.map((x,i)=>({...x,listIndex:i,isFile:true}))].filter(x=>x.name.toLocaleLowerCase('pt-BR').includes(search));
 $('browseList').innerHTML=rows.length?rows.map(x=>`<button type="button" class="browser-row ${selectedExecutable===x.path?'selected':''}" data-${x.isFile?'file':'dir'}="${x.listIndex}" title="${escapeHTML(x.path)}">${ico(x.kind==='drive'?'drive':x.isFile?'package':'folder')}<span>${escapeHTML(x.name)}</span>${x.isFile?'':ico('chevron')}</button>`).join(''):'<div class="browser-empty">Nenhuma pasta ou arquivo encontrado aqui.</div>';
 $('browseList').querySelectorAll('[data-dir]').forEach(el=>el.addEventListener('click',()=>browseNavigate(browseData.folders[Number(el.dataset.dir)].path).catch(()=>{})));
 $('browseList').querySelectorAll('[data-file]').forEach(el=>el.addEventListener('click',()=>{
  selectedExecutable=browseData.files[Number(el.dataset.file)].path;renderBrowser();
 }));
}
function chooseBrowse(){
 if(!browseData)return;
 const selected=browseMode==='folder'?browseData.path:selectedExecutable;
 if(!selected)return;
 $(browseTarget).value=selected;closeDialog('browseDialog');toast(browseMode==='folder'?'Pasta selecionada.':'Executável selecionado.','success');
}


let uploadAbort=null;
function resetUploadUI(){
 $('uploadInfo').textContent='Selecione arquivos e escolha uma pasta de destino no computador.';
 $('uploadProgress').value=0;
}
function sendOneFile(file,destination,position,total){
 return new Promise((resolve,reject)=>{
  const xhr=new XMLHttpRequest();uploadAbort=xhr;
  xhr.open('POST','/api/upload?'+new URLSearchParams({destination}));
  xhr.setRequestHeader('Content-Type','application/octet-stream');
  xhr.setRequestHeader('X-File-Name',encodeURIComponent(file.name));
  xhr.upload.onprogress=e=>{
   $('uploadInfo').textContent=`Enviando ${position}/${total}: ${file.name} — ${e.lengthComputable?Math.round(e.loaded/e.total*100)+'%':''}`;
   if(e.lengthComputable)$('uploadProgress').value=e.loaded/e.total*100;
  };
  xhr.onload=()=>{
   let v={};try{v=JSON.parse(xhr.responseText);}catch(_){}
   xhr.status>=200&&xhr.status<300?resolve(v):reject(new Error(v.error||'Falha ao enviar arquivo.'));
  };
  xhr.onerror=()=>reject(new Error('Conexão perdida durante o envio.'));
  xhr.onabort=()=>reject(new Error('Envio cancelado.'));
  xhr.send(file);
 });
}
async function uploadFiles(event){
 event.preventDefault();if(!isAdmin)return;
 const files=[...$('uploadFiles').files],destination=$('uploadDestination').value.trim();
 if(!files.length||!destination){toast('Selecione os arquivos e a pasta de destino.','error');return;}
 if(files.some(f=>f.size<=0||f.size>2*1024*1024*1024)){await message('Limite por arquivo','Cada arquivo deve ter até 2 GB e não pode estar vazio.',{kind:'error'});return;}
 if(!await message('Confirmar envio',`Enviar ${files.length} arquivo(s) para:
${destination}

Arquivos existentes com o mesmo nome não serão substituídos.`,{confirm:true,confirmLabel:'Enviar'}))return;
 $('uploadStart').disabled=true;$('uploadCancel').disabled=false;
 let done=0;
 try{
  for(const file of files){await sendOneFile(file,destination,done+1,files.length);done++;}
  $('uploadInfo').textContent=done+' arquivo(s) enviados para '+destination;
  $('uploadProgress').value=100;
  $('uploadFiles').value='';toast('Transferência concluída!','success');
 }catch(e){await message('Transferência interrompida',`${done} de ${files.length} concluído(s). ${e.message}`,{kind:'error'});}
 finally{uploadAbort=null;$('uploadStart').disabled=false;$('uploadCancel').disabled=true;}
}
function refreshAdminUI(){
 $('intelligenceTools').classList.toggle('hidden',!isAdmin);
 $('backupNow')?.classList.toggle('hidden',!isAdmin);
 $('adminAccess').textContent=isAdmin?'Sair do Admin':'Entrar como Admin';
 ['addButton','scanButton','addSourceSecondary','duplicatesStart'].forEach(id=>{const x=$(id);if(x)x.classList.toggle('hidden',!isAdmin);});
 $('toggleMulti').classList.toggle('hidden',!isAdmin);
 $('ignoreSteamMedia').disabled=!isAdmin;
 if(!isAdmin&&multiMode)resetMulti();
 syncMulti();
}

function setup(){
 $('uploadForm').addEventListener('submit',uploadFiles);$('browseUpload').addEventListener('click',()=>browseStart('uploadDestination','folder'));$('uploadCancel').addEventListener('click',()=>uploadAbort?.abort());
 $('adminAccess').addEventListener('click',async()=>{if(isAdmin)await lockPrivate();else openPrivateDialog(true);});
 try{let theme=localStorage.getItem('smart-library-theme')||'hydra';if(theme==='dark')theme='hydra';if([...$('themeSelect').options].some(x=>x.value===theme)){$('themeSelect').value=theme;document.body.dataset.theme=theme;}}catch(_){}
 renderNav();
 refreshAdminUI();api('/api/private/status').then(st=>{isAdmin=Boolean(st.unlocked);privateReady=Boolean(st.configured);refreshAdminUI();renderNav();}).catch(()=>{});
 $('addButton').addEventListener('click',openSource);$('addSourceSecondary').addEventListener('click',openSource);
 $('toggleMulti').addEventListener('click',()=>{multiMode=!multiMode;if(!multiMode)multiSelected.clear();syncMulti();});
 $('multiSelectPage').addEventListener('click',selectMultiPage);
 $('multiClear').addEventListener('click',()=>{multiSelected.clear();syncMulti();});
 $('multiTrash').addEventListener('click',openMultiTrash);
 $('trashDialog').addEventListener('close',()=>{multiTrashOpen=false;});
 $('duplicatesStart').addEventListener('click',startDuplicates);
 $('duplicatesStop').addEventListener('click',stopDuplicates);
 $('scanButton').addEventListener('click',scan);$('sourceForm').addEventListener('submit',saveSource);$('editForm').addEventListener('submit',saveEdit);
 $('backupNow')?.addEventListener('click',async()=>{
  if(!isAdmin){toast('Somente o administrador pode criar backups.','error');return;}
  const button=$('backupNow');button.disabled=true;
  try{const result=await api('/api/backup','POST');toast('Backup criado: '+result.created,'success');await refresh();}
  catch(error){await message('Falha no backup',error.message,{kind:'error'});}
  finally{button.disabled=false;}
 });
 $('ignoreSteamMedia').addEventListener('change',async event=>{
  const checkbox=event.currentTarget;
  if(!isAdmin){checkbox.checked=!checkbox.checked;return;}
  checkbox.disabled=true;
  try{
   const result=await api('/api/media-filters','POST',{ocultar_midias_steam:checkbox.checked});
   toast('Filtro atualizado: '+Number(result.updated||0)+' registro(s) reavaliados.','success');
   page=1;await refreshTypeFilters();await refresh();await loadItems();
  }catch(error){checkbox.checked=!checkbox.checked;await message('Não foi possível atualizar o filtro',error.message,{kind:'error'});}
  finally{checkbox.disabled=!isAdmin;}
 });
 $('themeSelect').addEventListener('change',changeTheme);
 $('privateForm').addEventListener('submit',handlePrivate);$('protectedForm').addEventListener('submit',handleProtected);$('editCategory').addEventListener('change',updateEditGameFields);$('privateLock').addEventListener('click',lockPrivate);
 $('gameFilters').querySelectorAll('[data-game-filter]').forEach(btn=>btn.addEventListener('click',()=>{gameFilter=btn.dataset.gameFilter;page=1;renderGameFilters();loadItems();}));
 $('closeViewer').addEventListener('click',closeViewer);
 $('viewerLocate').addEventListener('click',()=>{if(viewerItemId)locateItem(viewerItemId);});
 $('viewerLocate').classList.toggle('hidden',!canLocate);$('editLocate').classList.toggle('hidden',!canLocate);$('musicLocate').classList.toggle('hidden',!canLocate);
 $('editLocate').addEventListener('click',()=>{if(editId)locateItem(editId);});
 setupMusic();setupModalDismiss();
 $('viewerDialog').addEventListener('close',()=>{$('viewerBody').replaceChildren();viewerItemId=null;});
 document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>closeDialog(button.dataset.close)));
 $('query').addEventListener('input',()=>{clearTimeout(searchTimeout);searchTimeout=setTimeout(()=>{page=1;loadItems();},230);});
 $('sourceFilter').addEventListener('change',()=>{page=1;mediaFolder='';mediaSource=$('sourceFilter').value;if(isMediaCategory())mediaView='all';loadItems();});
 $('categoryFilter').addEventListener('change',()=>{subcategoryFilter=$('categoryFilter').value;extensionFilter='';page=1;refreshTypeFilters();loadItems();});
 $('extensionFilter').addEventListener('change',()=>{extensionFilter=$('extensionFilter').value;$('filterHint').textContent=extensionFilter?formatLabel(extensionFilter):'Formatos reais detectados nos arquivos';page=1;loadItems();});
 $('clearTypeFilters').addEventListener('click',async()=>{
  clearTimeout(searchTimeout);
  $('query').value='';$('sourceFilter').value='';subcategoryFilter='';extensionFilter='';gameFilter='';
  mediaSource='';mediaFolder='';if(isMediaCategory())mediaView='all';
  page=1;renderGameFilters();
  await refreshTypeFilters();await loadItems();
  toast('Todos os filtros foram limpos.','success');
 });
 $('gridView').addEventListener('click',()=>{viewMode='grid';$('items').classList.remove('list-mode');$('gridView').classList.add('active');$('listView').classList.remove('active');});
 $('listView').addEventListener('click',()=>{viewMode='list';$('items').classList.add('list-mode');$('listView').classList.add('active');$('gridView').classList.remove('active');});
 $('metadataOpen').addEventListener('click',openMetadataSearch);
 $('metadataSearch').addEventListener('click',searchMetadata);
 $('metadataQuery').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchMetadata();}});
 $('autoMetadataButton').addEventListener('click',startAutoMetadata);
 $('coverSearchOpen').addEventListener('click',openCoverSearch);
 $('coverSearchRun').addEventListener('click',runCoverSearch);$('coverExternalSearch').addEventListener('click',()=>{const q=$('coverQuery').value.trim();if(q)window.open('https://www.google.com/search?tbm=isch&q='+encodeURIComponent(q),'_blank','noopener,noreferrer');});
 $('coverQuery').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();runCoverSearch();}});
 $('renameDisk').addEventListener('click',openRename);
 $('moveDisk').addEventListener('click',openMove);
 $('trashDisk').addEventListener('click',openTrash);
 $('mediaFolderBar').addEventListener('click',e=>{const b=e.target.closest('[data-media-view],[data-media-reset],[data-media-go]');if(!b)return;
 if(b.dataset.mediaView){mediaView=b.dataset.mediaView;mediaCollection='';mediaFolder='';page=1;loadItems();return;}
 if(b.hasAttribute('data-media-reset')){if(mediaView==='collections')openMediaCollection('');else openMediaDirectory('','');}
 else if(b.hasAttribute('data-media-go'))openMediaDirectory(mediaSource,b.dataset.mediaGo);
 });
 $('items').addEventListener('click',e=>{const c=e.target.closest('[data-media-collection]');if(c){openMediaCollection(c.dataset.mediaCollection);return;}
 const b=e.target.closest('[data-media-folder]');if(b){openMediaDirectory(b.dataset.mediaSource,b.dataset.mediaFolder);}});
 $('renameForm').addEventListener('submit',handleRename);
 $('moveForm').addEventListener('submit',handleMove);
 $('trashForm').addEventListener('submit',handleTrash);
 $('browseMove').addEventListener('click',()=>browseStart('moveDestination','folder'));
 $('browseSource').addEventListener('click',()=>browseStart('addPath','folder'));
 $('browseExecutable').addEventListener('click',()=>browseStart('editLaunch','executable'));
 $('browseBack').addEventListener('click',()=>browseNavigate(browseData?.parent||'').catch(()=>{}));
 $('browseHome').addEventListener('click',()=>browseNavigate('').catch(()=>{}));
 $('browseSearch').addEventListener('input',renderBrowser);
 $('browseChoose').addEventListener('click',chooseBrowse);
 refreshTypeFilters();refresh();loadItems();setInterval(refresh,3000);setInterval(()=>{if(isAdmin)pollMetadata();},5000);
}
setup();
