// Browser-only read model for GitHub Pages. No social API calls or credentials.
export const METHODOLOGY='Datos recopilados por GitHub Actions mediante API oficiales y publicados como capturas estáticas. Fechas de publicación en America/Bogota; cada métrica conserva su captura. No representa toda la conversación pública. La programación puede retrasarse y las métricas ausentes no equivalen a cero.';
const day=s=>new Date(s).toLocaleDateString('en-CA',{timeZone:'America/Bogota'});
function aggregate(posts){
 const days=new Map(),platforms=new Map(),measured=posts.filter(p=>p.interactions!==null);
 for(const p of posts){const date=day(p.published_at);const d=days.get(date)||{date,posts:0,interactions:null};d.posts++;if(p.interactions!==null)d.interactions=(d.interactions??0)+p.interactions;days.set(date,d);const n=platforms.get(p.platform)||{platform:p.platform,posts:0,interactions:null};n.posts++;if(p.interactions!==null)n.interactions=(n.interactions??0)+p.interactions;platforms.set(p.platform,n)}
 return {posts:posts.length,interactions:measured.length?measured.reduce((n,p)=>n+p.interactions,0):null,measured_posts:measured.length,included_platforms:[...new Set(measured.map(p=>p.platform))].sort(),daily:[...days.values()].sort((a,b)=>a.date.localeCompare(b.date)),platforms:[...platforms.values()]};
}
export function querySnapshot(snapshot,path,now=new Date()){
 if(snapshot.version!==1)throw new Error('Formato de datos no compatible');
 const url=new URL(path,'https://snapshot.local'),q=url.searchParams;
 const date=day(now),end=q.get('end')||date;
 const initial=new Date(date+'T12:00:00Z');initial.setUTCDate(initial.getUTCDate()-29);
 const start=q.get('start')||initial.toISOString().slice(0,10);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!/^\d{4}-\d{2}-\d{2}$/.test(end)||end<start||(+new Date(end)-+new Date(start))/86400000>366)throw new Error('Rango inválido; máximo 366 días');
 const selectedAccounts=snapshot.accounts.filter(a=>(!q.get('platform')||a.platform===q.get('platform'))&&(!q.get('account')||String(a.id)===q.get('account')));
 const allowed=new Set(selectedAccounts.map(a=>a.id));
 const matches=p=>allowed.has(p.account_id)&&(!q.get('keyword')||p.text.toLocaleLowerCase('es').includes(q.get('keyword').toLocaleLowerCase('es')))&&(!q.get('format')||p.format===q.get('format'));
 const all=snapshot.posts.filter(matches).sort((a,b)=>b.published_at.localeCompare(a.published_at)||b.id-a.id);
 const filtered=all.filter(p=>day(p.published_at)>=start&&day(p.published_at)<=end);
 if(url.pathname==='/accounts')return {items:snapshot.accounts,limit:200};
 if(url.pathname==='/dashboard'){
  const duration=Math.round((+new Date(end)-+new Date(start))/86400000)+1;
  const priorEnd=new Date(start+'T12:00:00Z');priorEnd.setUTCDate(priorEnd.getUTCDate()-1);
  const priorStart=new Date(start+'T12:00:00Z');priorStart.setUTCDate(priorStart.getUTCDate()-duration);
  const previous=all.filter(p=>day(p.published_at)>=priorStart.toISOString().slice(0,10)&&day(p.published_at)<=priorEnd.toISOString().slice(0,10));
  const captures=filtered.map(p=>p.captured_at).filter(Boolean).sort();const summary=aggregate(filtered);
  return {...summary,previous:aggregate(previous),followers:selectedAccounts,top_posts:[...filtered].sort((a,b)=>(b.interactions??-1)-(a.interactions??-1)).slice(0,5),possibly_truncated:!!snapshot.truncated,previous_truncated:!!snapshot.truncated,limit:2000,start,end,timezone:'America/Bogota',last_capture:captures.at(-1)||null,generated_at:snapshot.generated_at,cache_seconds:600,methodology:METHODOLOGY,source_status:snapshot.sources,coverage:{published_accounts:selectedAccounts.length,platforms_with_data:[...new Set(filtered.map(p=>p.platform))],measured_posts:summary.measured_posts,observed_posts:filtered.length,complete:!snapshot.truncated,status:snapshot.truncated?'partial':filtered.length?'available':'no_authorized_data'},demo:false};
 }
 if(url.pathname==='/posts'){
  const page=Number(q.get('page')||1),size=Number(q.get('page_size')||25);
  if(!Number.isInteger(page)||page<1||page>200||!Number.isInteger(size)||size<1||size>100)throw new Error('Paginación inválida');
  const offset=(page-1)*size;return {items:filtered.slice(offset,offset+size),page,page_size:size,has_more:offset+size<filtered.length,methodology:METHODOLOGY};
 }
 const id=Number(url.pathname.split('/').at(-1)),post=snapshot.posts.find(p=>p.id===id);
 if(!post)throw new Error('Publicación no disponible');
 const page=Number(q.get('page')||1);if(!Number.isInteger(page)||page<1||page>200)throw new Error('Página inválida');
 const history=[...(post.history||[])].reverse();return {...post,history:history.slice((page-1)*50,page*50),page,has_more:page*50<history.length,methodology:METHODOLOGY};
}
let cached=null,loaded=0;
export async function readSnapshot(path,base='',signal){
 if(!cached||Date.now()-loaded>60000){const r=await fetch(base+'/data/observatory.json',{cache:'no-cache',credentials:'omit'});if(!r.ok)throw new Error('La captura pública aún no está disponible');cached=await r.json();loaded=Date.now()}
 if(signal?.aborted)throw new DOMException('Aborted','AbortError');
 return querySnapshot(cached,path);
}
