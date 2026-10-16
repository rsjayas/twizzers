// Shared timing so the composition length and the line reveal agree.
export const FPS = 30;
export const INTRO_SECONDS = 1.5;
export const OUTRO_SECONDS = 2.5;
export const SECONDS_PER_LINE = 2.2;
export const MIN_SECONDS = 8;
export const MAX_SECONDS = 60;

export function poemLines(poem) {
  return String(poem || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
}

export function durationInSeconds(poem) {
  const lines = poemLines(poem).length;
  const seconds = INTRO_SECONDS + lines * SECONDS_PER_LINE + OUTRO_SECONDS;
  return Math.min(MAX_SECONDS, Math.max(MIN_SECONDS, seconds));
}
