import {Config} from '@remotion/cli/config';

// PNG frames: JPEG at the default quality smears the 2px window borders and the dot texture.
Config.setVideoImageFormat('png');
Config.setCodec('h264');
Config.setCrf(16);
Config.setPixelFormat('yuv420p');
Config.setColorSpace('bt709');
Config.setOverwriteOutput(true);
