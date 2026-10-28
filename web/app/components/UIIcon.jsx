/** Small, shared outline icons for navigation and ordinary UI actions. */
export default function UIIcon({ name, size = 20, ...props }) {
  const paths = {
    play: <path d="m9 5 11 7-11 7z" />,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10h.01" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z" />,
    user: <><circle cx="12" cy="8" r="3.5" /><path d="M4.5 21v-2a7.5 7.5 0 0 1 15 0v2" /></>,
    home: <><path d="m3 10 9-7 9 7v10H3z" /><path d="M9 20v-7h6v7" /></>,
    live: <><circle cx="12" cy="12" r="2" /><path d="M7.5 7.5a6.4 6.4 0 0 0 0 9m9-9a6.4 6.4 0 0 1 0 9M4 4a11.3 11.3 0 0 0 0 16M20 4a11.3 11.3 0 0 1 0 16" /></>,
    wallet: <><path d="M20 7H5a2 2 0 0 1 0-4h13v4M5 7H3v13h17V7" /><path d="M20 11h-6v5h6m-3-2.5h.01" /></>,
    data: <><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M7 16v-3m5 3V8m5 8v-6" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>,
    moon: <path d="M20 15A8.5 8.5 0 0 1 9 4a8.5 8.5 0 1 0 11 11Z" />,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 8a2.5 2.5 0 1 1 4 2c-1.5 1-1.5 1-1.5 3m0 3h.01" /></>,
    expand: <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 3l6 6m12-6-6 6M3 21l6-6m12 6-6-6" />,
    grip: <path d="M5 19 19 5M11 19l8-8M17 19l2-2" />,
    history: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
    monitor: <><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></>,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="M9 12h6"/></>,
    logout: <path d="M9 4H4v16h5m5-5 4-3-4-3m-6 3h12" />,
    incoming: <path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4" />,
    outgoing: <path d="M12 17V4m-5 5 5-5 5 5M4 17v4h16v-4" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    filter: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="2" /><circle cx="16" cy="12" r="2" /><circle cx="10" cy="18" r="2" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.data}</svg>;
}
