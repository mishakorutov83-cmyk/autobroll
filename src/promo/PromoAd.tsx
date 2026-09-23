import React, {useState} from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  OffthreadVideo,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

// Restaurant promo ad (separate from the interview-reel preset): a STATIC branded
// frame with live video in a big window. Props are written by scripts/promo/build.py
// from promos/<id>/spec.py — texts and colours are data, the layout lives here.

export type PromoKey = {t: number; fx: number; fy: number; zoom: number};
export type PromoClip = {src: string; start: number; dur: number; xfade: number; aspect: number; keys: PromoKey[]};
export type PromoFrame = {
  theme: {bgTop: string; bgMid: string; bgDeep: string; accent: string; ink: string; paper: string; glow: string};
  brand: {name: string; lines: string[]};
  badge: {top: string; big: string};
  headline: string;
  offer: {prefix: string; big: string; sub: string};
  terms: string[];
  features: {icon: 'mic' | 'guitar' | 'note'; title: string; sub?: string}[];
  featureAccentClip?: number;
};
export type PromoProps = {
  fps: number;
  durationSec: number;
  window: {x: number; y: number; w: number; h: number; radius: number};
  clips: PromoClip[];
  audio: string | null;
  fadeOut: number;
  frame: PromoFrame | null;
};

const SANS = '"AB Inter", Inter, system-ui, sans-serif';
const SCRIPT = '"PR GreatVibes", cursive';
const HAND = '"PR Caveat", cursive';
const FONTS: [string, string, string][] = [
  ['AB Inter', 'Inter-600.ttf', '600'],
  ['AB Inter', 'Inter-700.ttf', '700'],
  ['AB Inter', 'Inter-800.ttf', '800'],
  ['PR GreatVibes', 'GreatVibes-400.ttf', '400'],
  ['PR Caveat', 'Caveat-700.ttf', '700'],
];
let fontsPromise: Promise<unknown> | null = null;
const loadFonts = () => {
  fontsPromise ??= Promise.all(
    FONTS.map(([fam, file, w]) =>
      new FontFace(fam, `url(${staticFile(`fonts/${file}`)})`, {weight: w})
        .load()
        .then((f) => (document.fonts as unknown as {add: (f: FontFace) => void}).add(f))
        .catch(() => null),
    ),
  );
  return fontsPromise;
};
const useFonts = () =>
  useState(() => {
    if (typeof document === 'undefined') return null;
    const h = delayRender('promo fonts');
    loadFonts().finally(() => continueRender(h));
    return h;
  });

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const inOut = Easing.inOut(Easing.sin);

// keyframed framing: (fx, fy) of the source goes to the window centre, clamped to cover
const frameAt = (keys: PromoKey[], t: number) => {
  if (keys.length === 1) return keys[0];
  const ts = keys.map((k) => k.t);
  const f = (sel: (k: PromoKey) => number) => interpolate(t, ts, keys.map(sel), {...clamp, easing: inOut});
  return {t, fx: f((k) => k.fx), fy: f((k) => k.fy), zoom: f((k) => k.zoom)};
};

const ClipLayer: React.FC<{clip: PromoClip; w: number; h: number}> = ({clip, w, h}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = frameAt(clip.keys, frame / fps);
  const vw = Math.max(w * k.zoom, h / clip.aspect);
  const vh = vw * clip.aspect;
  const left = Math.min(0, Math.max(w - vw, w / 2 - k.fx * vw));
  const top = Math.min(0, Math.max(h - vh, h / 2 - k.fy * vh));
  const op = clip.xfade ? interpolate(frame, [0, clip.xfade * fps], [0, 1], clamp) : 1;
  return (
    <AbsoluteFill style={{opacity: op}}>
      <OffthreadVideo src={staticFile(clip.src)} muted style={{position: 'absolute', left, top, width: vw, height: vh}} />
    </AbsoluteFill>
  );
};

