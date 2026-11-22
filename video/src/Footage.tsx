// A recording inside a Macintosh window: the clips of the timeline, a camera that zooms within the
// window, the cursor redrawn from the log, and outlines around what a caption talks about.
import React from 'react';
import {Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Video} from '@remotion/media';
import {cameraAt, cursorTrack, type Capture, type Rect, type Shot, type Timeline} from './capture';
import {MacWindow} from './chrome';
import {C, FPS, PIXEL, WIN, onTwos} from './theme';

export type Outline = {from: number; to: number; rect: Rect};

const Cursor: React.FC<{x: number; y: number; zoom: number; since: number}> = ({x, y, zoom, since}) => {
  // stays roughly the same size on screen however far the camera is in
  const size = 1.5 / Math.pow(zoom, 0.55);
  const press = since < 0.13 ? 0.8 : 1;
  const ring = since >= 0 && since < 0.36 ? Math.floor(since / 0.06) : -1;  // stepped, not eased
  return (
    <>
      {ring >= 0 ? (
        <div style={{position: 'absolute', left: x - (8 + ring * 5) / zoom, top: y - (8 + ring * 5) / zoom,
          width: (16 + ring * 10) / zoom, height: (16 + ring * 10) / zoom, boxSizing: 'border-box',
          border: `${2.5 / zoom}px solid ${C.cobalt}`, opacity: ring > 4 ? 0.5 : 1}} />
      ) : null}
      <svg width={20} height={30} viewBox="0 0 13 20" style={{position: 'absolute', left: x, top: y, overflow: 'visible',
        transform: `scale(${size * press})`, transformOrigin: '0 0', shapeRendering: 'crispEdges'}}>
        <path d="M1 1 L1 15 L4.5 11.8 L7 17.6 L9.4 16.6 L6.9 10.9 L11.6 10.9 Z" fill={C.ink} stroke="#fff" strokeWidth={1.3} strokeLinejoin="miter" />
      </svg>
    </>
  );
};

/** "Marching ants": the selection outline of the classic desktop. */
const Ants: React.FC<{rect: Rect; zoom: number; frame: number}> = ({rect, zoom, frame}) => {
  const pad = 5 / zoom, sw = 3 / zoom, dash = 9 / zoom;
  return (
    <svg style={{position: 'absolute', left: rect.x - pad, top: rect.y - pad, overflow: 'visible'}} width={rect.w + pad * 2} height={rect.h + pad * 2}>
      <rect x={0} y={0} width={rect.w + pad * 2} height={rect.h + pad * 2} fill="none" stroke="#fff" strokeWidth={sw} />
      <rect x={0} y={0} width={rect.w + pad * 2} height={rect.h + pad * 2} fill="none" stroke={C.cobalt} strokeWidth={sw}
        strokeDasharray={`${dash} ${dash}`} strokeDashoffset={-(onTwos(frame) / 2) * (dash / 4)} />
    </svg>
  );
};

/** Opacity of the dip across a soft cut: up over the last frames before it, down over the first after it. */
const DIP_OUT = 14, DIP_IN = 18;
function dipAt(f: number, tl: Timeline): number {
  let o = 0;
  for (const c of tl.clips) {
    if (!c.soft) continue;
    const d = onTwos(f) - c.start;
    if (d >= -DIP_OUT && d < 0) o = Math.max(o, (d + DIP_OUT + 1) / DIP_OUT);
    else if (d >= 0 && d < DIP_IN) o = Math.max(o, 1 - d / DIP_IN);
  }
  return Math.min(1, o);
}

export const Footage: React.FC<{
  capture: Capture; tl: Timeline; shots: Shot[]; title: string; right?: string; outlines?: Outline[];
  /** Label for a cut that skips waiting, given the seconds skipped. */
  skipLabel?: (seconds: number) => string;
  cursor?: boolean;
}> = ({capture, tl, shots, title, right, outlines = [], skipLabel, cursor = true}) => {
  const f = useCurrentFrame();
  const {width: vw, height: vh} = capture.view;
  const k = WIN.contentW / vw;
  const cam = cameraAt(f, shots, tl, vw, vh);
  const s = k * cam.z;
  const tx = Math.round(WIN.contentW / 2 - cam.cx * s), ty = Math.round(WIN.contentH / 2 - cam.cy * s);
  const t = tl.srcAt(f);
  const track = React.useMemo(() => cursorTrack(capture), [capture]);
  const pos = cursor ? track.posAt(t) : null;
  const win = {x: WIN.x, y: WIN.y, w: WIN.contentW + WIN.border * 2, h: WIN.contentH + WIN.bar + WIN.border * 2};
  const cut = tl.clips.find(c => c.skipped > 0.8 && f >= c.start && f < c.start + 2.2 * FPS);
  const dip = dipAt(f, tl);
  return (
    <MacWindow rect={win} title={title} right={right} bar={WIN.bar} body={{background: '#000'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: vw, height: vh, transformOrigin: '0 0',
        transform: `translate(${tx}px, ${ty}px) scale(${s})`}}>
        {tl.clips.map((c, i) => (
          <Sequence key={i} from={c.start} durationInFrames={c.frames} premountFor={FPS}>
            <Video src={staticFile(capture.video)} muted trimBefore={Math.round(c.from * FPS)} playbackRate={c.speed}
              style={{position: 'absolute', left: 0, top: 0, width: vw, height: vh}} />
          </Sequence>
        ))}
        {outlines.filter(o => f >= tl.frameOf(o.from) && f < tl.frameOf(o.to)).map((o, i) => (
          <Ants key={i} rect={o.rect} zoom={s} frame={f} />
        ))}
        {pos ? <Cursor x={pos.x} y={pos.y} zoom={cam.z} since={track.sinceClick(t)} /> : null}
      </div>
      {dip > 0 ? <div style={{position: 'absolute', inset: 0, background: C.paper, opacity: dip}} /> : null}
      {cut && skipLabel ? (
        <div style={{position: 'absolute', right: 18, top: 18, padding: '8px 16px', background: C.ink, color: C.paper,
          font: `22px ${PIXEL}`, boxShadow: `5px 5px 0 ${C.cobalt}`}}>
          {skipLabel(cut.skipped)}
        </div>
      ) : null}
    </MacWindow>
  );
};
