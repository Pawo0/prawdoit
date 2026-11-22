// The application's own visual language (web/static/style.css): cream paper, cobalt, Macintosh window chrome.
export const C = {
  paper: '#f4f3eb',
  paperDeep: '#eae9e2',
  ink: '#191919',
  muted: '#55554f',
  line: '#c4c3ba',
  cobalt: '#443cf2',
  cobaltDeep: '#3027cf',
  sage: '#e3e7d5',
  false: '#a32424',
  true: '#17623b',
};
export const PIXEL = '"Geist Pixel", ui-monospace, monospace';
export const BODY = 'system-ui, "Noto Sans", "Segoe UI", sans-serif';

export const FPS = 60;
export const W = 1920;
export const H = 1080;

/** Where recorded footage sits on the stage. The content area keeps the recording's 16:9 shape. */
export const WIN = {x: 190, y: 34, bar: 46, border: 3, contentW: 1536, contentH: 864};
export const CAPTION = {x: 190, y: 968, w: 1542, h: 80};

/** Screen-recording zoom: reaches 90% in about 0.3 s and settles without overshoot (the Cap defaults). */
export const ZOOM_SPRING = {stiffness: 205, damping: 33.3, mass: 1.5};

/** Retro chrome moves "on twos"; footage, camera and cursor stay smooth. */
export const onTwos = (frame: number) => Math.floor(frame / 2) * 2;
