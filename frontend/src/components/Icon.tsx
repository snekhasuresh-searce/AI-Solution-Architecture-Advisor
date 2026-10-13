const PATHS = {
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5m0-8.5v.01",
  close: "M6 6l12 12M18 6L6 18",
  chevron: "M6 9l6 6 6-6",
  logout: "M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4",
  check: "M5 12.5l4.5 4.5L19 7.5",
  upload: "M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 15v3.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V15",
  download: "M12 4v12m0 0l-4.5-4.5M12 16l4.5-4.5M5 15v3.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V15",
  plus: "M12 5v14M5 12h14",
  copy: "M9 9h10v10H9zM5 15V5h10",
  send: "M5 12h13m0 0l-5.5-5.5M18 12l-5.5 5.5",
  file: "M7 3.5h7l4 4V20.5H7zM14 3.5V8h4",
  redo: "M19 8v4h-4M19 12a7 7 0 1 1-2.05-4.95",
  alert: "M12 8v5m0 3.5v.01M10.3 4.2L2.8 17.5A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z",
  // Document editor
  undo: "M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11",
  redoEdit: "M15 14l5-5-5-5M20 9H9.5a5.5 5.5 0 0 0 0 11H13",
  alignLeft: "M4 6h16M4 10h10M4 14h16M4 18h10",
  alignCenter: "M4 6h16M7 10h10M4 14h16M7 18h10",
  alignRight: "M4 6h16M10 10h10M4 14h16M10 18h10",
  alignJustify: "M4 6h16M4 10h16M4 14h16M4 18h16",
  listBullet: "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
  listOrdered: "M10 6h10M10 12h10M10 18h10M4 4.5l1.5-1v5M3.5 13.5a1.5 1.5 0 0 1 3 .5L3.5 18.5h3",
  indent: "M4 6h16M11 10h9M11 14h9M4 18h16M4 9.5l3 2.5-3 2.5",
  outdent: "M4 6h16M11 10h9M11 14h9M4 18h16M7 9.5L4 12l3 2.5",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  unlink: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1M4 4l16 16",
  image: "M4 5h16v14H4zM4 16l4.5-4.5 4 4 2.5-2.5L20 18M15.5 9.5h.01",
  table: "M4 5h16v14H4zM4 10h16M4 14.5h16M10 5v14",
  rule: "M3 12h18M7 7.5h10M7 16.5h10",
  cut: "M8.5 7a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM8.5 17a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM8 8.5L20 18M8 15.5L20 6",
  paste: "M9 3.5h6v3H9zM9 5H6.5A1.5 1.5 0 0 0 5 6.5v13A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5v-13A1.5 1.5 0 0 0 17.5 5H15",
  selectAll: "M4 7V4h3M10 4h4M17 4h3v3M20 10v4M20 17v3h-3M14 20h-4M7 20H4v-3M4 14v-4M8.5 8.5h7v7h-7z",
  print: "M7 9V4h10v5M7 17H5a1.5 1.5 0 0 1-1.5-1.5v-5A1.5 1.5 0 0 1 5 9h14a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 19 17h-2M7 14h10v6H7z",
  save: "M5 4h11l3 3v13H5zM8 4v5h7V4M8 20v-6h8v6",
  history: "M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4M12 8v4.5l3 2",
  sections: "M4 5h9M4 10h16M7 14.5h13M7 19h10",
  expand: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  collapse: "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  trash: "M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13M10 11v5.5M14 11v5.5",
  arrowUp: "M12 19V5M6 11l6-6 6 6",
  arrowDown: "M12 5v14M6 13l6 6 6-6",
  textColor: "M6.5 15.5L12 3.5l5.5 12M8.6 11h6.8",
  highlight: "M15 3.5l5 5-8.5 8.5H6.5v-5zM4 20.5h9",
  clearFormat: "M6 5h12M12.5 5l-3 14M15 15l5 5M20 15l-5 5",
  edit: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />;
}
