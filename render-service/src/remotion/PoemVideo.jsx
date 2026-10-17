import {
  AbsoluteFill,
  Html5Audio,
  interpolate,
  interpolateColors,
  random,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { INTRO_SECONDS, OUTRO_SECONDS, SECONDS_PER_LINE, poemLines } from "./timing.js";

// ---------------------------------------------------------------- moods (fallback look)
const PALETTES = {
  romantic: ["#ff9a9e", "#fad0c4"],
  playful: ["#f6d365", "#fda085"],
  nostalgic: ["#a18cd1", "#fbc2eb"],
  deeply_romantic: ["#cc2b5e", "#753a88"],
  gratitude: ["#84fab0", "#8fd3f4"],
  apology: ["#a1c4fd", "#c2e9fb"],
};
const pickPalette = (tags = []) => {
  for (const t of tags) if (PALETTES[t]) return PALETTES[t];
  return PALETTES.romantic;
};

// ---------------------------------------------------------------- decorations
const Petals = ({ count = 18, color = "rgba(255,255,255,0.55)", min = 14, max = 40 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  return Array.from({ length: count }, (_, i) => {
    const x0 = random(`x${i}`) * width;
    const speed = 0.8 + random(`s${i}`) * 1.6;
    const size = min + random(`z${i}`) * (max - min);
    const phase = random(`p${i}`) * Math.PI * 2;
    const y = ((frame * speed + random(`y${i}`) * height) % (height + 80)) - 40;
    const x = x0 + Math.sin(frame / 25 + phase) * 40;
    return (
      <div
        key={i}
        style={{
          position: "absolute", left: x, top: y, width: size, height: size,
          borderRadius: "50% 0 50% 50%", background: color,
          transform: `rotate(${frame * 2 + i * 40}deg)`,
        }}
      />
    );
  });
};

const Stars = ({ count = 70 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  return Array.from({ length: count }, (_, i) => {
    const size = 2 + random(`ss${i}`) * 4;
    const twinkle = 0.35 + 0.65 * Math.abs(Math.sin(frame / (18 + random(`t${i}`) * 30) + random(`o${i}`) * 6));
    return (
      <div
        key={i}
        style={{
          position: "absolute", left: random(`sx${i}`) * width, top: random(`sy${i}`) * height * 0.8,
          width: size, height: size, borderRadius: "50%", background: "#fff", opacity: twinkle,
          boxShadow: `0 0 ${size * 3}px rgba(255,255,255,0.8)`,
        }}
      />
    );
  });
};

const Moon = () => (
  <div style={{ position: "absolute", top: 140, right: 130, width: 150, height: 150, borderRadius: "50%", background: "#fff7d6", boxShadow: "0 0 80px rgba(255,247,214,0.55)" }}>
    <div style={{ position: "absolute", top: -14, left: 38, width: 140, height: 140, borderRadius: "50%", background: "#1b1740" }} />
  </div>
);

const Rain = ({ count = 90 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  return Array.from({ length: count }, (_, i) => {
    const len = 40 + random(`rl${i}`) * 70;
    const speed = 22 + random(`rs${i}`) * 18;
    const y = ((frame * speed + random(`ry${i}`) * height) % (height + len)) - len;
    return (
      <div
        key={i}
        style={{
          position: "absolute", left: random(`rx${i}`) * (width + 200) - 100, top: y, width: 2, height: len,
          background: "linear-gradient(to bottom, rgba(255,255,255,0), rgba(220,235,255,0.55))",
          transform: "rotate(12deg)",
        }}
      />
    );
  });
};

const Sun = () => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const y = height * 0.62 + frame * 0.12;  // slowly sinking
  return (
    <>
      <div style={{ position: "absolute", left: "50%", top: y, width: 420, height: 420, marginLeft: -210, borderRadius: "50%", background: "radial-gradient(circle, #fff3c4 0%, #ffb347 55%, rgba(255,140,66,0) 72%)" }} />
      <div style={{ position: "absolute", left: -200, bottom: -140, width: 1000, height: 420, borderRadius: "50%", background: "#4a2a5c" }} />
      <div style={{ position: "absolute", right: -260, bottom: -190, width: 1100, height: 440, borderRadius: "50%", background: "#321a45" }} />
    </>
  );
};

const Glow = () => {
  const frame = useCurrentFrame();
  const flicker = 0.85 + 0.15 * Math.sin(frame / 7);
  return (
    <div style={{ position: "absolute", left: "50%", bottom: 260, width: 520, height: 520, marginLeft: -260, borderRadius: "50%", opacity: flicker, background: "radial-gradient(circle, rgba(255,196,110,0.35), rgba(255,196,110,0) 70%)" }} />
  );
};

// ---------------------------------------------------------------- looks, picked by the template's category
const LOOKS = {
  sunset_walk: {
    background: () => "linear-gradient(180deg, #ff9966 0%, #ff5e62 45%, #7b3fa0 100%)",
    text: "#fff8ee", shadow: "0 2px 18px rgba(60,20,60,0.55)", mark: "rgba(255,248,238,0.7)",
    decor: () => <Sun />,
  },
  cherry_blossom: {
    background: () => "linear-gradient(170deg, #ffe3ec 0%, #ffc2d4 100%)",
    text: "#5a1f3a", shadow: "none", mark: "rgba(90,31,58,0.55)",
    decor: () => <Petals count={36} color="rgba(255,255,255,0.8)" min={22} max={56} />,
  },
  starry_night: {
    background: () => "linear-gradient(180deg, #0b1026 0%, #1b1740 55%, #3a1c5e 100%)",
    text: "#f6edff", shadow: "0 0 22px rgba(160,140,255,0.55)", mark: "rgba(246,237,255,0.6)",
    decor: () => <><Stars /><Moon /></>,
  },
  cozy_rain: {
    background: () => "linear-gradient(180deg, #2f2a3d 0%, #4a3a46 60%, #6a4b4b 100%)",
    text: "#fdf1e1", shadow: "0 2px 14px rgba(0,0,0,0.5)", mark: "rgba(253,241,225,0.6)",
    decor: () => <><Glow /><Rain /></>,
  },
};

export const PoemVideo = ({ poem, recipient, moodTags, musicUrl, templateCategory }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const lines = poemLines(poem);
  const look = LOOKS[templateCategory];

  let background, textColor, textShadow, markColor, decor;
  if (look) {
    background = look.background(); textColor = look.text; textShadow = look.shadow; markColor = look.mark; decor = look.decor();
  } else {
    // No known template: a soft gradient from the mood tags with falling petals.
    const [c1, c2] = pickPalette(moodTags);
    background = `linear-gradient(160deg, ${interpolateColors(frame, [0, durationInFrames], [c1, c2])}, ${c2})`;
    textColor = "#3a1f2b"; textShadow = "none"; markColor = "rgba(58,31,43,0.55)"; decor = <Petals />;
  }

  const fadeOut = interpolate(frame, [durationInFrames - OUTRO_SECONDS * fps * 0.6, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const volume = (f) =>
    interpolate(f, [0, 30, durationInFrames - 45, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background,
        // Noto covers Hindi (Devanagari) and other Indian scripts on Linux hosts.
        fontFamily: "Georgia, 'Noto Serif', 'Noto Serif Devanagari', 'Noto Sans Devanagari', serif",
      }}
    >
      {musicUrl ? <Html5Audio src={musicUrl} volume={volume} /> : null}
      {decor}

      <AbsoluteFill
        style={{
          justifyContent: "center", alignItems: "center", padding: "0 90px", textAlign: "center",
          color: textColor, textShadow, fontSize: 58, lineHeight: 1.35, opacity: fadeOut,
        }}
      >
        <div>
          {recipient ? <div style={{ fontSize: 44, marginBottom: 40, opacity: 0.85 }}>For {recipient}</div> : null}
          {lines.map((text, i) => (
            <Line key={i} text={text} index={i} fps={fps} />
          ))}
        </div>
      </AbsoluteFill>

      <div style={{ position: "absolute", bottom: 70, width: "100%", textAlign: "center", color: markColor, fontSize: 34, letterSpacing: 4 }}>
        TWEEZERS
      </div>
    </AbsoluteFill>
  );
};

const Line = ({ text, index, fps }) => {
  const frame = useCurrentFrame();
  const start = Math.round((INTRO_SECONDS + index * SECONDS_PER_LINE) * fps);
  const progress = (from, to) => interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const opacity = progress(start, start + fps * 0.8);
  return <div style={{ opacity, transform: `translateY(${(1 - opacity) * 30}px)`, margin: "14px 0" }}>{text}</div>;
};
