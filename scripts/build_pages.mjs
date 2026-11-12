// Temporarily exclude server handlers for static export; restore even on failure.
import {rename,copyFile,mkdir,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const front=path.join(root,'frontend');
const api=path.join(front,'app/api'),excluded=path.join(front,'.pages-api-excluded');
await rename(api,excluded);
let result;
try{
 await mkdir(path.join(front,'public/data'),{recursive:true});
 await copyFile(path.join(root,'data/observatory.json'),path.join(front,'public/data/observatory.json'));
 result=spawnSync(process.execPath,[path.join(front,'node_modules/next/dist/bin/next'),'build'],{cwd:front,stdio:'inherit',env:{...process.env,NEXT_PUBLIC_DATA_MODE:'snapshot',NEXT_TELEMETRY_DISABLED:'1'}});
 if(result.status===0)await writeFile(path.join(front,'out/.nojekyll'),'');
}finally{await rename(excluded,api)}
process.exit(result?.status??1);
