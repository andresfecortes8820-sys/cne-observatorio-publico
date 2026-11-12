import type { NextConfig } from 'next';
const pages=process.env.NEXT_PUBLIC_DATA_MODE==='snapshot';
const config: NextConfig = { output: pages?'export':'standalone',basePath:process.env.NEXT_PUBLIC_BASE_PATH||'',trailingSlash:pages,poweredByHeader:false,...(pages?{}:{async headers(){return [{source:'/(.*)',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},{key:'X-Frame-Options',value:'DENY'}]}]}})};
export default config;
