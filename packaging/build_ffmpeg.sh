#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
RSB_ROOT="$(pwd)"
RSB_PREFIX="$RSB_ROOT/build/vendor"
RSB_JOBS="${RSB_BUILD_JOBS:-4}"
mkdir -p build/audio-source "$RSB_PREFIX/bin" "$RSB_PREFIX/notices"
tar -xf build/sources/lame-3.100.tar.gz -C build/audio-source
tar -xf build/sources/ffmpeg-8.1.3.tar.xz -C build/audio-source
cd build/audio-source/lame-3.100
./configure --prefix="$RSB_PREFIX" --disable-shared --enable-static --disable-frontend --disable-decoder --disable-asm --with-pic
make -j"$RSB_JOBS"
make install
cp COPYING "$RSB_PREFIX/notices/LAME-COPYING.txt"
cd ../ffmpeg-8.1.3
RSB_EXTRA_LDFLAGS="-L$RSB_PREFIX/lib"
if [[ "${MSYSTEM:-}" == MINGW64 ]]; then
  RSB_EXTRA_LDFLAGS="$RSB_EXTRA_LDFLAGS -static -static-libgcc"
fi
./configure --prefix="$RSB_PREFIX" --disable-autodetect --disable-doc --disable-debug --disable-network --disable-asm \
  --disable-everything --enable-ffmpeg --enable-static --disable-shared --enable-libmp3lame \
  --enable-protocol=file,pipe --enable-demuxer=aac,flac,mp3,mov,ogg,wav,aiff,pcm_s16le \
  --enable-decoder='aac,aac_fixed,alac,flac,mp3,mp3float,opus,vorbis,pcm*' \
  --enable-parser=aac,aac_latm,flac,mpegaudio,opus,vorbis \
  --enable-encoder=libmp3lame,pcm_s16le,pcm_f32le --enable-muxer=mp3,wav,pcm_s16le,pcm_f32le,null \
  --enable-filter=abuffer,abuffersink,aformat,aresample,anull,acompressor,highpass,loudnorm,ebur128,volume,alimiter \
  --extra-cflags="-I$RSB_PREFIX/include" --extra-ldflags="$RSB_EXTRA_LDFLAGS" --pkg-config=false
make -j"$RSB_JOBS"
make install
cp COPYING.LGPLv2.1 "$RSB_PREFIX/notices/FFmpeg-COPYING-LGPLv2.1.txt"
cp config.h "$RSB_PREFIX/notices/FFmpeg-build-config.h"
"$RSB_PREFIX/bin/ffmpeg" -version > "$RSB_PREFIX/notices/FFmpeg-build.txt"
"$RSB_PREFIX/bin/ffmpeg" -L > "$RSB_PREFIX/notices/FFmpeg-license.txt" 2>&1
if grep -E -- '--enable-gpl|--enable-nonfree|--enable-version3' "$RSB_PREFIX/notices/FFmpeg-build.txt"; then
  echo 'Unexpected license configuration' >&2
  exit 1
fi
