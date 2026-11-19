'use strict';
const REPO='https://github.com/prazeres-interrompidos/top-apple-podcasts-prazeres-interrompidos';
const RAW='https://raw.githubusercontent.com/prazeres-interrompidos/top-apple-podcasts-prazeres-interrompidos/main/';
const CAT={'1482':'Livros','1301':'Arte','26':'Top Geral de Programas'};
const LABEL={'apple_ids':'Apple · lista de IDs','apple_rss':'Apple · RSS','historical':'Registo fornecido'};
const flag=c=>/^[a-z]{2}$/i.test(c||'')?String.fromCodePoint(...c.toUpperCase().split('').map(v=>127397+v.charCodeAt(0))):'🌐';
function appleUrl(url){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname.endsWith('.apple.com');}catch{return false;}}
function allowedRecord(r){if(r.url&&!appleUrl(r.url))return false;return ['apple_ids','apple_rss'].includes(r.source)||/^(apple|arquivo)/i.test(r.source_name||'');}
const sourceLabel=r=>r.source==='historical'?(/^Apple/i.test(r.source_name||'')?'Apple Podcasts · histórico':'Registo fornecido'):LABEL[r.source];
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=u=>typeof u==='string'&&/^https:\/\//.test(u)?u:'#';
const displayNames=new Intl.DisplayNames(['pt-PT'],{type:'region'});
const country=c=>{try{return displayNames.of((c||'').toUpperCase())||c;}catch{return c||'Por confirmar';}};
const day=s=>s?new Intl.DateTimeFormat('pt-PT',{day:'2-digit',month:'short',year:'numeric',timeZone:'Europe/Lisbon'}).format(new Date(s.length===10?s+'T12:00:00Z':s)):'Data não indicada';
const stamp=s=>s?new Intl.DateTimeFormat('pt-PT',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Lisbon'}).format(new Date(s)):'Hora não indicada';
let state={history:[],queries:[],peaks:[],latest:{},runs:[],countries:[],page:0};
const dateval=r=>r.observed_at_utc||r.date||'';
function badge(r){if(r.divergent)return '<span class="tag divergent">Divergência documentada</span>';if(r.quality==='campos_por_confirmar')return '<span class="tag unknown">Campos por confirmar</span>';if(r.source==='historical')return '<span class="tag documented">'+'Registo histórico'+'</span>';return '<span class="tag">Comprovado na lista</span>';}
async function load(){
 $('refresh').disabled=true;$('sync-status').textContent='A consultar o arquivo…';
 let fallback=false;
 const names=['latest','history','countries','historical-consultations','runs','peaks'];
 let data;
 try{
  data=await Promise.all(names.map(async n=>{const r=await fetch(RAW+'public/'+n+'.json?t='+Math.floor(Date.now()/60000),{cache:'no-store'});if(!r.ok)throw new Error('Arquivo remoto indisponível');return r.json();}));
 }catch{
  fallback=true;
  try{data=await Promise.all(names.map(async n=>{const r=await fetch('snapshot/'+n+'.json');if(!r.ok)throw new Error('Sem cópia local');return r.json();}));}
  catch{$('sync-status').textContent='Não foi possível carregar os dados';$('notice').hidden=false;$('notice').textContent='O arquivo não respondeu. Tenta atualizar os dados dentro de alguns minutos.';$('refresh').disabled=false;return;}
 }
 [state.latest,state.history,state.countries,state.queries,state.runs,state.peaks]=data;
 state.history=state.history.filter(allowedRecord);state.queries=state.queries.filter(allowedRecord);
 const selected=$('country').value;
 $('country').innerHTML='<option value="">Todos os mercados</option>'+[...state.countries].sort((a,b)=>country(a.code).localeCompare(country(b.code),'pt')).map(c=>'<option value="'+esc(c.code)+'">'+esc(country(c.code))+'</option>').join('');
 $('country').value=state.countries.some(c=>c.code===selected)||selected===''?selected:'pt';
 const run=state.latest.run;
 $('sync-status').textContent=fallback?'Cópia guardada · ligação remota indisponível':'Ligado ao arquivo no GitHub';
 const age=run?.finished_at_utc?(Date.now()-Date.parse(run.finished_at_utc))/3600000:Infinity;
 let notice='';
 if(fallback)notice='Estás a consultar a cópia guardada com esta publicação. Não foi possível obter a versão atual do GitHub. As datas abaixo são as datas reais dos registos guardados.';
 else if(!run)notice='O arquivo histórico está disponível. A primeira ronda automática ainda não foi registada.';
 else if(run.status==='running')notice='A recolha está em curso. Alguns mercados podem ainda estar por consultar.';
 else if(age>48)notice='A última ronda terminou há mais de 48 horas. Consulta o estado das execuções no GitHub.';
 else if(run.status==='partial')notice='Ronda parcial: '+(run.errors||0)+' falha(s), '+(run.empty_lists||0)+' lista(s) vazia(s)'+(run.uncollected_count?' e '+run.uncollected_count+' consultas por concluir':'')+'. Os resultados obtidos foram preservados.';
 $('notice').hidden=!notice;$('notice').textContent=notice;
 $('last-observation').textContent=run?.finished_at_utc?'Ronda concluída · '+stamp(run.finished_at_utc):'Primeira recolha em preparação';
 renderCards();renderMetrics();render();renderFlags();renderWorld();renderQueries();
 $('refresh').disabled=false;
}
function observations(){return (state.latest.run?.observations||[]).filter(allowedRecord);}
function renderCards(){
 $('rank-grid').innerHTML=['1482','1301','26'].map(cat=>{const name=CAT[cat];
  const obs=observations().filter(r=>r.country==='pt'&&r.category===cat);
  const r=obs.find(r=>r.source==='apple_rss'&&r.status==='ranked')||obs.find(r=>r.source==='apple_ids'&&r.status==='ranked')||obs.find(r=>r.source==='apple_rss')||obs[0];
  const number=r?.rank?esc(r.rank)+'<small>.º</small>':'—';
  const status=r?(r.status==='not_found'?'Não encontrado nos '+r.count+' programas':r.status==='error'?'Falha na consulta':r.status==='empty'?'Lista vazia':'Lista de '+r.count+' programas'):'A aguardar a primeira recolha';
  return '<article class="rank-card"><div class="category">'+esc(name)+' <span>'+(cat==='1482'?'▤':cat==='1301'?'◈':'↗')+'</span></div><div class="rank-number">'+number+'</div><div class="source">'+esc(r?LABEL[r.source]:'Apple Podcasts')+'<br>'+esc(status)+'<br>'+esc(r?stamp(r.observed_at_utc):'Sem posição atual confirmada')+'</div>'+(r?.divergent?badge(r):'')+(r?'<button class="inspect" data-observation="'+esc(r.id)+'" aria-label="Ver dados de '+esc(name)+'">Ver</button>':'')+'</article>';
 }).join('');
}
function renderMetrics(){
 const h=state.history.filter(r=>r.category&&r.rank);
 const markets=new Set([...h.map(r=>r.country),...(state.peaks||[]).map(r=>r.country)]);

 $('metrics').innerHTML=[['174','mercados na cobertura diária'],[markets.size,'mercados com presença no arquivo'],[state.history.filter(r=>r.source==='historical').length,'registos históricos fornecidos'],[state.history.length,'observações com posição no arquivo']].map(([n,l])=>'<div class="metric"><strong>'+esc(n)+'</strong><span>'+esc(l)+'</span></div>').join('');
}
function filtered(){
 const cc=$('country').value,cat=$('category').value,source=$('source').value,period=$('period').value,q=$('search').value.toLowerCase(),div=$('divergences').checked;
 const cutoff=period==='all'?null:Date.now()-Number(period)*86400000;
 return state.history.filter(r=>(!cc||r.country===cc)&&(!cat||r.category===cat)&&(!source||r.source===source)&&(!div||r.divergent)&&(!cutoff||Date.parse(dateval(r))>=cutoff)&&(!q||JSON.stringify([r.date,r.source_name,r.source,r.notes,r.original_status,r.rank]).toLowerCase().includes(q))).sort((a,b)=>dateval(b).localeCompare(dateval(a)));
}
function render(){
 const rows=filtered();renderChart(rows);renderPeaks();
 const pages=Math.max(1,Math.ceil(rows.length/20));state.page=Math.min(state.page,pages-1);
 $('history-count').textContent=rows.length+' observações';
 $('history-body').innerHTML=rows.slice(state.page*20,(state.page+1)*20).map(r=>'<tr><td>'+esc(r.observed_at_utc?stamp(r.observed_at_utc):day(r.date)+(r.historical_time_text?' · '+r.historical_time_text:''))+'</td><td>'+esc(country(r.country))+'</td><td>'+esc(CAT[r.category]||r.category_name||'Por confirmar')+'</td><td><strong>'+esc(r.rank)+'.º</strong></td><td>'+esc(sourceLabel(r))+'<br>'+badge(r)+'</td><td><button class="link-button" data-observation="'+esc(r.id)+'">Ver registo</button></td></tr>').join('')||'<tr><td colspan="6" class="empty">Sem registos para estes filtros.</td></tr>';
 $('page-summary').textContent=rows.length?'Página '+(state.page+1)+' de '+pages:'Sem resultados';
 $('prev').disabled=state.page===0;$('next').disabled=state.page>=pages-1;
}
function renderChart(rows){
 const chosen=rows.filter(r=>r.category&&r.rank&&dateval(r));
 $('chart-summary').textContent=chosen.length?Math.min(...chosen.map(r=>r.rank))+'.º · melhor posição observada':'Sem posições observadas';
 $('chart-subtitle').textContent=chosen.length?chosen.length+' observações · '+day(dateval(chosen[chosen.length-1]))+' a '+day(dateval(chosen[0])):'Altera os filtros para consultar outro período ou mercado.';
 if(!chosen.length){$('chart').innerHTML='<div class="empty"><h3>Há mais histórias no arquivo.</h3>Não existem posições para a seleção atual.</div>';return;}
 const W=1000,H=275,L=44,R=18,T=25,B=35;
 const times=chosen.map(r=>Date.parse(r.observed_at_utc||r.date+'T12:00:00Z'));
 let lo=Math.min(...times),hi=Math.max(...times);if(lo===hi){lo-=43200000;hi+=43200000;}
 const max=Math.max(5,Math.ceil(Math.max(...chosen.map(r=>r.rank))/5)*5);
 const x=t=>L+(t-lo)/(hi-lo)*(W-L-R),y=rank=>T+(rank-1)/(max-1)*(H-T-B);
 const ticks=[1,...Array.from({length:4},(_,i)=>Math.round(1+(max-1)*(i+1)/4))];
 let svg='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Posições observadas na seleção">';
 ticks.forEach(t=>{svg+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y(t)+'" y2="'+y(t)+'"/><text x="5" y="'+(y(t)+4)+'">'+t+'.º</text>';});
 for(let i=0;i<5;i++){const t=lo+(hi-lo)*i/4;svg+='<text text-anchor="'+(i===0?'start':i===4?'end':'middle')+'" x="'+x(t)+'" y="'+(H-5)+'">'+esc(new Intl.DateTimeFormat('pt-PT',{month:'short',year:'2-digit',timeZone:'UTC'}).format(t))+'</text>';}
 const colors={historical:'#b39563',apple_ids:'#264d45',apple_rss:'#68518b'};
 // Draw lines only within the same source, country, category, and a gap under 36 hours.
 const groups={};chosen.forEach((r,i)=>{const key=r.source+':'+r.country+':'+r.category;(groups[key]||=[]).push({r,i});});
 Object.values(groups).forEach(g=>{g.sort((a,b)=>times[a.i]-times[b.i]);for(let i=1;i<g.length;i++){const a=g[i-1],b=g[i];if(a.r.source==='historical'||times[b.i]-times[a.i]>129600000)continue;svg+='<line style="stroke:'+colors[a.r.source]+';stroke-width:1.5;opacity:.5" x1="'+x(times[a.i])+'" y1="'+y(a.r.rank)+'" x2="'+x(times[b.i])+'" y2="'+y(b.r.rank)+'"/>';}});
 chosen.forEach((r,i)=>{svg+='<circle class="point" tabindex="0" role="button" aria-label="'+esc(country(r.country)+' '+(CAT[r.category]||'')+' '+r.rank+'.º '+day(dateval(r)))+'" data-observation="'+esc(r.id)+'" cx="'+x(times[i])+'" cy="'+y(r.rank)+'" r="'+(r.source==='historical'?4:5)+'" fill="'+(colors[r.source]||colors.historical)+'" opacity=".85"><title>'+esc(day(dateval(r))+' · '+r.rank+'.º · '+(sourceLabel(r)))+'</title></circle>';});
 $('chart').innerHTML=svg+'</svg>';
}
function renderWorld(){
 const obs=observations().filter(r=>r.source==='apple_ids');
 const grouped={};obs.forEach(r=>{(grouped[r.country]||={})[r.category]=r;});
 const only=$('only-ranked').checked;
 const list=Object.keys(grouped).filter(c=>!only||Object.values(grouped[c]).some(r=>r.rank)).sort((a,b)=>country(a).localeCompare(country(b),'pt'));
 const run=state.latest.run;
 $('coverage-summary').textContent=run?(run.coverage_market_count||174)+' mercados consultados · Listas até 250 programas. Cada célula permite consultar a fonte e a hora efetiva.':'A cobertura internacional aparecerá após a primeira ronda.';
 $('world-body').innerHTML=list.map(c=>'<tr><td><span class="country-code">'+esc(c.toUpperCase())+'</span>'+esc(country(c))+'</td>'+['1482','1301','26'].map(cat=>{const r=grouped[c][cat];if(!r)return '<td>Por consultar</td>';return '<td><button class="rank-pill '+(r.rank?'':'absent')+'" data-observation="'+esc(r.id)+'">'+(r.rank?r.rank+'.º':r.status==='not_found'?'Não encontrado / '+r.count:r.status==='empty'?'Lista vazia':'Falha')+'</button></td>';}).join('')+'<td>'+esc(stamp(Object.values(grouped[c])[0].observed_at_utc))+'</td></tr>').join('');
 $('world-empty').hidden=list.length>0;
}
function recordedCountries(){
 return [...new Set([...state.history,...state.peaks].filter(r=>r.country&&r.rank).map(r=>r.country))].sort((a,b)=>country(a).localeCompare(country(b),'pt'));
}
function renderFlags(){
 $('country-flags').innerHTML=recordedCountries().map(c=>{
  const n=[...state.history,...state.peaks].filter(r=>r.country===c&&r.rank).length;
  return '<button class="country-flag" data-country="'+esc(c)+'" aria-label="Consultar posições de '+esc(country(c))+'"><span class="flag-emoji" aria-hidden="true">'+flag(c)+'</span><strong>'+esc(country(c))+'</strong><small>'+n+' registo'+(n===1?'':'s')+'</small></button>';
 }).join('');
}
function showCountry(cc){
 const rows=state.history.filter(r=>r.country===cc&&r.rank).sort((a,b)=>dateval(b).localeCompare(dateval(a)));
 const peaks=state.peaks.filter(r=>r.country===cc&&r.rank);
 const categoryCards=['1482','1301','26'].map(cat=>{const name=CAT[cat];
  const records=[...rows,...peaks].filter(r=>r.category===cat);
  return '<div class="country-position"><span>'+esc(name)+'</span><strong>'+(records.length?Math.min(...records.map(r=>r.rank))+'.º':'—')+'</strong><small>'+(records.length?'Melhor posição no arquivo':'Sem posição registada')+'</small></div>';
 }).join('');
 const dated=rows.length?'<h3>Posições com data de observação</h3><div class="table-wrap"><table><thead><tr><th>Data</th><th>Categoria</th><th>Posição</th><th>Origem e validação</th><th></th></tr></thead><tbody>'+rows.map(r=>'<tr><td>'+esc(r.observed_at_utc?stamp(r.observed_at_utc):day(r.date)+(r.historical_time_text?' · '+r.historical_time_text:''))+'</td><td>'+esc(CAT[r.category]||'Por confirmar')+'</td><td><strong>'+r.rank+'.º</strong></td><td>'+esc(sourceLabel(r))+'<br>'+badge(r)+'</td><td><button class="link-button" data-observation="'+esc(r.id)+'">Ver registo</button></td></tr>').join('')+'</tbody></table></div>':'';
 const undated=peaks.length?'<h3>Referências históricas sem data do pico</h3><p class="caption">A última presença indicada é conservada separadamente: não demonstra a data em que foi alcançada a posição.</p><div class="table-wrap"><table><thead><tr><th>Categoria</th><th>Posição</th><th>Última presença indicada</th><th>Validação</th></tr></thead><tbody>'+peaks.map(r=>'<tr><td>'+esc(CAT[r.category])+'</td><td><strong>'+r.rank+'.º</strong></td><td>'+esc(day(r.last_charted_date))+'</td><td><span class="tag documented">Registo fornecido · data do pico não indicada</span></td></tr>').join('')+'</tbody></table></div>':'';
 $('detail-content').innerHTML='<div class="eyebrow">PAÍS OU REGIÃO COM REGISTOS</div><h2><span class="flag-emoji" aria-hidden="true">'+flag(cc)+'</span> '+esc(country(cc))+'</h2><div class="country-positions">'+categoryCards+'</div><p class="caption">Os valores reúnem os registos fornecidos pelo projeto e as observações Apple. Cada posição mantém a sua origem e o estado de validação; uma referência histórica não indica a classificação atual.</p>'+dated+undated+'<button class="button" data-evolution="'+esc(cc)+'">Consultar evolução histórica</button>';
 if(!$('detail').open)$('detail').showModal();
}
function renderPeaks(){const el=$('peaks');if(!el)return;const cc=$('country').value,cat=$('category').value;const rows=(state.peaks||[]).filter(r=>(!cc||r.country===cc)&&(!cat||r.category===cat));el.innerHTML=rows.map(r=>'<div class="query-row"><b>'+esc(country(r.country))+' · '+esc(CAT[r.category])+' · '+r.rank+'.º</b><br>Última presença indicada: '+esc(r.last_charted_date?day(r.last_charted_date):'não indicada')+'<br>'+esc(r.notes)+'</div>').join('')||'<p>Sem referências para esta seleção.</p>';}
function renderQueries(){
 $('query-count').textContent=' · '+state.queries.length;
 $('queries').innerHTML=[...state.queries].reverse().map(q=>'<div class="query-row"><b>'+esc(day(q.date))+' · '+esc(country(q.country))+' · '+esc(q.category_name)+'</b><br>'+esc(q.source_name)+' — '+esc(q.result)+'<br>'+esc(q.notes||'')+(q.url?' <a href="'+esc(safe(q.url))+'" target="_blank" rel="noopener">Fonte</a>':'')+'</div>').join('');
}
function showObservation(id){
 const r=state.history.find(v=>v.id===id)||observations().find(v=>v.id===id);if(!r)return;
 const stateText=r.rank?r.rank+'.º':r.status==='not_found'?'Não encontrado nos '+r.count+' programas':r.status==='empty'?'Lista vazia':'Consulta não verificável';
 const meta=[['Mercado',country(r.country)],['Categoria',CAT[r.category]||r.category_name],['Posição',stateText],['Fonte',sourceLabel(r)],['Consulta',r.observed_at_utc?stamp(r.observed_at_utc)+' (Lisboa)':day(r.date)+(r.historical_time_text?' · '+r.historical_time_text:' · hora não indicada')],['Âmbito',r.count!=null?r.count+' programas recebidos / '+r.requested_limit+' pedidos':'Registo histórico fornecido'],['Estado original',r.original_status||r.quality],['Atualização da fonte',r.source_updated_raw||'Não indicada / significado temporal não confirmado']];
 $('detail-content').innerHTML='<div class="eyebrow">REGISTO DA OBSERVAÇÃO</div><h2>'+esc(CAT[r.category]||r.category_name)+' · '+esc(stateText)+'</h2>'+badge(r)+'<dl class="detail-meta">'+meta.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v||'—')+'</dd>').join('')+'</dl><p>'+esc(r.notes||r.divergence_note||r.error||'A posição corresponde à ordem do programa na lista recebida. A hora de consulta não demonstra a hora exata em que esta posição foi atingida.')+'</p>'+(r.source==='historical'?'<p class="caption">Classificação fornecida pelo projeto, com o estado original preservado. Não corresponde a uma nova verificação automática.</p>':'')+'<div class="proof-links">'+(appleUrl(r.url)?'<a class="button" href="'+esc(safe(r.url))+'" target="_blank" rel="noopener">Abrir fonte</a>':'')+(r.evidence_path?'<a class="button" href="'+esc(RAW+r.evidence_path)+'" target="_blank" rel="noopener">Dados recebidos da Apple</a>':'')+'</div>'+(r.sha256?'<p><code>SHA-256: '+esc(r.sha256)+'</code></p>':'');
 if(!$('detail').open)$('detail').showModal();
}
function exportRows(){
 const rows=filtered();const headers=['Data','Hora UTC','País','Categoria','Posição','Fonte','Comprovação','Divergência','URL','Observações'];
 const quote=v=>{let s=String(v??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
 const csv='\ufeff'+[headers,...rows.map(r=>[r.date,r.observed_at_utc,country(r.country),CAT[r.category]||r.category_name,r.rank,sourceLabel(r),r.original_status||r.quality,r.divergent?'Sim':'Não',appleUrl(r.url)?r.url:'',r.notes||''])].map(r=>r.map(quote).join(';')).join('\r\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='Prazeres_Interrompidos_Classificacoes.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
document.addEventListener('click',e=>{const c=e.target.closest('[data-country]');if(c){showCountry(c.dataset.country);return;}const evo=e.target.closest('[data-evolution]');if(evo){$('country').value=evo.dataset.evolution;$('category').value='';$('source').value='';$('period').value='all';$('search').value='';$('divergences').checked=false;state.page=0;render();$('detail').close();$('evolution').scrollIntoView({behavior:'smooth'});return;}const obs=e.target.closest('[data-observation]');if(obs)showObservation(obs.dataset.observation);});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('.point'))showObservation(e.target.dataset.observation);});
$('detail').querySelector('.close').onclick=()=>$('detail').close();
$('detail').addEventListener('click',e=>{if(e.target===$('detail')){const r=$('detail').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('detail').close();}});
['country','category','source','period','divergences'].forEach(id=>$(id).addEventListener('change',()=>{state.page=0;render();}));
$('search').addEventListener('input',()=>{state.page=0;render();});
$('only-ranked').onchange=renderWorld;
$('prev').onclick=()=>{state.page--;render();};$('next').onclick=()=>{state.page++;render();};
$('refresh').onclick=load;$('export').onclick=exportRows;
document.querySelectorAll('.sidebar nav a').forEach(a=>a.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(v=>v.classList.remove('active'));a.classList.add('active');}));
load();setInterval(load,900000);

