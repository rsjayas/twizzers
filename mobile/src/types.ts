export type User = { id: string; phone: string | null; email: string | null; name: string | null };
export type PoemVariant = { id: string; variant_text: string; selected: boolean };
export type Poem = { id: string; source: string; content: string | null; status: string; variants: PoemVariant[] };
export type Template = { id: string; name: string; category: string; mood_tags: string[]; preview_thumbnail_url: string | null };
export type MusicTrack = { id: string; title: string; mood_tags: string[]; audio_file_url: string; duration_seconds: number | null };
export type Creation = {
  id: string;
  poem_id: string;
  status: 'rendering' | 'ready' | 'failed';
  rendered_video_url: string | null;
  thumbnail_url: string | null;
  share_link_slug: string;
};
export type GenerateInput = {
  occasion: string;
  tone: string;
  recipient_nickname?: string;
  detail_1?: string;
  detail_2?: string;
};
