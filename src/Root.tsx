import React from 'react';
import {Composition, staticFile} from 'remotion';
import {MultiClipVideo} from './MultiClipVideo';
import {totalDurationFrames} from './timeline';
import {PromoAd, type PromoProps} from './promo/PromoAd';

// The editor renders MultiClipVideo via @remotion/player; this composition is
// what `remotion render` exports. Props come straight from the editor on export;
// in Studio they fall back to the files on disk.
export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="MultiClip"
      component={MultiClipVideo}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{clips: [], music: null, captions: [], brolls: [], accentColor: '#FFB020', captionPreset: 'default', titles: []}}
      calculateMetadata={async ({props}) => {
        const fps = 30;
        const p = props as {clips?: unknown; music?: unknown; captions?: unknown; brolls?: unknown};
        const tl =
          Array.isArray(p.clips) && p.clips.length
            ? {clips: p.clips, music: p.music ?? null}
            : await fetch(staticFile('timeline.json')).then((r) => r.json()).catch(() => ({clips: [], music: null}));
        const captions =
          Array.isArray(p.captions) && p.captions.length
            ? p.captions
            : await fetch(staticFile('captions.multi.json')).then((r) => r.json()).catch(() => []);
        const brolls =
          Array.isArray(p.brolls) && p.brolls.length
            ? p.brolls
            : await fetch(staticFile('broll.json')).then((r) => r.json()).catch(() => []);
        const arr = (v: unknown) => (Array.isArray(v) ? v : []);
        return {
          fps,
          width: 1080,
          height: 1920,
          durationInFrames: totalDurationFrames(tl.clips, fps),
          props: {...props, clips: arr(tl.clips), music: tl.music ?? null, captions: arr(captions), brolls: arr(brolls)},
        };
      }}
    />
    {/* Restaurant promo ads — separate preset (scripts/promo/, promos/<id>/spec.py) */}
    <Composition
      id="Promo"
      component={PromoAd}
      durationInFrames={450}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{fps: 30, durationSec: 15, window: {x: 28, y: 212, w: 1024, h: 1016, radius: 44}, clips: [], audio: null, fadeOut: 0.45, frame: null} as PromoProps}
      calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)), fps: props.fps})}
    />
    </>
  );
};
