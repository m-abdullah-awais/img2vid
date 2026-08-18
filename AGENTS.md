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
- The concat demuxer emits one frame per image, so `scale` and `pad` run once per image
  rather than once per output frame. Frame duplication to the target fps happens after
  the filter graph, where static frames are cheap to encode.