const Heart: React.FC<{size: number; color: string; stroke?: number; style?: React.CSSProperties}> = ({size, color, stroke = 5, style}) => (
  <svg width={size} height={size} viewBox="0 0 48 44" style={style}>
    <path d="M24 40 C8 28 3 20 5 12 C7 4 18 2 24 11 C30 2 41 4 43 12 C45 20 40 28 24 40 Z" fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const Icon: React.FC<{kind: string; size: number; color: string}> = ({kind, size, color}) => {
  const p = {fill: 'none', stroke: color, strokeWidth: 3.2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const};
  if (kind === 'mic')
    return (
      <svg width={size} height={size} viewBox="0 0 64 64">
        <circle cx="40" cy="20" r="12" {...p} />
        <path d="M40 8 L40 32 M28 20 L52 20" {...p} strokeWidth={1.6} opacity={0.7} />
        <path d="M31.5 28.5 L12 52 L16 56 L35.5 36.5" {...p} />
        <path d="M13 55 C9 59 6 60 4 62" {...p} />
      </svg>
    );
  if (kind === 'guitar')
    return (
      <svg width={size} height={size} viewBox="0 0 64 64">
        <path d="M34 30 L52 12 M48 8 L56 16 M50 10 L54 14" {...p} />
        <path d="M34 30 C30 26 24 27 22 31 C20 34 16 33 13 35 C6 39 7 50 13 55 C19 61 29 59 31 51 C32 47 31 44 34 42 C38 40 38 34 34 30 Z" {...p} />
        <circle cx="23" cy="44" r="3.4" {...p} />
        <path d="M17 48 L22 53" {...p} />
      </svg>
    );
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      <path d="M24 48 L24 14 L50 8 L50 42" {...p} />
      <ellipse cx="17" cy="48" rx="7" ry="5.5" {...p} />
      <ellipse cx="43" cy="42" rx="7" ry="5.5" {...p} />
    </svg>
  );
};

