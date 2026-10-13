const palettes: Record<string, [string, string, string]> = {
  blue: ['#91cbef', '#235881', '#041321'], ice: ['#d1e5e8', '#567b8f', '#101824'],
  gold: ['#f5ddaa', '#a87738', '#241709'], teal: ['#c5f5e7', '#388b78', '#061d22'],
  violet: ['#e0c8fb', '#7650a5', '#190e34'], silver: ['#edf1f0', '#8399a9', '#111d2e'],
};

/** Original 2D procedural SVG artwork. No external imagery or real geographic outlines. */
export function Planet({ id, color }: { id: string; color: string }) {
  const [light, mid, dark] = palettes[color] ?? palettes.blue;
  return <svg className={`planet planet-${color}`} viewBox="0 0 100 100" aria-hidden="true">
    <defs>
      <radialGradient id={`${id}-body`} cx="25%" cy="18%" r="83%"><stop stopColor={light}/><stop offset=".35" stopColor={mid}/><stop offset=".8" stopColor={dark}/><stop offset="1" stopColor="#02050d"/></radialGradient>
      <radialGradient id={`${id}-shade`} cx="26%" cy="25%" r="78%"><stop offset=".25" stopColor="#020813" stopOpacity="0"/><stop offset=".8" stopColor="#020813" stopOpacity=".3"/><stop offset="1" stopColor="#020813" stopOpacity=".95"/></radialGradient>
      <clipPath id={`${id}-clip`}><circle cx="50" cy="50" r="36"/></clipPath>
      <filter id={`${id}-texture`} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feTurbulence baseFrequency={color === 'gold' ? '.035 .18' : '.08 .11'} numOctaves="5" seed={color.length * 7} type="fractalNoise"/>
        <feColorMatrix type="saturate" values="0"/>
        <feComponentTransfer><feFuncA type="linear" slope=".48"/></feComponentTransfer>
        <feBlend in="SourceGraphic" mode="soft-light"/>
      </filter>
    </defs>
    <g className="planet-orbits" fill="none" stroke={light} strokeWidth=".25"><circle cx="50" cy="50" r="47" strokeDasharray="1 2"/><circle cx="50" cy="50" r="44"/><path d="M50 0v12M50 88v12M0 50h12M88 50h12"/>{color === 'blue' && <ellipse cx="50" cy="50" rx="49" ry="20" transform="rotate(-40 50 50)"/>}{color === 'violet' && <path d="M50 2L92 74H8ZM50 98L8 26H92Z"/>}</g>
    <circle cx="50" cy="50" r="45" fill="none" stroke={mid} strokeOpacity=".15"/>
    <circle cx="50" cy="50" r="40" fill="none" stroke={light} strokeOpacity=".35" strokeWidth=".65"/>
    <g clipPath={`url(#${id}-clip)`}>
      <circle cx="50" cy="50" r="36" fill={`url(#${id}-body)`}/>
      <circle cx="50" cy="50" r="36" fill={mid} filter={`url(#${id}-texture)`} opacity=".85"/>
      <g fill="none" stroke={light} opacity=".16" strokeWidth=".8">
        <path d="M9 42Q27 14 51 35T93 39M15 49Q41 25 54 45T86 48M23 65Q41 42 64 61T93 64M36 16Q53 33 49 51T67 88"/>
        <path d="M13 56Q29 72 43 54T78 21M23 79Q33 55 46 72T84 70" strokeWidth=".55"/>
      </g>
      <circle cx="50" cy="50" r="36" fill={`url(#${id}-shade)`}/>
    </g>
    <circle cx="50" cy="50" r="36" fill="none" stroke={light} strokeOpacity=".58" strokeWidth=".6"/>
    <path d="M19 36A34 34 0 0 1 49 16" stroke={light} strokeWidth="1.2" strokeOpacity=".9" fill="none"/>
  </svg>;
}
