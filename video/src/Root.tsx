import React from 'react';
import {Composition, staticFile} from 'remotion';
import {loadFont} from '@remotion/fonts';
import {Demo, DEMO_FRAMES} from './Demo';
import {FPS, H, W} from './theme';

// The application's display font; the body font is the system one, exactly as in the recorded pages.
loadFont({family: 'Geist Pixel', url: staticFile('fonts/GeistPixel-Square.woff2'), weight: '400'});

export const Root: React.FC = () => (
  <Composition id="Demo" component={Demo} durationInFrames={DEMO_FRAMES} fps={FPS} width={W} height={H} />
);