// fixed pink satin backdrop: soft gradients + a few blurred sheen bands (no motion)
const Backdrop: React.FC<{th: PromoFrame['theme']}> = ({th}) => (
  <AbsoluteFill>
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 60% at 50% 0%, ${th.bgTop} 0%, ${th.bgMid} 55%, ${th.bgDeep} 100%),
        linear-gradient(180deg, ${th.bgTop}, ${th.bgDeep})`,
      }}
    />
    <svg width={1080} height={1920} style={{position: 'absolute', inset: 0}}>
      <defs>
        <filter id="blur40">
          <feGaussianBlur stdDeviation="38" />
        </filter>
        <filter id="blur14">
          <feGaussianBlur stdDeviation="14" />
        </filter>
        <radialGradient id="lowGlow" cx="50%" cy="70%" r="60%">
          <stop offset="0%" stopColor={th.bgTop} stopOpacity="0.9" />
          <stop offset="100%" stopColor={th.bgTop} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect x="-100" y="1100" width="1280" height="900" fill="url(#lowGlow)" />
      <g filter="url(#blur40)" opacity="0.55">
        <path d="M-120 1380 C 200 1250, 520 1520, 1200 1330 L 1200 1420 C 600 1600, 240 1360, -120 1480 Z" fill="#ff8cc3" />
        <path d="M-120 1800 C 300 1700, 700 1900, 1200 1720 L 1200 1790 C 700 1980, 300 1790, -120 1880 Z" fill="#ff9fcd" />
        <path d="M-120 120 C 260 40, 640 220, 1200 70 L 1200 130 C 660 290, 240 110, -120 200 Z" fill="#ff7ab8" />
      </g>
      <g filter="url(#blur14)" opacity="0.35">
        <path d="M-60 1560 C 300 1480, 640 1650, 1140 1520" stroke="#ffd1e6" strokeWidth="10" fill="none" />
        <path d="M-60 60 C 320 10, 620 150, 1140 30" stroke="#ffd1e6" strokeWidth="8" fill="none" />
      </g>
    </svg>
    <AbsoluteFill style={{background: 'radial-gradient(140% 90% at 50% 50%, transparent 60%, rgba(40,0,20,0.45) 100%)'}} />
  </AbsoluteFill>
);

export const PromoAd: React.FC<PromoProps> = (props) => {
  useFonts();
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const {window: win, clips, frame: F} = props;
  const t = frame / fps;
  if (!F) return <AbsoluteFill style={{background: '#000'}} />;
  const th = F.theme;

  // the frame is complete from frame 0 (cover-safe); only 30%, a sheen and the karaoke glow move
  const pctP = interpolate(t, [0.3, 0.9], [0, 1], {...clamp, easing: ease});
  // sheen sweep over the offer strip, twice
  const sheen = (at: number) => interpolate(t, [at, at + 0.9], [-0.4, 1.4], clamp);
  const sheenX = t < 6 ? sheen(1.6) : sheen(9.6);
  // karaoke block lights up when its clip starts
  const accClip = F.featureAccentClip != null ? clips[F.featureAccentClip] : null;
  const accT = accClip ? t - accClip.start : -1;
  const acc = accClip ? interpolate(accT, [0, 0.5, 1.6, 2.6], [0, 1, 1, 0.35], clamp) : 0;
  const fadeOut = interpolate(frame, [durationInFrames - props.fadeOut * fps, durationInFrames - 1], [0, 1], clamp);

  return (
    <AbsoluteFill style={{background: th.bgDeep, fontFamily: SANS, color: '#fff'}}>
      <Backdrop th={th} />

      {/* live video window */}
      <div
        style={{
          position: 'absolute',
          left: win.x,
          top: win.y,
          width: win.w,
          height: win.h,
          borderRadius: win.radius,
          overflow: 'hidden',
          background: '#1a0610',
          boxShadow: `0 0 0 4px rgba(255,255,255,0.92), 0 0 0 10px rgba(255,160,205,0.35), 0 24px 60px rgba(60,0,25,0.55), 0 0 90px ${th.glow}66`,
        }}
      >
        {clips.map((c, i) => (
          <Sequence key={i} from={Math.round(c.start * fps)} durationInFrames={Math.round((c.dur + (clips[i + 1]?.xfade ?? 0)) * fps) + 1} layout="none">
            <ClipLayer clip={c} w={win.w} h={win.h} />
          </Sequence>
        ))}
        {/* soft pink fade at the bottom so the headline sits on the video cleanly */}
        <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(0,0,0,0.18) 0%, transparent 16%, transparent 78%, ${th.bgMid}cc 100%)`}} />
      </div>

      {/* brand */}
      <div style={{position: 'absolute', left: 40, top: 22, width: 620, textAlign: 'center'}}>
        <div style={{fontFamily: SCRIPT, fontSize: 112, lineHeight: 1.02, textShadow: '0 4px 18px rgba(80,0,35,0.45)'}}>{F.brand.name}</div>
        {F.brand.lines.map((l) => (
          <div key={l} style={{fontSize: 25, fontWeight: 600, letterSpacing: 6, lineHeight: 1.35, opacity: 0.95}}>
            {l}
          </div>
        ))}
      </div>

      {/* date badge — overlaps the window corner, over the ceiling/windows, not the faces */}
      <div
        style={{
          position: 'absolute',
          right: 30,
          top: 34,
          width: 356,
          padding: '18px 0 14px',
          background: th.paper,
          borderRadius: 26,
          textAlign: 'center',
          color: th.ink,
          boxShadow: '0 14px 36px rgba(70,0,30,0.45)',
          transform: 'rotate(-3deg)',
        }}
      >
        <div style={{fontSize: 30, fontWeight: 800, letterSpacing: 1.5, color: '#3a0a22'}}>{F.badge.top}</div>
        <div style={{fontSize: 98, fontWeight: 800, lineHeight: 1, letterSpacing: -2, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6}}>
          {F.badge.big}
          <Heart size={44} color={th.ink} stroke={5.5} style={{marginTop: 6, flexShrink: 0}} />
        </div>
      </div>

      {/* headline straddles the bottom edge of the window */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          width: 1080,
          top: win.y + win.h - 122,
          textAlign: 'center',
          fontFamily: HAND,
          fontSize: 206,
          lineHeight: 1,
          letterSpacing: 2,
          textShadow: `0 6px 0 ${th.ink}, 0 10px 30px rgba(70,0,30,0.6), 0 0 44px ${th.glow}aa`,
          transform: 'rotate(-3deg)',
        }}
      >
        {F.headline}
      </div>

      {/* offer strip */}
      <div style={{position: 'absolute', left: 90, width: 900, top: win.y + win.h + 100}}>
        <div
          style={{
            position: 'relative',
            background: th.paper,
            transform: 'rotate(-1.5deg)',
            borderRadius: '18px 40px 22px 44px / 30px 18px 36px 20px',
            padding: '4px 0 12px',
            textAlign: 'center',
            overflow: 'hidden',
            boxShadow: '0 16px 40px rgba(70,0,30,0.45)',
          }}
        >
          <div style={{display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: 22, color: th.ink}}>
            <span style={{fontSize: 76, fontWeight: 800, letterSpacing: 1}}>{F.offer.prefix}</span>
            <span
              style={{
                fontSize: 150,
                fontWeight: 800,
                lineHeight: 1.02,
                letterSpacing: -4,
                display: 'inline-block',
                transform: `scale(${1.1 - 0.1 * pctP})`,
                opacity: 0.35 + 0.65 * pctP,
              }}
            >
              {F.offer.big}
            </span>
          </div>
          <div style={{fontSize: 40, fontWeight: 800, color: '#2d0718', letterSpacing: 2, marginTop: -8}}>{F.offer.sub}</div>
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              width: 180,
              left: `${sheenX * 100}%`,
              transform: 'skewX(-20deg)',
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.75), transparent)',
            }}
          />
        </div>
      </div>

      {/* terms */}
      <div style={{position: 'absolute', left: 0, width: 1080, top: win.y + win.h + 346, textAlign: 'center'}}>
        <div style={{fontSize: 33, fontWeight: 800, letterSpacing: 1.5}}>{F.terms[0]}</div>
        {F.terms.slice(1).map((l) => (
          <div key={l} style={{fontSize: 27, fontWeight: 600, letterSpacing: 1, opacity: 0.92, marginTop: 6}}>
            {l}
          </div>
        ))}
      </div>

      {/* karaoke / live music */}
      <div
        style={{
          position: 'absolute',
          left: 60,
          width: 960,
          top: win.y + win.h + 462,
          height: 148,
          display: 'flex',
          alignItems: 'center',
          borderRadius: 40,
          background: 'rgba(58,4,30,0.62)',
          boxShadow: `0 0 0 2px rgba(255,190,220,${0.35 + 0.55 * acc}), 0 0 ${20 + 50 * acc}px ${th.glow}${acc > 0.05 ? 'aa' : '00'}`,
        }}
      >
        {F.features.map((f, i) => (
          <React.Fragment key={f.title}>
            {i > 0 && <div style={{width: 2, alignSelf: 'stretch', margin: '26px 0', background: 'rgba(255,255,255,0.35)'}} />}
            <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18}}>
              <div style={{transform: i === 0 ? `scale(${1 + 0.1 * acc}) rotate(${-6 * acc}deg)` : undefined}}>
                <Icon kind={f.icon} size={74} color="#fff" />
              </div>
              <div>
                <div style={{fontSize: 38, fontWeight: 800, letterSpacing: 0.5, lineHeight: 1.1}}>{f.title}</div>
                {f.sub ? <div style={{fontSize: 40, fontWeight: 800, color: '#ffc2de', lineHeight: 1.15}}>{f.sub}</div> : null}
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>

      {props.audio ? <Audio src={staticFile(props.audio)} /> : null}
      <AbsoluteFill style={{background: '#000', opacity: fadeOut}} />
    </AbsoluteFill>
  );
};
