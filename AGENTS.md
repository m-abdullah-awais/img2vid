# AGENTS.md

Persistent memory for this project. This is the only memory location, per the project rules.

## Project Rules (binding, from claude-rules.md)

1. Never go outside this directory (`E:\YT\Images to Video`).
2. Store all memory inside this same directory in this `AGENTS.md` file and no other place.
3. Always follow the rules defined in `claude-rules.md`.
4. The developer details below must be included in project documentation.
5. Do not push code. Only commit locally, time to time, per feature or phase.
6. Never commit with a co author trailer of any kind.
7. Install everything locally to project scope only. Never install anything globally.
8. Stop all servers, shells, terminals and monitors that were started before finishing.
9. Never use an em dash anywhere in the complete project.
10. Always keep `README.md` as professional, high quality documentation, including the developer details.
11. Store all exported, tested or generated artefacts in the `./temp/` folder inside this directory.
12. Keep replies straightforward, no filler.
13. Do not change git config or other machine settings.

## Developer

Muhammad Abdullah Awais
Full Stack Developer

- Website: www.abdullahawais.com
- Email: contact@abdullahawais.com
- LinkedIn: https://www.linkedin.com/in/m-abdullah-awais-programmer
- GitHub: https://github.com/m-abdullah-awais
- YouTube: https://www.youtube.com/@m\_abdullah\_awais
- Instagram: https://www.instagram.com/m\_abdullah\_awais

## Project

**img2vid** turns a timestamped transcript plus one image per transcript line plus one or more
audio files into a finished MP4. Each image is held on screen from its own timestamp until the
next one. The last image runs until the audio ends.

Priority is render speed. All heavy work is delegated to ffmpeg. Python only orchestrates.

## Environment Facts (verified on this machine, 2026-08-18)

- ffmpeg and ffprobe N-121938 full GPL build, already on PATH. Not installed by this project.
- `h264_qsv` (Intel Quick Sync) hardware encoder is available and works. This is the fast path.
- `h264_nvenc` fails: `nvcuda.dll` missing. No NVIDIA runtime on this machine.
- `h264_amf` fails: `amfrt64.dll` missing. No AMD runtime on this machine.
- `libx264` is the software fallback.
- Python 3.14.6, 8 logical CPUs, git 2.51.2.
- Python standard library only. There are no third party dependencies, so there is nothing to install.

## Design Notes

- Segment `i` is extended to the start of segment `i+1`, so there are never black gaps.
  End times present in an SRT or VTT file are deliberately ignored.
- Durations are quantised to whole frames at shared boundaries
  (`frames[i] = round(end*fps) - round(start*fps)`), so rounding error never accumulates
  and total video length matches total audio length exactly.

## Findings That Cost Time To Discover

These were all measured on this machine. Do not undo them without re-measuring.

1. **The concat demuxer cannot be used for image timing.** It was the first design and it
   was wrong. Durations are stored in whole microseconds, and a 30fps frame boundary is
   33333.33 microseconds, which is not representable. Measured symptoms: segment
   boundaries moved a frame either way, the final entry ignored its declared `duration`
   completely, and the whole stream came out shifted one frame early. Adding a repeated
   trailing `file` entry fixes only the last entry, not the drift. Setting an input `-r`
   makes it far worse (one frame per image).
   The replacement is `loop=loop=N-1:size=1` per image plus `concat` filter plus
   `-frames:v`, which is exact by construction. Verified frame by frame.

2. **JPEG and PNG produce different colour ranges.** A JPEG decodes to full range
   `yuvj420p`, a PNG to limited range `yuv420p`. Chunks built from different source
   formats then cannot be stream copied together without a visible brightness jump.
   Fixed by pinning `format=rgb24` on the way in and
   `scale=out_color_matrix=bt709:out_range=tv` on the way out, for every image.

3. **libx264 already threads across all cores.** Running one encoder process per core is
   therefore not the big win it looks like. Measured on the 300 image, 10 minute fixture:
   1 job 152.9s, 8 jobs 119.3s. Real but modest, about 22 percent.
   Quick Sync is a single fixed function engine and peaks at about 3 concurrent sessions
   (137.6s at 1 job, 105.6s at 3, 110.7s at 6), which is why `--jobs 0` caps it.

4. **The encoder is the wall, not the pipeline.** Measured on a real still PNG through
   the actual filter chain, single process, static 1080p:

   | encoder             | fps | size |
   | ------------------- | --- | ---- |
   | x264 ultrafast      | 393 | 1.5 MB |
   | x264 superfast      | 228 | 1.4 MB |
   | x264 veryfast       | 202 | 1.4 MB |
   | x264 faster         | 122 | 1.4 MB |
   | qsv veryfast        | 255 | 1.4 MB |
   | qsv faster          | 251 | 1.4 MB |
   | qsv fast            | 239 | 1.4 MB |

   Conclusions that are now baked into the code:
   - `x264 -preset ultrafast` is twice as fast as `veryfast` for about 7 percent more
     size. For still frames the slower presets only buy better motion estimation, and
     consecutive frames here are identical, so there is nothing to estimate.
   - `-tune stillimage` measured as making no difference whatsoever. Removed.
   - **Software beat hardware on this machine** (393 against 255). "Hardware is faster"
     is not a safe assumption for still image content. This is why `detect_encoder`
     now times the candidates and caches the winner instead of preferring QSV.

   The remaining levers are `--fps` (biggest by far, and free on a still slideshow) and
   nothing much else. The orchestration layer has no large win left in it.

5. **Do not benchmark with `-f lavfi -i testsrc2` plus `select=eq(n,0)`.** ffmpeg still
   generates and filters every source frame before the select drops them, so the
   measurement is dominated by source generation rather than encoding. An earlier sweep
   was thrown away for this reason. Benchmark against a real image file instead.
