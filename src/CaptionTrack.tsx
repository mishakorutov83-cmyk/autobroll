import React from 'react';
import {useCurrentFrame, useVideoConfig, interpolate, Sequence} from 'remotion';
import type {Caption} from './captions';
import {TITLE_FONT, SERIF_FONT} from './Titles';

export type {Caption} from './captions';

const FONT = 'Inter, -apple-system, system-ui, sans-serif';
const ACCENT = '#FFB020';

// 'default'   — the original look (active word pops, dimmed rest).
// 'clean'     — calmer interview style: Inter, no per-word scaling, words brighten
//               as they are spoken, accents only by weight/colour/size.
// 'soft'      — delicate: lighter Inter on a frosted rounded plate, each word fades
//               and rises in as it is spoken, accents in colour.
// 'editorial' — magazine look: Inter for the text, accent words in a serif italic
//               (Playfair Display) in colour; words rise in softly as spoken.
export type CaptionPreset = 'default' | 'clean' | 'soft' | 'editorial';

// per-word reveal (0 → 1) over ~140 ms from the word's start
const reveal = (absMs: number, startMs: number) => Math.max(0, Math.min(1, (absMs - startMs + 40) / 140));

const SoftOrEditorial: React.FC<{caption: Caption; accentColor: string; absMs: number; editorial: boolean}> = ({caption, accentColor, absMs, editorial}) => {
  const base = Math.round((editorial ? 58 : 52) * (caption.scale ?? 1));
  const words = caption.words.map((w, i) => {
    const r = reveal(absMs, w.startMs);
    const accentSerif = editorial && w.accent;
    return (
      <React.Fragment key={i}>
        {i > 0 ? ' ' : null}
        <span
          style={{
            display: 'inline-block',
            fontFamily: accentSerif ? SERIF_FONT : TITLE_FONT,
            fontStyle: accentSerif ? 'italic' : 'normal',
            fontSize: accentSerif ? Math.round(base * 1.2) : w.accent ? Math.round(base * 1.04) : base,
            fontWeight: accentSerif ? 600 : w.accent ? 700 : editorial ? 600 : 500,
            letterSpacing: accentSerif ? 0 : -0.3,
            lineHeight: 1.22,
            color: w.accent ? accentColor : '#ffffff',
            opacity: 0.3 + 0.7 * r,
            transform: `translateY(${(1 - r) * 6}px)`,
            textShadow: editorial ? '0 2px 12px rgba(0,0,0,0.55), 0 0 3px rgba(0,0,0,0.35)' : '0 1px 6px rgba(0,0,0,0.35)',
          }}
        >
          {w.text}
        </span>
      </React.Fragment>
    );
  });
  // the spaces between word spans take the parent's font — keep it the caption size
  const box = {fontFamily: TITLE_FONT, fontSize: base, fontWeight: 500, lineHeight: 1.22};
  return editorial ? (
    <div style={{...box, textAlign: 'center', textWrap: 'balance', maxWidth: 880} as React.CSSProperties}>{words}</div>
  ) : (
    <div
      style={{
        ...box,
        textAlign: 'center',
        textWrap: 'balance',
        maxWidth: 880,
        background: 'rgba(14,14,18,0.42)',
        backdropFilter: 'blur(10px)',
        borderRadius: 26,
        padding: '14px 30px 16px',
      } as React.CSSProperties}
    >
      {words}
    </div>
  );
};

