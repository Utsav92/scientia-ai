#!/bin/zsh
# Soft ambient pad (synthesised, no samples): layered sines on a Cmaj9-ish voicing with slow tremolo, shimmer echo, low-pass, fade in/out.
OUT=${1:-music.mp3}; D=${2:-100}
ffmpeg -y -loglevel error \
 -f lavfi -i "sine=f=65.41:d=$D" -f lavfi -i "sine=f=98.00:d=$D" -f lavfi -i "sine=f=164.81:d=$D" -f lavfi -i "sine=f=246.94:d=$D" -f lavfi -i "sine=f=293.66:d=$D" -f lavfi -i "sine=f=392.00:d=$D" -f lavfi -i "sine=f=523.25:d=$D" \
 -filter_complex "[0]volume=0.55,tremolo=f=0.1:d=0.3[a];[1]volume=0.40,tremolo=f=0.12:d=0.4[b];[2]volume=0.28,tremolo=f=0.14:d=0.5[c];[3]volume=0.20,tremolo=f=0.11:d=0.5[d];[4]volume=0.16,tremolo=f=0.16:d=0.5[e];[5]volume=0.11,tremolo=f=0.13:d=0.6[f];[6]volume=0.07,tremolo=f=0.18:d=0.6[g];[a][b][c][d][e][f][g]amix=inputs=7:normalize=0,aecho=0.8:0.88:700|1300:0.30|0.22,lowpass=f=2400,highpass=f=40,volume=2.4,afade=t=in:d=5,afade=t=out:st=$((D-7)):d=7" \
 -c:a libmp3lame -b:a 192k "$OUT"
