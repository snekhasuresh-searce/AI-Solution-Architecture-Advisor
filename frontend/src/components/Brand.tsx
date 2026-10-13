// The Archpilot logo. Artwork (and the original file) lives in /brand; the web copies are in /public.
// The wordmark has a Night-mode variant whose navy letters are lightened to stay readable.

export const PRODUCT_NAME = "Archpilot";
export const PRODUCT_DESCRIPTOR = "AI-powered solution architecture advisor";

/** The "A" mark with the flight arrow (square image). */
export function ArchpilotMark({ size = 32 }: { size?: number }) {
  return <img className="brand-mark" src="/archpilot-mark.png" width={size} height={size} alt="" />;
}

/** The "Archpilot" wordmark; CSS shows the artwork that matches the Normal/Night mode. */
export function Wordmark({ height = 24 }: { height?: number }) {
  return (
    <span className="wordmark" role="img" aria-label={PRODUCT_NAME}>
      <img className="wordmark-light" src="/archpilot-wordmark.png" alt="" style={{ height, width: "auto" }} />
      <img className="wordmark-dark" src="/archpilot-wordmark-dark.png" alt="" style={{ height, width: "auto" }} />
    </span>
  );
}

/** Mark + wordmark (+ descriptor), as in the app header. */
export function BrandLockup({ descriptor = true }: { descriptor?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-tile"><ArchpilotMark size={30} /></span>
      <span className="brand-text">
        <Wordmark height={20} />
        {descriptor && <span className="brand-descriptor">{PRODUCT_DESCRIPTOR}</span>}
      </span>
    </span>
  );
}