// один блок субтитров (внутри своего Sequence)
const CaptionPage: React.FC<{caption: Caption; accentColor: string; durationInFrames: number; preset: CaptionPreset}> = ({caption, accentColor, durationInFrames, preset}) => {
  const clean = preset === 'clean';
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const absMs = caption.startMs + (frame / fps) * 1000;
  const fontSize = Math.round((clean ? 60 : 62) * (caption.scale ?? 1));

  // soft cross-dissolve: fade in at the start, fade out near the end so a page
  // doesn't snap away the instant the last word is spoken.
  // Guarded for very short pages (1–2 frames after autocut/clip clamping) —
  // interpolate() requires strictly increasing ranges.
  const inF = Math.max(1, Math.min(Math.round(fps * 0.14), Math.floor(durationInFrames / 2)));
  const outStart = Math.max(inF + 1, durationInFrames - Math.round(fps * 0.18));
  const appear = interpolate(frame, [0, inF], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const disappear =
    outStart >= durationInFrames
      ? 1 // page too short for a fade-out
      : interpolate(frame, [outStart, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = appear * disappear;

  if (preset === 'soft' || preset === 'editorial') {
    return (
      <div style={{position: 'absolute', top: `${caption.topPct}%`, left: 0, right: 0, display: 'flex', justifyContent: 'center',
                   padding: '0 90px', opacity, transform: `translateY(${interpolate(appear, [0, 1], [8, 0])}px)`}}>
        <SoftOrEditorial caption={caption} accentColor={accentColor} absMs={absMs} editorial={preset === 'editorial'} />
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: `${caption.topPct}%`,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        padding: clean ? '0 110px' : '0 70px',
        opacity,
        transform: `translateY(${interpolate(appear, [0, 1], [10, 0])}px)`,
      }}
    >
     <div
       data-ab={`cap:${caption.id}`}
       style={clean ? {display: 'block', textAlign: 'center', textWrap: 'balance', maxWidth: 860, fontFamily: TITLE_FONT, fontSize, fontWeight: 700, lineHeight: 1.2} as React.CSSProperties : {
         display: 'flex',
         justifyContent: 'center',
         flexWrap: 'wrap',
         gap: clean ? '0 15px' : '0 16px',
         fontFamily: clean ? TITLE_FONT : FONT,
       }}
     >
      {caption.words.map((w, i) => {
        const active = absMs >= w.startMs && absMs <= w.endMs;
        if (clean) {
          const spoken = absMs >= w.startMs;
          return (
            <React.Fragment key={i}>
            {i > 0 ? ' ' : null}
            <span
              style={{
                fontSize: w.accent ? Math.round(fontSize * 1.07) : fontSize,
                fontWeight: w.accent ? 800 : 700,
                lineHeight: 1.2,
                letterSpacing: -0.4,
                color: w.accent ? accentColor : spoken ? '#ffffff' : 'rgba(255,255,255,0.62)',
                textShadow: '0 2px 10px rgba(0,0,0,0.6), 0 0 3px rgba(0,0,0,0.35)',
              }}
            >
              {w.text}
            </span>
            </React.Fragment>
          );
        }
        const color = w.accent ? accentColor : active ? '#ffffff' : 'rgba(255,255,255,0.78)';
        return (
          <span
            key={i}
            style={{
              fontSize,
              fontWeight: w.accent ? 800 : 600,
              lineHeight: 1.25,
              letterSpacing: -0.5,
              color,
              transform: active || w.accent ? 'scale(1.05)' : 'scale(1)',
              display: 'inline-block',
              textShadow: '0 2px 12px rgba(0,0,0,0.55), 0 0 26px rgba(0,0,0,0.35)',
            }}
          >
            {w.text}
          </span>
        );
      })}
     </div>
    </div>
  );
};

// каждая фраза = свой Sequence
export const CaptionTrack: React.FC<{
  captions: Caption[];
  accentColor?: string;
  preset?: CaptionPreset;
}> = ({captions, accentColor = ACCENT, preset = 'default'}) => {
  const {fps} = useVideoConfig();
  if (!captions?.length) return null;

  return (
    <>
      {captions.map((c, i) => {
        const nextStart = captions[i + 1]?.startMs ?? Infinity;
        const visEnd = Math.min(nextStart, c.endMs + 700, c.holdMaxMs ?? Infinity);
        const from = Math.round((c.startMs / 1000) * fps);
        const dur = Math.max(1, Math.round(((visEnd - c.startMs) / 1000) * fps));
        return (
          <Sequence key={c.id} from={from} durationInFrames={dur} layout="none" name={c.words.map((w) => w.text).join(' ')}>
            <CaptionPage caption={c} accentColor={accentColor} durationInFrames={dur} preset={preset} />
          </Sequence>
        );
      })}
    </>
  );
};
