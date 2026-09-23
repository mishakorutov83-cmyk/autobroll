import React, {useState} from 'react';
import {AbsoluteFill, Sequence, continueRender, delayRender, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {placeClips, type Clip} from './timeline';

// Graphic titles: a lower-third name plate and a closing end card.
// Anchored to a clip like captions/B-roll (offset from the clip's start on the
// timeline), so they move with the clip when it is reordered or trimmed.
export type TitleItem = {
  id: string;
  kind: 'lower' | 'end';
  clipId: string; // anchor clip
  offsetSec: number; // start, relative to the anchor clip's start on the timeline
  durationSec: number;
  title: string;
  subtitle?: string;
};

export const TITLE_FONT = '"AB Inter", Inter, -apple-system, system-ui, sans-serif';

// Inter (Cyrillic) shipped in public/fonts — loaded once, render waits for it.
// Falls back to system fonts if the files are not there.
const FONT_WEIGHTS = [500, 600, 700, 800];
let fontsPromise: Promise<unknown> | null = null;
const loadFonts = () => {
  if (!fontsPromise) {
    fontsPromise = Promise.all(
      FONT_WEIGHTS.map((w) => {
        const f = new FontFace('AB Inter', `url(${staticFile(`fonts/Inter-${w}.ttf`)})`, {weight: String(w)});
        return f.load().then((ff) => (document.fonts as unknown as {add: (f: FontFace) => void}).add(ff)).catch(() => null);
      }),
    );
  }
  return fontsPromise;
};

export const useTitleFonts = (enabled: boolean) => {
  useState(() => {
    if (!enabled || typeof document === 'undefined') return null;
    const handle = delayRender('Loading Inter');
    loadFonts().finally(() => continueRender(handle));
    return handle;
  });
};

export function projectTitles(items: TitleItem[], clips: Clip[], fps: number) {
  const byId = new Map(placeClips(clips, fps).map((p) => [p.clip.id, p]));
  return items.flatMap((t) => {
    const pc = byId.get(t.clipId);
    if (!pc) return [];
    return [{...t, from: pc.fromFrame + Math.round(t.offsetSec * fps), dur: Math.max(1, Math.round(t.durationSec * fps))}];
  });
}

const ease = Easing.bezier(0.22, 1, 0.36, 1);

const LowerThird: React.FC<{item: TitleItem; dur: number; accent: string}> = ({item, dur, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inP = interpolate(frame, [0, fps * 0.45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const subP = interpolate(frame, [fps * 0.15, fps * 0.6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const out = interpolate(frame, [dur - fps * 0.35, dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 84, top: '49%', opacity: out, fontFamily: TITLE_FONT}}>
      <div style={{display: 'flex', alignItems: 'stretch', gap: 22}}>
        <div style={{width: 6, borderRadius: 3, background: accent, transform: `scaleY(${inP})`, transformOrigin: 'top'}} />
        <div style={{overflow: 'hidden', padding: '4px 0'}}>
          <div
            style={{
              fontSize: 76,
              fontWeight: 800,
              letterSpacing: 3,
              color: '#fff',
              lineHeight: 1,
              transform: `translateX(${(1 - inP) * -40}px)`,
              opacity: inP,
              textShadow: '0 2px 18px rgba(0,0,0,0.45)',
            }}
          >
            {item.title}
          </div>
          {item.subtitle && (
            <div
              style={{
                marginTop: 14,
                fontSize: 34,
                fontWeight: 600,
                letterSpacing: 0.5,
                color: 'rgba(255,255,255,0.9)',
                transform: `translateX(${(1 - subP) * -30}px)`,
                opacity: subP,
                textShadow: '0 2px 14px rgba(0,0,0,0.55)',
              }}
            >
              {item.subtitle}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const EndCard: React.FC<{item: TitleItem; dur: number; accent: string}> = ({item, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const bg = interpolate(frame, [0, fps * 0.5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const t = interpolate(frame, [fps * 0.2, fps * 0.8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const s = interpolate(frame, [fps * 0.45, fps * 1.05], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return (
    <AbsoluteFill style={{fontFamily: TITLE_FONT}}>
      <AbsoluteFill style={{backdropFilter: `blur(${bg * 22}px)`, background: `rgba(8,8,10,${bg * 0.62})`}} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 140}}>
        <div
          style={{
            fontSize: 88,
            fontWeight: 800,
            letterSpacing: 4,
            lineHeight: 1.08,
            color: '#fff',
            textAlign: 'center',
            whiteSpace: 'pre-line',
            opacity: t,
            transform: `translateY(${(1 - t) * 24}px)`,
          }}
        >
          {item.title}
        </div>
        <div style={{width: 120 * t, height: 5, borderRadius: 3, background: accent, margin: '38px 0 34px'}} />
        {item.subtitle && (
          <div style={{fontSize: 40, fontWeight: 500, color: 'rgba(255,255,255,0.88)', opacity: s, transform: `translateY(${(1 - s) * 14}px)`}}>
            {item.subtitle}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const TitleLayer: React.FC<{items: Array<TitleItem & {from: number; dur: number}>; accentColor: string}> = ({items, accentColor}) => (
  <>
    {items.map((it) => (
      <Sequence key={it.id} from={it.from} durationInFrames={it.dur} name={`title:${it.title}`}>
        {it.kind === 'end' ? <EndCard item={it} dur={it.dur} accent={accentColor} /> : <LowerThird item={it} dur={it.dur} accent={accentColor} />}
      </Sequence>
    ))}
  </>
);
