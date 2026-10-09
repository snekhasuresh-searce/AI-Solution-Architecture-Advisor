// The Nexora logo. Artwork (and the original file) lives in /brand; the web copies are in /public.
// The wordmark has a dark-theme variant whose navy letters are lightened to stay readable.

export const PRODUCT_NAME = "Nexora";
export const PRODUCT_DESCRIPTOR = "AI solution architecture advisor";

/** The N mark (square image). */
export function NexoraMark({ size = 32 }: { size?: number }) {
  return <img className="brand-mark" src="/nexora-mark.png" width={size} height={size} alt="" />;
}

/** The "Nexora" wordmark; switches to the dark-theme artwork with the colour scheme. */
export function Wordmark({ height = 24 }: { height?: number }) {
  return (
    <picture className="wordmark">
      <source srcSet="/nexora-wordmark-dark.png" media="(prefers-color-scheme: dark)" />
      <img src="/nexora-wordmark.png" alt={PRODUCT_NAME} style={{ height, width: "auto" }} />
    </picture>
  );
}

/** Mark + wordmark (+ descriptor), as in the app header. */
export function BrandLockup({ descriptor = true }: { descriptor?: boolean }) {
  return (
    <span className="brand">
      <NexoraMark size={34} />
      <Wordmark height={22} />
      {descriptor && <span className="brand-descriptor">{PRODUCT_DESCRIPTOR}</span>}
    </span>
  );
}
