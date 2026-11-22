import React from 'react';
import {Series} from 'remotion';
import {COPY} from './copy';
import {Card, CARD_FRAMES, Intro, INTRO_FRAMES, Outro, OUTRO_FRAMES} from './scenes/Cards';
import {Discord, DISCORD_FRAMES} from './scenes/Discord';
import {Extension, EXTENSION_FRAMES} from './scenes/Extension';
import {Web, WEB_FRAMES} from './scenes/Web';

const PARTS: [React.ReactNode, number][] = [
  [<Intro />, INTRO_FRAMES],
  [<Card {...COPY.web.card} />, CARD_FRAMES],
  [<Web />, WEB_FRAMES],
  [<Card {...COPY.discord.card} />, CARD_FRAMES],
  [<Discord />, DISCORD_FRAMES],
  [<Card {...COPY.extension.card} />, CARD_FRAMES],
  [<Extension />, EXTENSION_FRAMES],
  [<Outro />, OUTRO_FRAMES],
];
export const DEMO_FRAMES = PARTS.reduce((n, [, frames]) => n + frames, 0);
/** First frame of each part — handy for stills and for jumping around in the studio. */
export const PART_STARTS = PARTS.map((_, i) => PARTS.slice(0, i).reduce((n, [, frames]) => n + frames, 0));

export const Demo: React.FC = () => (
  <Series>
    {PARTS.map(([node, frames], i) => (
      <Series.Sequence key={i} durationInFrames={frames}>{node}</Series.Sequence>
    ))}
  </Series>
);
