// The Nexora logo. Artwork (and the original file) lives in /brand; the web copies are in /public.
// The wordmark has a Night-mode variant whose navy letters are lightened to stay readable.

export const PRODUCT_NAME = "Nexora";
export const PRODUCT_DESCRIPTOR = "AI solution architecture advisor";

/** The N mark (square image). */
export function NexoraMark({ size = 32 }: { size?: number }) {
  return <img className="brand-mark" src="/nexora-mark.png" width={size} height={size} alt="" />;
}

/** The "Nexora" wordmark; CSS shows the artwork that matches the Normal/Night mode. */
export function Wordmark({ height = 24 }: { height?: number }) {
  return (
    <span className="wordmark" role="img" aria-label={PRODUCT_NAME}>
      <img className="wordmark-light" src="/nexora-wordmark.png" alt="" style={{ height, width: "auto" }} />
      <img className="wordmark-dark" src="/nexora-wordmark-dark.png" alt="" style={{ height, width: "auto" }} />
    </span>
  );
}

/** Mark + wordmark (+ descriptor), as in the app header. */
export function BrandLockup({ descriptor = true }: { descriptor?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-tile"><NexoraMark size={26} /></span>
      <span className="brand-text">
        <Wordmark height={20} />
        {descriptor && <span className="brand-descriptor">{PRODUCT_DESCRIPTOR}</span>}
      </span>
    </span>
  );
}
