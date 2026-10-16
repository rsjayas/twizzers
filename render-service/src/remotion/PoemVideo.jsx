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

// Gradient pairs per mood. The first matching mood tag wins.
// TODO: replace with the real Lottie/Rive template once those files exist.
const PALETTES = {
  romantic: ["#ff9a9e", "#fad0c4"],
  playful: ["#f6d365", "#fda085"],
  nostalgic: ["#a18cd1", "#fbc2eb"],
  deeply_romantic: ["#cc2b5e", "#753a88"],
  gratitude: ["#84fab0", "#8fd3f4"],
  apology: ["#a1c4fd", "#c2e9fb"],
};
const DEFAULT_PALETTE = PALETTES.romantic;

const pickPalette = (tags = []) => {
  for (const t of tags) if (PALETTES[t]) return PALETTES[t];
  return DEFAULT_PALETTE;
};

const Petal = ({ index, width, height }) => {
  const frame = useCurrentFrame();
  const x0 = random(`x${index}`) * width;
  const speed = 0.8 + random(`s${index}`) * 1.6;
  const size = 14 + random(`z${index}`) * 26;
  const phase = random(`p${index}`) * Math.PI * 2;
  const y = ((frame * speed + random(`y${index}`) * height) % (height + 80)) - 40;
  const x = x0 + Math.sin(frame / 25 + phase) * 40;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        height: size,
        borderRadius: "50% 0 50% 50%",
        background: "rgba(255,255,255,0.55)",
        transform: `rotate(${frame * 2 + index * 40}deg)`,
      }}
    />
  );
};

const Line = ({ text, index, fps }) => {
  const frame = useCurrentFrame();
  const start = Math.round((INTRO_SECONDS + index * SECONDS_PER_LINE) * fps);
  const opacity = interpolate(frame, [start, start + fps * 0.8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const lift = interpolate(frame, [start, start + fps * 0.8], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ opacity, transform: `translateY(${lift}px)`, margin: "14px 0" }}>{text}</div>
  );
};

export const PoemVideo = ({ poem, recipient, moodTags, musicUrl }) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const lines = poemLines(poem);
  const [c1, c2] = pickPalette(moodTags);

  const bg = interpolateColors(frame, [0, durationInFrames], [c1, c2]);
  const fadeOut = interpolate(
    frame,
    [durationInFrames - OUTRO_SECONDS * fps * 0.6, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, ${bg}, ${c2})`,
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      {musicUrl ? <Html5Audio src={musicUrl} volume={(f) => interpolate(f, [0, 30, durationInFrames - 45, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} /> : null}

      {Array.from({ length: 18 }, (_, i) => (
        <Petal key={i} index={i} width={width} height={height} />
      ))}

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: "0 90px",
          textAlign: "center",
          color: "#3a1f2b",
          fontSize: 58,
          lineHeight: 1.35,
          opacity: fadeOut,
        }}
      >
        <div>
          {recipient ? (
            <div style={{ fontSize: 44, marginBottom: 40, opacity: 0.8 }}>For {recipient}</div>
          ) : null}
          {lines.map((text, i) => (
            <Line key={i} text={text} index={i} fps={fps} />
          ))}
        </div>
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          bottom: 70,
          width: "100%",
          textAlign: "center",
          color: "rgba(58,31,43,0.55)",
          fontSize: 34,
          letterSpacing: 4,
        }}
      >
        TWEEZERS
      </div>
    </AbsoluteFill>
  );
};
