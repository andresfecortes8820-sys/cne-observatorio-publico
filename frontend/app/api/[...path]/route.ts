// Local/development proxy. Production Caddy routes /api directly to FastAPI.
// API_INTERNAL_URL is server-only; visitors cannot choose an upstream destination.
import {NextRequest} from 'next/server';
export const runtime='nodejs';
export const dynamic='force-dynamic';
async function proxy(request:NextRequest,{params}:{params:Promise<{path:string[]}>}){
 const {path}=await params;
 if(path.some(p=>p==='.'||p==='..'||p.includes('/')||p.includes('\\')))return new Response('Invalid path',{status:400});
 const upstream=new URL('/'+path.map(encodeURIComponent).join('/'),process.env.API_INTERNAL_URL||'http://localhost:8000');
 upstream.search=request.nextUrl.search;
 const headers=new Headers();
 for(const name of ['content-type','cookie','origin','x-csrf-token']){const value=request.headers.get(name);if(value)headers.set(name,value)}
 try{
  const response=await fetch(upstream,{method:request.method,headers,body:['GET','HEAD'].includes(request.method)?undefined:await request.arrayBuffer(),redirect:'manual',signal:AbortSignal.timeout(30000),cache:'no-store'});
  const outgoing=new Headers();
  for(const name of ['content-type','content-disposition','retry-after','x-data-cache']){const value=response.headers.get(name);if(value)outgoing.set(name,value)}
  for(const cookie of response.headers.getSetCookie())outgoing.append('set-cookie',cookie);
  outgoing.set('cache-control','no-store');
  return new Response(response.body,{status:response.status,headers:outgoing});
 }catch{return Response.json({detail:'Servidor de datos temporalmente no disponible'},{status:503})}
}
export {proxy as GET,proxy as POST,proxy as PATCH,proxy as DELETE};
