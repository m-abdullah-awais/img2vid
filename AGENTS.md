# AGENTS.md

Persistent memory for this project. This is the only memory location, per the project rules.

## Project Rules (binding, from temp/claude-rules.md)

Re-read `temp/claude-rules.md` at the start of a session. It is the source of truth and
the user edits it.


1. Never go outside this directory (`E:\YT\Images to Video`).
2. Store all memory inside this same directory in this `AGENTS.md` file and no other place.
3. Always follow the rules defined in `temp/claude-rules.md`.
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
14. Keep `claude-rules.md` in the `temp/` folder. `temp/` must be listed in `.gitignore`
    so the whole folder is never tracked, and `claude-*.bat` must be ignored too.

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
- `h264_qsv` (Intel Quick Sync) hardware encoder is available and works, but it is NOT the
  fast path on this machine. See finding 4: software x264 at ultrafast beats it.
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

## Behaviour Decisions

- Count mismatches are a hard error by default, because silently pairing images to the
  wrong lines produces a video that looks fine until watched. `--force` repairs it and
  reports what it did.
- `--force` relaxes all four input checks, not just the count. A flag that bypasses one
  validation and then dies on the next is useless.
- `--force` is a no-op on valid input, verified by comparing timelines, so it is safe to
  leave switched on permanently in the Run.bat FLAGS line.
- Forcing never touches the frame quantiser. Frame counts still sum to the audio length
  exactly, so the video cannot drift. Only the image to line pairing is repaired.
- Run.bat has a FLAGS line and an interactive prompt on mismatch, because a double click
  gives the user nowhere to type a flag.

## Setup And Portability

- `Setup.bat` installs nothing system wide, per rule 7. System Python and ffmpeg are
  used when present, otherwise private copies go in `runtime\python` and `bin`.
- The Python embeddable zip is the right vehicle: about 11 MB, no installer, no admin,
  no registry, and it carries the full standard library. Verified 3.12.10 runs this
  project including the ctypes job object, producing a frame exact video.
  It only works because the project has zero pip dependencies.
- `Run.bat` prefers `runtime\python\python.exe` when it exists, so a folder set up
  portably keeps working on a machine with no Python at all.
- ffmpeg download sources, in the order Setup tries them. gyan.dev was unreachable when
  this was written, so the GitHub mirror is first:
  `github.com/GyanD/codexffmpeg` 7.1 essentials, about 88 MB, then gyan.dev, then
  `github.com/BtbN/FFmpeg-Builds` gpl, about 163 MB. The archives nest the binaries
  under a version named folder, so `for /r` searches for them rather than assuming.
- Two batch traps hit while writing it, both fixed: `findstr /c:"import site"` matches
  the commented out `#import site` line in the embeddable `._pth` file, so `/b` is
  needed to anchor to the start of a line. And `%~dp0` in a helper script under `temp\`
  resolves to `temp\`, which silently doubles paths.

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

3. **One encoder process per core is wrong.** libx264 already threads across every core
   by itself, so eight processes oversubscribe the CPU. Best of 3 runs, 100 images at
   1080p30 on 8 cores: 1 job 40.3s, 2 jobs 41.3s, **4 jobs 37.2s**, 8 jobs 43.5s. The
   4 job run also had the lowest spread by far, 2 percent against 8 to 37 percent for
   the others. `--jobs 0` therefore picks `cores // 2` for software encoding.
   Quick Sync is a single fixed function engine, so it is capped at 3 instead
   (1 job 64.0s, 3 jobs 44.7s on the same fixture).

   **Wall clock on this machine is noisy.** Identical configurations measured 25 percent
   apart across batches. Any performance claim needs best of N repeated runs on an
   otherwise idle machine, never a single measurement. An earlier round of conclusions
   was drawn from single runs and had to be thrown out.

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

6. **ffmpeg children do not reliably die with their Python parent on Windows.**
   Measured directly: killing the orchestrator left 4 ffmpeg running in one test and
   killed them in another, so the behaviour was not even consistent. Fixed with a
   Windows job object using JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, assigned in
   `probe.bind_children_to_this_process()`. Verified 4 out of 4: ffmpeg 4 -> 0.
   Two ctypes traps in that code, both already hit and fixed: handles must have
   explicit argtypes or the GetCurrentProcess pseudo handle overflows, and the job
   handle must be kept referenced or the job closes early and kills the encoders.
   A hard kill still skips cleanup, so `probe.sweep_stale_jobs()` deletes leftover
   `job_<pid>` folders whose process is gone.

   Cancelling also has to set a flag, not just kill the running processes. Killing
   alone made the thread pool start the next queued chunk, so a cancel took as long
   as the remaining work.

7. **CHUNKS_PER_JOB is 2, measured.** Best of 3 on the 100 image fixture:
   1 chunk per job 46.1s, 2 per job 44.7s at 3 percent spread, 3 per job 44.7s but with
   a 178 percent spread. More chunks costs process startup, fewer chunks leaves cores
   idle on the tail. Two is the flat spot. Progress smoothness does not depend on this
   any more, since progress comes from frame counts.

8. **Progress must come from frame counts, not completed chunks.** Reporting once per
   finished chunk meant the bar sat at zero for 54 seconds of a 100 second render and
   then jumped, which reads as a hung program. Each chunk now runs with
   `-progress pipe:1` and the frame counts are summed across concurrent chunks.

9. **Killing a background shell does not kill the ffmpeg it spawned.** A stopped sweep
   kept running and silently competed with a benchmark, making every number in it too
   slow and useless. Always confirm with `Get-Process ffmpeg, python` afterwards, and
   never trust a benchmark that ran while anything else was encoding.
