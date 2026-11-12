import type { Metadata } from 'next';
import './globals.css';
import './public.css';
export const metadata: Metadata = {title:'CNE | Escucha de redes sociales',description:'Comentarios y respuestas de la audiencia en las cuentas administradas por el CNE, con fuentes y cobertura explícitas'};
export default function Layout({children}:{children:React.ReactNode}) {return <html lang="es"><body>{children}</body></html>}
