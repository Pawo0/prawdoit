import React from 'react';
import webJson from '../../public/captures/web.json';
import {at, clickAt, cutting, part, rectOf, timeline, union, type Capture, type Shot} from '../capture';
import {Captions, Paper, ZoomOpen} from '../chrome';
import {COPY} from '../copy';
import {Footage} from '../Footage';
import {WIN} from '../theme';

const cap = webJson as unknown as Capture;
const T = COPY.web;

// Moments of the recording (seconds of footage). Clicks: 0 text box, 1 "Sprawdź", 2 "Sprawdź kolejną", 3 "Sprawdź".
const focusA = clickAt(cap, 0), goA = clickAt(cap, 1), resA = at(cap, 'a-result'), evA = at(cap, 'a-evidence');
const typeB = at(cap, 'type-start', 1), goB = clickAt(cap, 3), waitB = at(cap, 'b-waiting'), resB = at(cap, 'b-result');
const srcA = at(cap, 'a-source'), unknownB = at(cap, 'b-unknown');

// Waiting for the server is shown for a moment and then cut; the cut is labelled on screen with the time skipped.
// The trip back to the form between the two checks is cut as well.
const tl = timeline(cutting(at(cap, 'home') + 0.1, cap.duration - 0.3, [
  {from: goA + 1.6, to: resA - 0.2, wait: true},
  {from: evA + 3.8, to: typeB - 0.6},
  {from: waitB + 3.0, to: resB - 0.2, wait: true},
]));
export const WEB_FRAMES = tl.frames;

const shots: Shot[] = [
  {t: 0},
  {t: focusA - 0.6, rect: rectOf(cap, 'home'), maxZoom: 1.5},
  {t: goA + 0.5},
  {t: resA - 0.2, cut: true},
  {t: resA + 0.5, rect: union(part(rectOf(cap, 'a-verdict'), 0, 0, 0.8, 1), rectOf(cap, 'a-explanation')), maxZoom: 1.6},
  {t: srcA + 2.5, rect: union(part(rectOf(cap, 'a-source'), 0, 0, 0.72, 1), rectOf(cap, 'a-source-link')), maxZoom: 1.85},
  {t: evA - 1.5},
  {t: evA + 0.25, rect: part(rectOf(cap, 'a-evidence'), 0, 0, 0.78, 1), maxZoom: 1.6},
  {t: typeB - 0.6, rect: rectOf(cap, 'b-typed'), maxZoom: 1.5, cut: true},
  {t: goB + 0.35, rect: rectOf(cap, 'b-waiting'), maxZoom: 1.35},
  {t: resB - 0.2, cut: true},
  {t: resB + 0.5, rect: union(part(rectOf(cap, 'b-verdict'), 0, 0, 0.85, 1), rectOf(cap, 'b-explanation')), maxZoom: 1.5},
  {t: unknownB + 0.1, rect: part(rectOf(cap, 'b-unknown'), 0, 0, 0.85, 1), maxZoom: 1.6},
];

const f = tl.frameOf;
const lines = [
  {from: f(focusA - 0.3), to: f(goA - 0.2), text: T.paste},
  {from: f(goA + 0.1), to: f(resA), text: T.search},
  {from: f(resA + 0.3), to: f(srcA + 2.4), text: T.verdict},
  {from: f(srcA + 2.4), to: f(evA - 1.4), text: T.source},
  {from: f(evA), to: f(typeB - 0.6) , text: T.quote},
  {from: f(typeB - 0.4), to: f(goB), text: T.second},
  {from: f(goB + 0.2), to: f(resB), text: T.live},
  {from: f(resB + 0.3), to: f(unknownB), text: T.abstain},
  {from: f(unknownB), to: tl.frames, text: T.settle},
];

const outlines = [
  {from: srcA + 2.9, to: evA - 1.5, rect: rectOf(cap, 'a-source')},
  {from: evA + 0.7, to: evA + 3.6, rect: rectOf(cap, 'a-quote')},
  {from: unknownB + 0.6, to: cap.duration, rect: rectOf(cap, 'b-unknown')},
];

export const Web: React.FC = () => (
  <Paper>
    <ZoomOpen to={{x: WIN.x, y: WIN.y, w: WIN.contentW, h: WIN.contentH + WIN.bar}}>
      <Footage capture={cap} tl={tl} shots={shots} outlines={outlines} title={T.window} right={new URL(cap.base ?? 'http://localhost:8000').host}
        skipLabel={COPY.skipped} />
      <Captions lines={lines} tag={T.tag} />
    </ZoomOpen>
  </Paper>
);
