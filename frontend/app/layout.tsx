import type { Metadata } from 'next';
import './globals.css';
import './public.css';
export const metadata: Metadata = {title:'CNE | Social Intelligence',description:'Monitoreo institucional de redes sociales con fuentes oficiales'};
export default function Layout({children}:{children:React.ReactNode}) {return <html lang="es"><body>{children}</body></html>}
