// The parts of the video that are not footage: opening, section cards, closing.
import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {MacWindow, Paper, Typed, ZoomOpen} from '../chrome';
import {COPY} from '../copy';
import {BODY, C, FPS, H, PIXEL, W, onTwos} from '../theme';

export const INTRO_FRAMES = Math.round(5.2 * FPS);
export const CARD_FRAMES = Math.round(3.2 * FPS);
export const OUTRO_FRAMES = Math.round(5.5 * FPS);

/** Appears at a frame, without easing — like a system drawing a control. */
const After: React.FC<{frame: number; children: React.ReactNode}> = ({frame, children}) =>
  onTwos(useCurrentFrame()) >= frame ? <>{children}</> : null;

export const Intro: React.FC = () => {
  const f = useCurrentFrame();
  // the artwork resolves in coarse steps, as a dithered image loading
  const reveal = Math.min(1, Math.floor((f / (0.9 * FPS)) * 8) / 8);
  return (
    <Paper>
      <Img src={staticFile('hero-dither.png')} style={{position: 'absolute', right: -190, top: 20, width: 1500, mixBlendMode: 'multiply',
        clipPath: `inset(0 0 ${(1 - reveal) * 100}% 0)`,
        WebkitMaskImage: 'linear-gradient(to right, transparent 0%, #000 30%)', maskImage: 'linear-gradient(to right, transparent 0%, #000 30%)'}} />
      <div style={{position: 'absolute', left: 130, top: 250, width: 1100}}>
        <div style={{font: `26px ${PIXEL}`, color: C.muted, letterSpacing: '0.04em', marginBottom: 18}}>
          <After frame={6}>HackNation 2026 · wyzwanie MSZ</After>&nbsp;
        </div>
        <div style={{font: `168px/1 ${PIXEL}`, color: C.cobalt, letterSpacing: '-0.035em', whiteSpace: 'nowrap'}}>
          <Typed text={COPY.brand} start={10} cps={16} color={C.cobalt} />
        </div>
        <After frame={62}>
          <div style={{fontSize: 46, letterSpacing: '-0.02em', marginTop: 30}}>{COPY.intro.lead}</div>
        </After>
        <After frame={92}>
          <div style={{fontSize: 30, color: C.muted, marginTop: 16}}>{COPY.intro.sub}</div>
        </After>
        <div style={{display: 'flex', gap: 22, marginTop: 54}}>
          {COPY.intro.channels.map((name, i) => (
            <After key={name} frame={120 + i * 14}>
              <div style={{display: 'flex', alignItems: 'center', gap: 14, padding: '14px 24px', background: i === 0 ? C.cobalt : C.paper,
                color: i === 0 ? '#fff' : C.ink, border: `3px solid ${C.ink}`, boxShadow: `6px 6px 0 ${C.ink}`, font: `28px ${PIXEL}`}}>
                <span style={{fontSize: 22, opacity: 0.8}}>0{i + 1}</span>{name}
              </div>
            </After>
          ))}
        </div>
      </div>
    </Paper>
  );
};

export const Card: React.FC<{no: string; title: string; sub: string}> = ({no, title, sub}) => {
  const rect = {x: (W - 1180) / 2, y: (H - 470) / 2, w: 1180, h: 470};
  return (
    <Paper>
      <ZoomOpen to={rect} frames={22}>
        <MacWindow rect={rect} title={`Prawdowid · ${no} / 03`} blue>
          <div style={{display: 'flex', alignItems: 'center', gap: 48, padding: '0 64px', height: '100%'}}>
            <div style={{width: 190, height: 190, border: `4px solid ${C.cobalt}`, color: C.cobalt, display: 'grid', placeItems: 'center',
              font: `118px/1 ${PIXEL}`, flexShrink: 0}}>{no}</div>
            <div>
              <div style={{font: `104px/1.05 ${PIXEL}`, color: C.cobalt, letterSpacing: '-0.03em'}}>
                <Typed text={title} start={26} cps={18} caret={false} />&nbsp;
              </div>
              <After frame={78}><div style={{fontSize: 36, marginTop: 22, letterSpacing: '-0.015em', fontFamily: BODY}}>{sub}</div></After>
            </div>
          </div>
        </MacWindow>
      </ZoomOpen>
    </Paper>
  );
};

export const Outro: React.FC = () => {
  const rect = {x: 1010, y: 250, w: 780, h: 470};
  const O = COPY.outro;
  return (
    <Paper>
      <div style={{position: 'absolute', left: 130, top: 270, width: 820}}>
        <div style={{font: `26px ${PIXEL}`, color: C.muted, letterSpacing: '0.04em', marginBottom: 20}}>{COPY.brand}</div>
        <div style={{font: `84px/1.12 ${PIXEL}`, color: C.cobalt, letterSpacing: '-0.035em', whiteSpace: 'nowrap'}}>
          <Typed text={O.title} start={8} cps={22} caret={false} /><br />
          <Typed text={O.title2} start={8 + Math.round((O.title.length / 22) * FPS)} cps={22} caret={false} />&nbsp;
        </div>
        <After frame={150}>
          <div style={{display: 'flex', gap: 14, alignItems: 'center', background: C.sage, padding: '16px 20px', marginTop: 44, fontSize: 25, lineHeight: 1.4}}>
            <span style={{font: `700 40px/1 ui-monospace, monospace`}}>?</span>{O.note}
          </div>
        </After>
      </div>
      <AbsoluteFill>
        <ZoomOpen to={rect} frames={14} from={{x: 950, y: 500}}>
          <MacWindow rect={rect} title="Gdzie działa Prawdowid?" bar={46}>
            {O.rows.map(([name, what], i) => (
              <After key={name} frame={70 + i * 22}>
                <div style={{display: 'flex', alignItems: 'center', gap: 26, padding: '0 32px', height: 141, boxSizing: 'border-box',
                  borderBottom: i < 2 ? `2px solid ${C.line}` : 'none'}}>
                  <span style={{font: `44px ${PIXEL}`, color: C.cobalt, width: 70}}>0{i + 1}</span>
                  <span>
                    <span style={{display: 'block', font: `40px ${PIXEL}`}}>{name}</span>
                    <span style={{display: 'block', fontSize: 24, color: C.muted, marginTop: 6}}>{what}</span>
                  </span>
                </div>
              </After>
            ))}
          </MacWindow>
        </ZoomOpen>
      </AbsoluteFill>
    </Paper>
  );
};
