// Stage furniture in the application's style: paper, Macintosh windows, captions. None of it is footage.
import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {BODY, C, CAPTION, FPS, H, PIXEL, W, onTwos} from './theme';
import type {Rect} from './capture';

export const Paper: React.FC<{children?: React.ReactNode}> = ({children}) => (
  <AbsoluteFill style={{
    backgroundColor: C.paper,
    backgroundImage: 'radial-gradient(#ccc9bb 1.3px, transparent 1.6px), radial-gradient(#dbd8cc 1.2px, transparent 1.6px)',
    backgroundSize: '12px 12px', backgroundPosition: '0 0, 6px 6px', fontFamily: BODY, color: C.ink,
  }}>{children}</AbsoluteFill>
);

const stripes = (color: string) => `repeating-linear-gradient(to bottom, ${color} 0 2px, transparent 2px 6px)`;

export const TitleBar: React.FC<{title: string; right?: string; accented?: boolean; height?: number; size?: number}> =
  ({title, right, accented, height = 46, size = 22}) => {
    const fg = accented ? '#fff' : C.ink;
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', gap: 14, padding: '0 14px', boxSizing: 'border-box',
        background: accented ? C.brand : C.paper, color: fg, borderBottom: `3px solid ${C.ink}`, font: `${size}px ${PIXEL}`,
      }}>
        <span style={{width: 16, height: 16, border: `3px solid ${fg}`, flexShrink: 0}} />
        <span style={{whiteSpace: 'nowrap'}}>{title}</span>
        <span style={{flex: 1, height: 22, background: stripes(fg), minWidth: 20}} />
        {right ? <span style={{whiteSpace: 'nowrap', fontSize: size - 4}}>{right}</span> : null}
        <span style={{width: 16, height: 16, border: `3px solid ${fg}`, flexShrink: 0}} />
      </div>
    );
  };

export const MacWindow: React.FC<{
  rect: Rect; title: string; right?: string; accented?: boolean; children?: React.ReactNode; bar?: number; body?: React.CSSProperties;
}> = ({rect, title, right, accented, children, bar = 46, body}) => (
  <div style={{
    position: 'absolute', left: rect.x, top: rect.y, width: rect.w, height: rect.h, boxSizing: 'border-box',
    background: C.paper, border: `3px solid ${C.ink}`, boxShadow: `8px 8px 0 ${C.ink}`, display: 'flex', flexDirection: 'column',
  }}>
    <TitleBar title={title} right={right} accented={accented} height={bar} />
    <div style={{flex: 1, position: 'relative', overflow: 'hidden', ...body}}>{children}</div>
  </div>
);

/**
 * The System-7 way of opening a window: outline rectangles step from a point to the window's frame,
 * then the window is simply there. `children` appear once the last rectangle has landed.
 */
export const ZoomOpen: React.FC<{to: Rect; from?: {x: number; y: number}; children: React.ReactNode; frames?: number}> =
  ({to, from = {x: W / 2, y: H / 2}, children, frames = 24}) => {
    const f = onTwos(useCurrentFrame());
    if (f >= frames) return <>{children}</>;
    const steps = 5, lead = (f / frames) * (steps + 2);
    const rects = [];
    for (let i = 0; i < steps; i++) {
      const p = (lead - i) / steps;
      if (p <= 0 || p > 1) continue;
      rects.push({x: from.x + (to.x - from.x) * p, y: from.y + (to.y - from.y) * p, w: to.w * p, h: to.h * p});
    }
    return (
      <AbsoluteFill>
        {rects.map((r, i) => (
          <div key={i} style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, boxSizing: 'border-box', border: `2px solid ${C.ink}`}} />
        ))}
      </AbsoluteFill>
    );
  };

/** Text that types itself, with the block caret of an old terminal. */
export const Typed: React.FC<{text: string; start?: number; cps?: number; caret?: boolean; color?: string}> =
  ({text, start = 0, cps = 38, caret = true, color}) => {
    const f = useCurrentFrame() - start;
    const n = Math.max(0, Math.min(text.length, Math.floor((f / FPS) * cps)));
    const blink = Math.floor(f / (FPS / 2)) % 2 === 0;
    return (
      <span>
        {text.slice(0, n)}
        {caret ? <span style={{display: 'inline-block', width: '0.55em', height: '0.9em', marginLeft: '0.08em', verticalAlign: '-0.08em',
          background: n < text.length || blink ? (color ?? 'currentColor') : 'transparent'}} /> : null}
      </span>
    );
  };

export type Line = {from: number; to: number; text: string};

/** One caption at a time under the window; frames are relative to the scene. */
export const Captions: React.FC<{lines: Line[]; tag: string}> = ({lines, tag}) => {
  const f = useCurrentFrame();
  const line = lines.find(l => f >= l.from && f < l.to);
  return (
    <div style={{
      position: 'absolute', left: CAPTION.x, top: CAPTION.y, width: CAPTION.w, height: CAPTION.h, boxSizing: 'border-box',
      background: C.paper, border: `3px solid ${C.ink}`, boxShadow: `8px 8px 0 ${C.ink}`, display: 'flex', alignItems: 'center',
    }}>
      <div style={{alignSelf: 'stretch', display: 'flex', alignItems: 'center', padding: '0 22px', background: C.brand, color: '#fff',
        font: `24px ${PIXEL}`, borderRight: `3px solid ${C.ink}`, whiteSpace: 'nowrap'}}>{tag}</div>
      <div style={{flex: 1, padding: '0 26px', font: `31px ${PIXEL}`, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden'}}>
        {line ? <Typed key={line.from} text={line.text} start={line.from} cps={46} /> : null}
      </div>
    </div>
  );
};
