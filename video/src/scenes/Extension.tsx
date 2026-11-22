import React from 'react';
import extJson from '../../public/captures/extension.json';
import {at, clickAt, cutting, part, rectOf, timeline, type Capture, type Shot} from '../capture';
import {Captions, Paper, ZoomOpen} from '../chrome';
import {COPY} from '../copy';
import {Footage} from '../Footage';
import {WIN} from '../theme';

const cap = extJson as unknown as Capture;
const T = COPY.extension;

const loaded = at(cap, 'feed-loaded'), badge = at(cap, 'badge-first'), top = at(cap, 'badges-top');
const scroll1 = at(cap, 'scrolled', 0), middle = at(cap, 'feed-middle'), scroll2 = at(cap, 'scrolled', 1), bottom = at(cap, 'feed-bottom');
const fab = at(cap, 'fab'), fabClick = clickAt(cap, 0), picker = at(cap, 'picker'), target = at(cap, 'pick-target');
const loading = at(cap, 'sheet-loading'), result = at(cap, 'sheet-result'), details = at(cap, 'sheet-details'), quotes = at(cap, 'sheet-quotes');
const sheet = rectOf(cap, 'sheet-result');

// The page scan and the check are real waits and play at true speed; only long idle stretches are cut.
const tl = timeline(cutting(loaded + 0.15, cap.duration - 0.3, [
  {from: loaded + 1.6, to: badge - 0.5, wait: true},
  {from: scroll1 + 0.6, to: middle - 0.4, wait: true},
  {from: scroll2 + 0.6, to: bottom - 0.4, wait: true},
], 1.5));
export const EXTENSION_FRAMES = tl.frames;

const shots: Shot[] = [
  {t: 0},
  {t: top + 0.3, rect: rectOf(cap, 'post-first'), maxZoom: 1.85, pad: 0.2},
  {t: scroll1 - 1.6, rect: {x: 166, y: 80, w: 948, h: 533}, maxZoom: 1.35, pad: 0},
  {t: fab - 0.5},
  {t: fab + 0.1, rect: part(rectOf(cap, 'fab'), -2.2, -3.2, 1.1, 1.2), maxZoom: 1.7, pad: 0},
  {t: picker + 0.3, rect: {x: 250, y: 300, w: 800, h: 420}, maxZoom: 1.45, pad: 0},
  {t: loading + 0.15, rect: rectOf(cap, 'sheet-loading'), maxZoom: 1.6, pad: 0.12},
  {t: result + 0.3, rect: part(sheet, 0, 0, 1, 0.72), maxZoom: 1.7, pad: 0.06},
  {t: details + 0.1, rect: part(rectOf(cap, 'sheet-details'), 0, 0.22, 1, 0.98), maxZoom: 1.6, pad: 0.05},
];

const f = tl.frameOf;
const lines = [
  {from: f(loaded + 0.2), to: f(top + 0.3), text: T.scan},
  {from: f(top + 0.3), to: f(scroll1 - 1.6), text: T.badge},
  {from: f(scroll1 - 1.6), to: f(middle - 0.5), text: T.neutral},
  {from: f(middle - 0.5), to: f(fab), text: T.more},
  {from: f(fab), to: f(target - 0.3), text: T.fab},
  {from: f(target - 0.3), to: f(result), text: T.pick},
  {from: f(result + 0.2), to: f(details - 0.4), text: T.sheet},
  {from: f(details - 0.4), to: tl.frames, text: T.details},
];

const outlines = [
  {from: top + 0.9, to: scroll1 - 1.6, rect: rectOf(cap, 'badges-top')},
  {from: fab + 0.5, to: fabClick, rect: rectOf(cap, 'fab')},
  {from: result + 0.9, to: details - 0.6, rect: rectOf(cap, 'sheet-sources')},
];
void quotes;

export const Extension: React.FC = () => (
  <Paper>
    <ZoomOpen to={{x: WIN.x, y: WIN.y, w: WIN.contentW, h: WIN.contentH + WIN.bar}}>
      <Footage capture={cap} tl={tl} shots={shots} outlines={outlines} title={T.window} skipLabel={COPY.skipped} right={new URL(cap.base ?? 'http://localhost:8000').host + '/demo/feed.html'} />
      <Captions lines={lines} tag={T.tag} />
    </ZoomOpen>
  </Paper>
);
