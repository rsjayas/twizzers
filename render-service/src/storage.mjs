// Where rendered files end up.
//
// If the R2_* env vars are set, files are uploaded to Cloudflare R2 (S3
// compatible) and the public CDN URL is returned. Otherwise files stay in
// OUTPUT_DIR and are served by this process (local dev only).
//
//   R2_ENDPOINT           https://<account-id>.r2.cloudflarestorage.com
//   R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY
//   R2_BUCKET
//   R2_PUBLIC_BASE_URL    public URL of the bucket / CDN domain, e.g. https://media.example.com
import fs from "node:fs";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const { R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL } = process.env;

export const r2Enabled = Boolean(R2_ENDPOINT && R2_ACCESS_KEY_ID && R2_SECRET_ACCESS_KEY && R2_BUCKET && R2_PUBLIC_BASE_URL);

const client = r2Enabled
  ? new S3Client({
      region: "auto",
      endpoint: R2_ENDPOINT,
      forcePathStyle: true,
      credentials: { accessKeyId: R2_ACCESS_KEY_ID, secretAccessKey: R2_SECRET_ACCESS_KEY },
    })
  : null;

/** Uploads a local file and returns its public URL. */
export async function uploadFile(localPath, key, contentType) {
  await client.send(
    new PutObjectCommand({
      Bucket: R2_BUCKET,
      Key: key,
      Body: fs.readFileSync(localPath),
      ContentType: contentType,
      CacheControl: "public, max-age=31536000, immutable",
    }),
  );
  return `${R2_PUBLIC_BASE_URL.replace(/\/$/, "")}/${key}`;
}
