'use strict';
const $ = id => document.getElementById(id);
let data = {papers: [], sources: [], state: {}}, view = 'all', topic = '', page = 1, filtered = [];
const pageSize = 15;
const names = {all: ['把新进展，带回你的研究。', '追踪电力电子与人工智能的交叉研究，让每一次阅读更有方向。', '全部领域'], fault: ['聚焦故障，理解系统。', '电力电子设备与电机驱动系统中的 AI 检测、诊断与定位。', '故障检测专题'], favorite: ['为下一次灵感，留一份索引。', '你收藏的论文保存在本机数据库中。', '我的收藏'], read: ['每一次阅读，都有迹可循。', '回看已经读过的研究，再次连接值得追问的问题。', '已读记录']};
function node(tag, className, text) { const e = document.createElement(tag); if(className) e.className = className; if(text !== undefined) e.textContent = text; return e; }
function button(text, className, action) {const e = node('button', className, text); e.addEventListener('click', action); return e;}
function dateLabel(p) {return p.date_precision === '年' ? p.published.slice(0,4) : p.date_precision === '月' ? p.published.slice(0,7) : p.published;}
async function api(path, body) {
  const r = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
  if(!r.ok) throw new Error(r.status === 401 ? '本机登录已失效，请重新双击 start.cmd。' : `请求失败（${r.status}）`);
  return r.json();
}
async function refresh() {
  try {data = await api('/api/data'); renderStatus(); renderStats(); renderSources(); render();}
  catch(e) {$('status').textContent = e.message; $('status-dot').className='status-dot warning';}
}
function renderStats() {
  const counts = {all:data.papers.length, fault:data.papers.filter(p=>p.fault).length, favorite:data.papers.filter(p=>p.favorite).length, read:data.papers.filter(p=>p.read).length};
  for (const [key,value] of Object.entries(counts)) { $('count-'+key).textContent=value; if($('stat-'+key)) $('stat-'+key).textContent=value; }
  const added=data.papers.filter(p=>p.discovered.slice(0,10)===data.today).length;
  $('stat-new').textContent=added;
  const allOK=data.sources.length && data.sources.every(s=>s.status==='ok');
  $('new-description').textContent=added ? '包含首次导入及补收录' : data.state.running ? '采集中，结果尚未完整' : allOK ? '今日暂无新增' : '已检查来源今日暂无新增；部分来源覆盖受限';
}
function renderStatus() {
  $('status').textContent = data.state.stage;
  $('ai-status').textContent = data.state.ai + ' · 付费论文也收录，不下载全文。';
  const warning = data.sources.some(s=>['error','limited'].includes(s.status));
  $('status-dot').className='status-dot'+(data.state.running?' busy':warning?' warning':'');
  $('update').disabled=!!data.state.running;
  $('update').querySelector('span').textContent=data.state.running&&data.state.task==='collect'?'正在采集…':'检查更新';
  $('enrich').disabled=!!data.state.running||data.ai_pending===0;
  $('enrich').textContent=data.state.running&&data.state.task==='ai'?'正在生成…':'生成译名与概括';
  $('ai-choice').textContent=`检查更新不使用 AI。待中文补全 ${data.ai_pending||0} 篇；点击生成才使用本机 Ollama 模型。`;
}
function renderSources() {
  const box=$('sources'); box.replaceChildren();
  const labels={ok:'已检查',error:'失败',limited:'覆盖受限',running:'采集中',pending:'等待采集'};
  for(const s of data.sources) {
    const item=node('div','source'); item.append(node('span','source-status '+s.status,labels[s.status]||s.status),node('strong','',s.name),node('small','',s.message||''));
    item.append(node('small','', '最近检查：'+(s.checked?.replace('T',' ').slice(0,19)||'尚未检查')+' · 最近成功：'+(s.last_success?.replace('T',' ').slice(0,19)||'暂无'))); box.append(item);
  }
  $('dialog-ai').textContent='中文生成：'+data.state.ai+'。运行日志与论文数据库位于项目 data 文件夹。关闭网页不会停止采集；关闭启动窗口才会停止程序。';
  if($('journal').options.length===1) for(const j of data.journals||[]) {const option=node('option','',j.id.startsWith('T')?j.id:j.name); option.value=j.id; $('journal').append(option);}
}
function render() {
  const q=$('search').value.trim().toLowerCase(), journal=$('journal').value, kind=$('kind').value;
  filtered=data.papers.filter(p=> {
    if(view==='fault'&&!p.fault || view==='favorite'&&!p.favorite || view==='read'&&!p.read) return false;
    if(journal&&p.journal!==journal || topic&&!p.tags.includes(topic)) return false;
    if(kind==='review'&&!p.review || kind==='research'&&p.review) return false;
    if($('unread').checked&&p.read) return false;
    if($('date-from').value&&p.published<$('date-from').value || $('date-to').value&&p.published>$('date-to').value) return false;
    return !q || [p.title,p.title_zh,p.abstract,p.summary,p.doi,p.journal,...p.tags].join(' ').toLowerCase().includes(q);
  });
  const sort=$('sort').value; filtered.sort((a,b)=>(b[sort]||'').localeCompare(a[sort]||''));
  const totalPages=Math.max(1,Math.ceil(filtered.length/pageSize)); page=Math.min(page,totalPages);
  $('result-count').textContent=filtered.length+' 篇';
  const box=$('papers'); box.replaceChildren();
  for(const p of filtered.slice((page-1)*pageSize,page*pageSize)) box.append(card(p));
  if(!filtered.length) {
    const empty=node('div','empty'); empty.append(node('strong','',data.state.running?'正在建立你的文献档案…':data.papers.length?'当前筛选下没有论文':'还没有收录到论文'));
    empty.append(node('p','',data.state.running?'首次会检查最近 12 个月，耗时取决于网络与来源响应。已有数据会持续显示。':data.papers.length?'试试其他关键词，或清空主题、日期和期刊筛选。':'请检查来源状态。网络失败、元数据缺失和暂时无匹配论文是不同情况。')); box.append(empty);
  }
  $('page-info').textContent=`${page} / ${totalPages}`; $('previous').disabled=page<=1; $('next').disabled=page>=totalPages;
  renderTags();
}
function renderTags() {
  const box=$('tags'); box.replaceChildren();
  const topics=['全部主题','数字孪生','故障检测','寿命预测','控制优化','参数辨识','设计与建模','强化学习','物理信息学习'];
  for(const name of topics) {const value=name==='全部主题'?'':name; box.append(button(name,'tag'+(topic===value?' active':''),()=>{topic=value;page=1;render();}));}
}
function card(p) {
  const card=node('article','paper'+(p.read?' read':''));
  const mark=button(p.favorite?'★':'☆','bookmark'+(p.favorite?' saved':''),()=>save(p,'favorite',!p.favorite)); mark.title=p.favorite?'取消收藏':'收藏论文'; mark.setAttribute('aria-label',mark.title); mark.setAttribute('aria-pressed',String(!!p.favorite)); card.append(mark);
  const head=node('div','paper-head');
  head.append(node('span','journal-label',data.journals.find(j=>j.id===p.journal)?.name.replace('IEEE Transactions on ','')||p.journal),node('span','',dateLabel(p)),node('span','type-label',p.review?'综述':'研究论文'));
  if(p.backfill) head.append(node('span','backfill','补收录'));
  card.append(head,node('h3','',p.title_zh||p.title));
  if(p.title_zh&&p.title_zh!==p.title) card.append(node('p','english',p.title));
  if(!p.title_zh) card.append(node('p','missing','中文译名待生成'));
  if(p.summary) card.append(node('p','summary',p.summary));
  else card.append(node('p','missing',p.abstract?'已有摘要 · 中文概括待生成':'未获取摘要 · 仅收录题名和译名'));
  const tags=node('div','paper-tags'); for(const t of p.tags) tags.append(node('span','',t)); card.append(tags);
  const bottom=node('div','paper-bottom');
  bottom.append(node('span','',p.date_basis+(p.date_precision!=='日'?' · 精度到'+p.date_precision:'')));
  if(p.ai_note) bottom.append(node('span','',p.ai_note));
  bottom.append(button(p.read?'✓ 已读':'标记已读','',()=>save(p,'read',!p.read)));
  const url=p.url;
  if(/^https?:\/\//i.test(url)) {const link=node('a','','查看原文 ↗'); link.href=url;link.target='_blank';link.rel='noopener noreferrer'; link.addEventListener('click',()=>save(p,'read',true));bottom.append(link);}
  card.append(bottom); return card;
}
async function save(p,field,value) {
  try {await api('/api/paper',{id:p.id,field,value});p[field]=value?1:0;renderStats();render();}
  catch(e) {$('status').textContent=e.message;}
}
for(const nav of document.querySelectorAll('[data-view]')) nav.addEventListener('click',()=>{view=nav.dataset.view;page=1;for(const e of document.querySelectorAll('[data-view]')) e.classList.toggle('active',e===nav); const n=names[view];$('page-title').textContent=n[0];$('page-description').textContent=n[1];$('crumb').textContent=n[2];$('list-title').textContent=view==='all'?'文献动态':n[2];render();});
for(const id of ['search','journal','kind','sort','date-from','date-to','unread']) $(id).addEventListener(id==='search'?'input':'change',()=>{page=1;render();});
$('reset').addEventListener('click',()=>{for(const id of ['search','journal','kind','date-from','date-to']) $(id).value='';$('unread').checked=false;topic='';page=1;render();});
$('previous').addEventListener('click',()=>{page--;render();$('list-title').scrollIntoView({block:'start'});});
$('next').addEventListener('click',()=>{page++;render();$('list-title').scrollIntoView({block:'start'});});
$('enrich').addEventListener('click',async()=>{try{await api('/api/enrich',{});await refresh();}catch(e){$('status').textContent=e.message;}});
$('update').addEventListener('click',async()=>{try{await api('/api/update',{});await refresh();}catch(e){$('status').textContent=e.message;}});
for(const id of ['open-sources','view-status']) $(id).addEventListener('click',()=>$('source-dialog').showModal());
$('close-dialog').addEventListener('click',()=>$('source-dialog').close());
$('export').addEventListener('click',()=>{const text=JSON.stringify(filtered,null,2);const url=URL.createObjectURL(new Blob([text],{type:'application/json;charset=utf-8'}));const a=node('a');a.href=url;a.download='power-ai-papers-'+data.today+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
refresh();setInterval(refresh,5000);
