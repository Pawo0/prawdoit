import React from 'react';
import discordJson from '../../public/captures/discord.json';
import {at, clickAt, has, part, rectOf, timeline, union, type Capture, type Shot} from '../capture';
import {Captions, Paper, ZoomOpen} from '../chrome';
import {COPY} from '../copy';
import {Footage} from '../Footage';
import {WIN} from '../theme';

const cap = discordJson as unknown as Capture;
const T = COPY.discord;

const focus = clickAt(cap, 0), list = at(cap, 'command-list'), chosen = at(cap, 'command-chosen');
const typed = at(cap, 'typed'), sent = at(cap, 'sent'), reply = at(cap, 'reply'), settled = at(cap, 'reply-settled');
const replyRect = rectOf(cap, 'reply-settled'), box = rectOf(cap, 'typed');

// One uncut take: the bot's answer arrives fast enough to be shown at its real speed.
const tl = timeline([{from: at(cap, 'channel') + 0.1, to: cap.duration - 0.2}]);
export const DISCORD_FRAMES = tl.frames;

const shots: Shot[] = [
  {t: 0},
  {t: focus - 0.5, rect: part(union(rectOf(cap, 'command-list'), rectOf(cap, 'composer')), 0, 0, 0.62, 1), maxZoom: 1.9, pad: 0.3},
  {t: chosen + 0.5, rect: part(box, 0, -0.9, 0.86, 1), maxZoom: 1.6, pad: 0.1},
  {t: sent + 0.15},
  {t: reply + 0.45, rect: part(replyRect, 0, 0, 0.8, 0.5), maxZoom: 1.6, pad: 0.08},
  {t: settled + 2.4, rect: part(replyRect, 0, 0.42, 0.9, 1), maxZoom: 1.45, pad: 0.06},
];

const f = tl.frameOf;
const lines = [
  {from: f(0.3), to: f(focus + 0.3), text: T.channel},
  {from: f(focus + 0.3), to: f(typed + 0.2), text: T.command},
  {from: f(typed + 0.2), to: f(reply), text: T.send},
  {from: f(reply + 0.2), to: f(settled + 2.4), text: T.reply(reply - sent)},
  {from: f(settled + 2.4), to: tl.frames, text: T.link},
];

const outlines = [
  // The list closes when Tab is pressed — 0.9 s after it was marked — not at `command-chosen`, which is logged later.
  {from: list + 0.2, to: has(cap, 'command-pressed') ? at(cap, 'command-pressed') - 0.05 : list + 0.8, rect: rectOf(cap, 'command-list')},
  {from: settled + 0.2, to: settled + 2.4, rect: rectOf(cap, 'reply-verdict')},
];

export const Discord: React.FC = () => (
  <Paper>
    <ZoomOpen to={{x: WIN.x, y: WIN.y, w: WIN.contentW, h: WIN.contentH + WIN.bar}}>
      <Footage capture={cap} tl={tl} shots={shots} outlines={outlines} title={T.window} right="discord.com" />
      <Captions lines={lines} tag={T.tag} />
    </ZoomOpen>
  </Paper>
);
