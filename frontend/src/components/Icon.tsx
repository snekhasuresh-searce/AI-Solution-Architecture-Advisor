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
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2.5v2m0 15v2M4.6 4.6l1.4 1.4m12 12l1.4 1.4M2.5 12h2m15 0h2M4.6 19.4L6 18M18 6l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7.5V12l3 2",
  sidebar: "M4 5h16v14H4zM9.5 5v14",
  expand: "M6 17l5-5-5-5M13 17l5-5-5-5",
  dollar: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM14.8 9.2c-.4-.8-1.4-1.4-2.8-1.4-1.6 0-2.8.8-2.8 2s1.2 1.7 2.8 2.1 2.8.9 2.8 2.1-1.2 2-2.8 2c-1.4 0-2.4-.6-2.8-1.4M12 6.3v1.5m0 8.4v1.5",
  collapse: "M11 17l-5-5 5-5M18 17l-5-5 5-5",
  bolt: "M13 3L5 13.5h6L10 21l8-10.5h-6z",
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
