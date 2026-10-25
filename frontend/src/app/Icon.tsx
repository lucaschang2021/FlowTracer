const paths = {
  plus: 'M12 4v16M4 12h16', minus: 'M5 12h14', close: 'M6 6l12 12M18 6L6 18',
  reset: 'M5 6v5h5M5 11a8 8 0 1 0 3-6', fit: 'M9 3H3v6M15 3h6v6M21 15v6h-6M9 21H3v-6M8 12h8M12 8v8',
  arrow: 'M5 12h14M14 7l5 5-5 5', radar: 'M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l7-7',
};
export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}
