#!/bin/sh
# Generates the three original placeholder tracks (synthesised pads, no samples,
# no licensing issues). Replace them with licensed music before launch.
# Usage: sh static/music/generate.sh   (needs ffmpeg)
set -e
cd "$(dirname "$0")"
D=32
# name  freq1 freq2 freq3  tremolo_hz
make() {
  ffmpeg -loglevel error -y \
    -f lavfi -i "sine=frequency=$2:duration=$D" \
    -f lavfi -i "sine=frequency=$3:duration=$D" \
    -f lavfi -i "sine=frequency=$4:duration=$D" \
    -filter_complex "[0][1][2]amix=inputs=3:normalize=0,volume=2.2,tremolo=f=$5:d=0.35,lowpass=f=1800,aecho=0.8:0.6:420:0.35,afade=t=in:d=2,afade=t=out:st=$((D-3)):d=3" \
    -ac 1 -b:a 64k "$1.mp3"
}
make soft_piano_love      261.63 329.63 392.00 0.25   # C major, slow and warm
make playful_strings      293.66 369.99 440.00 1.4    # D major, livelier shimmer
make nostalgic_guitar     220.00 261.63 329.63 0.5    # A minor, wistful
