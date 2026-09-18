# AGENTS.md

Persistent memory for this project. This is the only memory location, per the project rules.

## Project Rules (binding, from temp/claude-rules.md)

Re-read `temp/claude-rules.md` at the start of a session. It is the source of truth and
the user edits it.


1. Never go outside this directory (`E:\YT\Images to Video`).
2. Store all memory inside this same directory in this `AGENTS.md` file and no other place.
3. Always follow the rules defined in `temp/claude-rules.md`.
4. The developer details below must be included in project documentation.
5. Do not push code. Only commit locally, time to time, per feature or phase. The user
   has overridden this for single commits by asking outright ("commit it with no
   coauthor , and push it"); that permission covers only the commit it was given for.
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

**img2vid** turns narration audio plus one image per transcript line into a finished MP4.
Each image is held on screen from its own timestamp until the next one. The last image
runs until the audio ends.

Since 2026-09-18 it is a **web app**. `Run.bat` starts the engine's API and the Next.js
frontend in one console and opens the browser. Everything happens there: projects,
uploading narration, transcribing, adding and arranging images, building the video and
downloading it. See "Web App" below. The sections further down that talk about
`app\`, `input\`, `output\` and the three step `.bat` files describe the design before
that date. Their findings about the engine still hold; the file locations do not.

Priority is speed at both steps, and it stayed the priority through the move to a web
app, on the user's explicit instruction: "make sure that we donot compromise on the
speed". All heavy work is delegated to ffmpeg or to the speech engine. Python only
orchestrates, and the web app only starts and watches the same scripts.

## Web App

Asked for on 2026-09-18: a complete Next.js frontend, frontend and backend kept apart,
one `Run.bat` that starts both in the same terminal and opens the browser, an
`/about-developer` page, and no compromise on UX. The `.claude` folder's
`fullstack-developer` agent and `frontend-design` skill were used for it, at the user's
request.

**Layout**

```
backend/i2v/        the engine, unchanged apart from folder paths
backend/i2v/paths.py  every folder, worked out once
backend/cli/        the scripts: img2vid.py, transcribe.py, rename_images.py,
                    setup_check.py, setup_speech.py, console.py, start.py
backend/api/        the HTTP API, standard library only
backend/runtime/    gitignored: private python, bin (ffmpeg), node, whisper, npm-cache
backend/storage/    gitignored: projects/<id>/, work/, trash/
frontend/           Next.js 16 App Router, created by create-next-app
Run.bat  Setup.bat  README.md  LICENSE  AGENTS.md  .gitignore
```

**User decisions of 2026-09-18**

- **The root stays clean and everything is done in the browser.** The user's words:
  "we donot need the input, output folders etc on the root, we want the root to be
  clean, the user on the frontend upload the local files on the UI and also after
  completing downloads that files from the frontend ... the user will have no need to
  open the files". So there is no `input\` or `output\` any more, and nothing a user
  needs lives outside the app.
- Create Video.bat, Transcribe Audio.bat and Rename Images.bat were removed. The
  scripts they called remain in `backend\cli`, with explicit arguments, and are what
  the API runs.
- Setup.bat stays at the root as the one time step, and gained a Node.js step and a
  web app install and build step.
- Named projects: each video is a project with its own narration, transcript, images
  and finished videos.
- Dark editing suite look: graphite `#1B1F24`, panel `#242A31`, text `#E6E8EB`, missing
  amber `#E0A23A`, ready green `#4FB286`, build red `#E5484D`. Barlow at three widths.
- The backend is Python standard library only, so the embeddable Python still runs it.
- Images can be arranged by drag and drop. Dropping on a line places the image there,
  swapping with any image already on it. Dropping between lines inserts, and the shift
  stops at the first empty line so nothing past a gap moves.

**How the pieces fit**

- The API serves on `127.0.0.1:8765` from a thread inside `start.py`. It answers only
  requests addressed to 127.0.0.1 or localhost, only from localhost origins, and
  anything that changes state must be JSON. That closes DNS rebinding and the cross
  site form POST.
- Renders and transcriptions run as child processes of the same scripts a terminal
  would run, one at a time, with the engine's default flags. In process was rejected
  because `render._CANCELLED` is a module level Event that is never cleared, so in a
  long lived server every render after the first cancel would count as cancelled.
- Progress comes from the engine's own `[####....]  45.0%` lines, parsed from the
  child's merged, continuously drained output. An undrained pipe would stall a render.
- The UI polls `GET /api/job` rather than using server sent events. The API is a
  second origin, and an open EventSource permanently holds one of the browser's six
  connections to it, which a storyboard of 170 thumbnails needs.
- Thumbnails are keyed by content, not name, so arranging never regenerates one, and
  they are not generated at all while a render runs.
- Nothing is hard deleted through the UI. Removed or replaced files go to
  `backend\storage\trash` and can be restored for seven days.
- On first start the API imports anything left in the old root `input\` and
  `output\` folders as a project named after the first audio file, then removes those
  folders. `Run.bat` and `Setup.bat` likewise move an old root `runtime\` and `bin\`
  into `backend\runtime` rather than downloading them again.
- The browser is opened through `explorer.exe`, not directly. `start.py` sits in a
  Windows job object that kills every child when the window closes, which is what
  stops ffmpeg and Node, and a browser started as its child would be killed with it.
- npm's cache, create-next-app's saved preferences and Next's telemetry all default to
  the user profile. The cache goes to `backend\runtime\npm-cache`, telemetry is off,
  and create-next-app was run with `APPDATA` and `LOCALAPPDATA` pointed into `temp\`.
  Its preferences file did land there, which confirms the redirect was needed.
- `frontend/AGENTS.md` and `frontend/CLAUDE.md` are gitignored. `next dev` writes and
  rewrites them for coding assistants, and the text it writes contains an em dash.

**Speed through the app, measured 2026-09-18** on the imported Florian project, 54
images, 207.4 s of narration, 1920x1080 at 30 fps, with `temp/bench_render.py` and
`temp/bench_transcribe.py`:

| | terminal | browser | difference |
| --- | --- | --- | --- |
| render, best of 4 | 52.04 s | 52.92 s | +1.7% |
| transcribe `--fresh`, best of 2 | 29.49 s | 29.57 s | +0.3% |

Identical terminal renders spread from 52 to 57 s in the same session, so both
differences are inside the noise. The first attempt read +5.6 percent, and it was the
protocol, not the app: the terminal side ran with `--quiet`, and the browser run always
followed a terminal run onto a CPU that was already hot. The fixed script drops
`--quiet` and alternates which side goes first. Earlier that day, on a cooler machine,
the same terminal render took 45.3 s and 51.9 s, which is finding 12 again: this laptop
throttles hard, and any comparison has to interleave.

**Verification of the web app**
- `temp/check_engine.py`, 27 checks: the engine after the move, placement and
  `placement_report`, the black line gate end to end, the rename round trip.
- `temp/check_api.py`, 28 tests: every endpoint, security, Range, trash, the render
  gate and a real render, cancel leaving no ffmpeg, locks, every arrange case, legacy
  import on a fake root.
- `backend\cli\setup_check.py`, all fourteen checks including the speech engine from
  `backend\runtime`.
- `Run.bat --no-browser` for real: built the frontend, imported the root `input\`
  folder as project `florian-be7a` with all 54 images, the narration and both
  transcript files, and removed the empty `input\` and `output\`. A second `start.py`
  reported the running copy and exited 0.
- The old harnesses (`verify.py`, `check_index_placement.py` and the PowerShell ones)
  were gone from `temp\` by 2026-09-18, which is untracked and was cleared at some
  point. `check_engine.py` replaces the parts that still apply.

## Environment Facts (verified on this machine, 2026-08-18)

- ffmpeg and ffprobe N-121938 full GPL build, already on PATH. Not installed by this project.
- `h264_qsv` (Intel Quick Sync) hardware encoder is available and works, but it is NOT the
  fast path on this machine. See finding 4: software x264 at ultrafast beats it.
- `h264_nvenc` fails: `nvcuda.dll` missing. No NVIDIA runtime on this machine.
- `h264_amf` fails: `amfrt64.dll` missing. No AMD runtime on this machine.
- `libx264` is the software fallback.
- Python 3.14.6, 8 logical CPUs, git 2.51.2.
- The video path is Python standard library only, and that property is load bearing: it is
  why a bare embeddable Python can run it. The speech engine is the single exception and
  is kept isolated in `runtime\whisper\lib`, imported lazily, never at module import time.

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
  leave switched on permanently in the Create Video.bat FLAGS line.
- Forcing never touches the frame quantiser. Frame counts still sum to the audio length
  exactly, so the video cannot drift. Only the image to line pairing is repaired.
- Create Video.bat has a FLAGS line and an interactive prompt on mismatch, because a
  double click gives the user nowhere to type a flag. Transcribe Audio.bat follows the
  same pattern, including the --pick chooser.

## Output Naming

- The finished video is named `%Y-%m-%d_%H-%M-%S.mp4` in local time, set by
  `OUTPUT_NAME` in `app\run.py`, on the user's decision of 2026-08-29. It used to take
  the transcript's stem, which in practice was always `script.srt`, so every render
  produced `output\script.mp4` and silently replaced the take before it. A timestamp
  keeps every attempt and sorts oldest first in Explorer.
- `-o` on the command line still wins. `run.py` appends its own `-o` first and argparse
  keeps the last, so a user supplied one overrides it. `run.py` reads `-o` out of the
  passed arguments itself, in all four forms argparse accepts (`-o X`, `-oX`,
  `--output X`, `--output=X`), purely so the `output :` line it prints is the file that
  will really be written. Without that it printed the invented timestamp name while the
  render went somewhere else, which is worse than not printing it at all.

## Root Layout

Superseded on 2026-09-18 by the web app layout above. Kept for the reasoning.

- The six launchers live in `app\`, on the user's decision of 2026-08-24, so that the
  root holds only what a user touches: the four `.bat` files, `README.md`, `LICENSE`,
  `AGENTS.md`, `.gitignore`, and the folders. Fourteen items down to ten. Not to be
  confused with `app/src` in the Story Video Generator notes below, which is a different
  project.
- The `.bat` files stay at the root and must. They are the whole interface, and every one
  of them treats `%~dp0` as the project folder: `cd /d "%~dp0"`, `input\images`,
  `runtime\python\python.exe`, the zip guard. Moving them means rewriting each of those
  as `%~dp0..\` in order to hide the only thing a user is looking for.
- Every launcher therefore computes `ROOT` as the folder above its own, not its own:
  `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`. `setup_check.py` also
  keeps `APP`, because it runs `img2vid.py` as a separate process.
- `from run import ...` in `transcribe.py` and `rename_images.py` still works because
  `sys.path[0]` is the folder of the running script, which is now `app\`, and `ROOT` is
  inserted ahead of it for `import i2v`. Nothing needs `app` to be a package, so there is
  no `__init__.py` in it.
- The `.bat` files were not renumbered. `1 Setup.bat` would read badly in the error
  messages that name it, and the README already numbers the steps. So Explorer still
  shows them in the wrong order, which is a known and accepted cost.
- Verified after the move: `app\setup_check.py` all fourteen checks,
  `Create Video.bat --dry-run` over the real 162 image project, `Transcribe Audio.bat
  --help`, `Setup.bat --check`, `Rename Images.bat --dry-run`, and all three harnesses
  including the shipped copy one, which proves `app\setup_check.py` resolves from a
  `git ls-files` copy.

## Model Download Failures

- Reported from a second laptop on 2026-09-04: `429 Too Many Requests` for
  `Systran/faster-whisper-base`, after it had already joined twelve audio files. Three
  separate faults behind one error.
- **`load()` asked the Hub about a model it may already have had.** It passed
  `local_files_only=model_is_local(...)`, so any reason that helper returned False sent
  it to the network, and a rate limit then broke a machine that needed no network at
  all. It now tries `local_files_only=True` first, every time, and only goes online when
  that fails. A cached model can no longer be taken down by an outage.
- **A 429 was fatal on the first try.** It means "come back shortly", and a dropped
  connection part way through 140 MB is ordinary, so `download()` retries rather than
  giving up. `snapshot_download` skips what already arrived, so a retry resumes rather
  than restarts.
- **Forty five seconds was not long enough, reported 2026-09-05.** The same laptop hit
  the same 429 again, exhausted all three tries inside a minute and stopped. A Hub rate
  limit is counted in minutes, so the old schedule was really just the same wait with
  more steps in it. `RETRY_WAITS` now runs 5, 15, 30, 60, 120, which is six attempts
  over 3m 50s, and `retry_after()` reads the Hub's own `Retry-After` header when it
  sends one. That number wins over the schedule, but only upwards: it is floored at the
  scheduled pause so a `Retry-After: 1` cannot turn the loop into hammering, and capped
  at `LONGEST_WAIT` so a large one cannot look like a hang. A header holding an HTTP
  date rather than a count falls back to the schedule; parsing it is not worth the code.
- **The message named no way out.** It said to run Setup.bat again in a few minutes,
  which is the advice that had just failed. It now also names the exact folder to carry
  over from a machine that already has the model, `models--Systran--faster-whisper-base`,
  and the absolute path to drop it into. That is the one answer that always works, and
  the README had it while the program did not. `cache_folder_name()` builds the name so
  `model_is_local()` and the message cannot drift apart.
- `network_problem()` reads `error.response.status_code` before falling back to looking
  for "429" in the text. The substring could as easily be part of a byte count or a
  request id as the status of a response.
- **The failure came after half a minute of wasted ffmpeg work.** `transcribe.py` now
  fetches a missing model before it joins any audio.
- `network_problem()` classifies the error so the message can say what to do. Anything
  it does not recognise is passed through untouched rather than dressed up as a
  connection fault.
- Verified: `HF_HUB_OFFLINE=1` loads the base model, proving the offline path takes no
  network, and a stubbed 429 produces the new message rather than the raw HfHubHTTPError.

## Placing Images By Index

- **The reported failure, 2026-09-06.** "sometimes the image might be missing at some
  point and it results in the disturbance of all the images after it". With image 4
  absent, image 5 was shown on line 4, image 6 on line 5, and the whole video ran
  against the wrong narration from that point on. The user asked for images to be placed
  by their index, with a black screen wherever one is missing.
- **Root cause.** `build_timeline` zipped the sorted image list against the sorted start
  times. Position carries no identity, so a file that was never made is not a hole in the
  list, it is an absence, and everything after it moves up one. The only symptom was a
  count one short, which says nothing about where the gap is. `--force` then made it
  worse: with fewer images than timestamps it kept the first N timestamps and held the
  last image to the end, so the shift survived and the tail was mangled on top of it.
- **`render.place_by_index(images, count)`** returns a list of `count` slots, each a path
  or `None`, built from the number each filename starts with. `004.jpg` is line 4 whether
  or not `003.jpg` exists.
- **When it declines and falls back to position.** Any name not starting with a number,
  or any number claiming a line past the end of the transcript. The second condition is
  what keeps camera names out: `20260401_182233.jpg` claims line twenty million, so a
  folder of those is paired by position exactly as before. Without that guard every slot
  would come back empty and the whole video would render black, which is far worse than
  the bug being fixed.
- **Duplicates raise rather than fall back.** `4.jpg` and `004.png` both claim line 4, and
  by the time that check runs the folder is plainly numbered, so only one of them can be
  right. The check runs after the range check on purpose, so `2020 photo.jpg` next to
  `2020 other.jpg` exits as a camera style folder instead of being called a conflict.
- **Base 0 or 1.** `Rename Images.bat --start 0` numbers a folder from `000`, so a zero
  present means the numbers are zero based. Anything else is one based. Inferring the
  base from the lowest number present was rejected: if `001` is the missing file the base
  would shift to 2 and reintroduce the exact off by one being fixed.
- **The black frame is a real PNG, written by hand.** `render.black_image()` builds a
  solid black PNG with `struct` and `zlib`, roughly fifteen lines. The video side of this
  project is standard library only and that is worth keeping, and asking ffmpeg for a
  `color=` source would have meant plumbing `Tools` into the timeline. 1080p of zeros
  compresses to 6 KB in a few milliseconds.
- **It is made at the output resolution deliberately.** Then `--fit contain` has nothing
  to pad and `--fit cover` has nothing to crop, so the frame is black whatever `--bg` is
  set to. A small placeholder would show `--bg` coloured bars around it.
- **`fill_black()` is called from `render.render()`, not from the caller.** The only thing
  that needs a real file on disk is the encoder, so it happens where encoding starts and
  no caller can forget it. `--dry-run` never writes the file at all, which is why the
  timeline entry carries a `black` flag rather than being identified by its path.
- **Black lines are reported, not fatal.** The user asked for the black screen, and the
  alignment is correct rather than mistimed, so the run proceeds and prints which lines
  are affected. That is a real departure from the "count mismatches are a hard error"
  rule above, and it is safe for the same reason the rule exists: the failure is visible
  in the finished video instead of hidden in it.
- **Rename Images.bat is now a hazard on a numbered folder.** `plan()` renumbers
  contiguously, so running it on a folder with a gap closes the gap and puts every later
  image on the wrong line, which is the original bug reintroduced by hand. Documented in
  the README rather than changed, because renumbering without gaps is that tool's whole
  job. Worth revisiting if the user hits it.
- **Verified by `temp/check_index_placement.py`**, 22 checks. Fourteen on placement
  itself: complete folders, a hole in the middle, at the start and at the tail, several
  holes, listing order irrelevant, mixed padding and extensions, zero based folders,
  camera names and unnumbered names falling back, a number past the end falling back,
  duplicates refused, and an empty folder. Three on the black PNG, including decoding
  all 6220800 bytes of it and asserting the brightest is 0. Five end to end: it builds
  its own six colour fixture, renders it complete, deletes `004.png`, renders again and
  run length checks every one of the 360 frames, confirming line 4 is black and lines 5
  and 6 have not moved. The last check asserts the old positional pairing would have put
  image 5 on line 4, so the harness fails if the bug ever comes back.
- **Only the leading digits are read, so a name can carry words too.** The user asked on
  2026-09-06 whether the first words of the generating prompt could go in the filename as
  well, and they already could: `004. two men talking.jpg` is line 4. Worth keeping that
  way, because it is the only thing that makes a folder of 170 images reviewable by eye.
  The `--dry-run` image column was widened from 32 to 44 to suit, since a name of that
  shape was being clipped, and the rule under it from 71 to 83.
- Sampling a frame through `crop,scale=1:1` costs a few units of swscale error, which is
  invisible on a saturated colour and obvious on black, where it read `(4, 0, 5)`. The
  black PNG is therefore checked by decoding the whole file, not by sampling it.
- `temp/verify.py` pointed at `ROOT/img2vid.py`, which moved to `app/` on 2026-08-24.
  Fixed in place so the regression suite runs. All of it passes unchanged, because the
  fixture is named `shot1.png` and so takes the positional path.

- **A warning was not a gate, asked for 2026-09-06.** The first version printed which
  lines would be black and built the video anyway. The user wanted it to stop and ask:
  "if no image is provided to that index then after confirmation create the video but
  that portion will remains empty". A black frame is a real edit, so it is offered
  rather than assumed. `cli.missing_images_error()` raises, and answering yes adds
  `--allow-black`.
- **`--force` deliberately does not cover this, the user's decision of 2026-09-06.**
  It breaks the rule two sections up that `--force` relaxes every input check, and it is
  the right break: the README tells people `--force` is safe to leave permanently on the
  FLAGS line, and a permanently on flag must not be able to silence a question about
  their own images. `--allow-black` is the only permission, and it is the flag the
  prompt adds.
- **Missing lines at the tail behave exactly like a gap in the middle, the user's
  decision of 2026-09-06.** Holding the last image to the end, which is what `--force`
  does for a count mismatch, was offered and declined. Fifteen images against sixty cues
  becomes forty five black lines after a yes, and the question names the count so the
  size of that is not a surprise.
- **`--dry-run` is exempt from the gate, `--quiet` is not.** Showing what would happen is
  the whole job of the first, and the second suppresses remarks rather than stops.
- **`RenderError` now carries `repair` and `question`.** `repair` is the one flag that
  would let that particular run carry on, `question` is what to ask before adding it.
  This replaced a hardcoded `--force` in `app/run.py`, which offered that flag for every
  failure including ones it cannot repair, such as a missing images folder, and then
  re-ran and failed identically. Annotated raises: count mismatch, audio ending before
  the last timestamp, timestamps under a frame apart, and the last timestamp leaving no
  room. Unannotated: missing folder, no images, duplicate line claims, and the two
  "even with --force there is nothing to render" cases.
- **The offer in `run.py` is a loop, not a single retry.** Each repair is appended before
  the retry so it can only be offered once and cannot spin, and a second, different
  problem still gets its own offer, which the single retry could not do.
  `_offer_lines()` drops the trailing `Pass --flag` line, because the next thing printed
  is that same offer as a question.
- **`these_lines()` exists because "1 transcript line(s) have no image" is the first
  thing a user reads when a run stops.** It returns the three phrasings the message
  needs, so it reads like a sentence somebody wrote.
- Harness grew from 22 checks to 38. The new ones: a hole stops the run by default,
  the stop names the line and says nothing else moved, `--force` alone does not get past
  it, `--dry-run` does, `--allow-black` builds it and still reports the black lines, the
  error carries the right flag and question, the numbers clip past twelve, a duplicate
  and a missing folder carry no flag at all, and `run()` itself retries with the named
  flag on a yes and returns 1 on a no. That last one drives `run()` directly with
  `_can_prompt` and `_confirm` replaced, because a subprocess cannot reach the prompt:
  `_can_prompt()` wants a real console.

## Ordering Images

- `--by created|modified|name|size|type|random` and `--desc`, asked for on 2026-08-29.
  Everything works off the `ORDERS` dict, which holds the forward and reversed wording
  for each key, so adding an order is a row there plus a sort in `collect()`.
- Ties are sorted by filename first, then the real key is applied with `reverse=`. Two
  passes, because a single reversed sort would also reverse the tie break and scramble
  files that share a timestamp. Copying a folder stamps every file with the same second,
  so ties are the normal case here, not an edge case.
- **The trap that made this worth building.** The user's 137 images all had distinct
  creation times, 8 milliseconds apart, in alphabetical order, because a batch copy
  writes files alphabetically. `--by created` replayed that faithfully, and alphabetical
  puts `100_` before `10_` since a digit sorts before an underscore, so image 10 landed
  at 020. Nothing was broken: `natural_key` was correct, the sort was correct, the
  default was simply wrong for that folder. `numbered_hint()` now detects it, when four
  fifths of the names start with a digit and the chosen order disagrees with natural
  name order, and names the first position where they diverge. It stays quiet on
  `--by name`, on folders whose names are not numbered, and when the orders agree.
- **A warning was not enough, reported 2026-09-05.** The same trap reappeared on a second
  machine, and this time the copy had run *backwards*: all 170 files in `input\images`
  hold distinct creation times spanning 5.5 seconds, in exact reverse filename order, so
  `--by created` renamed `170.jpg` to `001.jpg` and reversed the whole folder. The hint
  fired and was ignored, which it would be: it appears above a list of 170 renames, the
  answer it gives is a flag, and a double click has nowhere to type one.
  `numbered_hint()` is therefore no longer only a message. When it fires and `--by` was
  *not* given, `main()` switches the order to `name`, recollects, and prints `say_kept()`
  above the menu instead. Filenames that are already numbered are an order somebody
  chose; a copy date is when the file reached the machine, which is not the same thing
  and is not even reliably forwards.
- `--by` uses `argparse.SUPPRESS` as its default so the code can tell an explicit
  `--by created` from no answer at all, `hasattr(args, "by")`. Only the unasked for
  default is overruled, and SUPPRESS also keeps `(default: None)` out of `--help`, which
  a plain `default=None` would print under `ArgumentDefaultsHelpFormatter`.
- `numbered_hint()` skips entries marked `inserted`. It used to judge the folder by every
  name in `entries`, which after `place()` includes the `__inserted__0.png` staging name,
  and then quoted that name back at the user as though they had chosen it.
- Checks 11 and 12 of the harness are the pair that pins this down: a numbered folder
  whose creation dates run backwards must come out untouched, and `--by created` on that
  same folder must still reverse it. Over-correcting would break the second one.
- `random` reports the seed it picked when none was given. A shuffle nobody can repeat
  is one you cannot get back to, and `--undo` is not always what you want. `--seed`
  makes it reproducible, which is also what makes it testable.
- `random` never asks which way round, since there is no other way round a shuffle.
- The interactive menu is now three way: Enter renumbers as is, `2` inserts, `3` changes
  the order and then asks whether to insert as well. The common case is still one press
  of Enter.
- After a successful rename it offers `--undo` on the spot, defaulting to no. The result
  is still on screen and the record is the newest one, so changing your mind costs a
  keypress rather than a flag. Skipped under `--yes`, so automation never blocks.

## Inserting An Image

- `--insert IMAGE --at N`, repeatable in pairs, asked for on 2026-08-29. Everything from
  N onward shifts up one and the whole folder is renumbered. Double clicking offers the
  same thing as a menu, because there is nowhere to type a flag: Enter is the ordinary
  renumber, `2` starts the insert questions.
- An image from outside the folder is **copied**, not moved, so the user's original stays
  where they left it. One already in the folder is only moved within the ordering.
- The copy lands under an `__inserted__` staging name until the renumber gives it its
  real one. That prefix is what tells `--undo` to delete the copy rather than rename it
  back to a staging name the user never chose. `collect()` skips both staging prefixes so
  a leftover from a killed run is never numbered as though it were content, and every
  path that does not apply the plan calls `discard_staged()`.
- Two bugs found while testing this, both in code that predates it:
  - `newest_log()` sorted records as text, so two runs in the same second gave
    `20260829-075435.json` and `20260829-075435-2.json`, and a hyphen sorts before a dot.
    `names[-1]` therefore returned the **older** record. `--undo` then applied a stale
    record to a folder that had moved on and left it mangled. Now ordered by mtime.
  - `--undo` applied a record move by move, so a record that no longer matched the folder
    got half applied, which is worse than refusing: the folder then matches neither the
    record nor what the user had. It now checks every destination up front and changes
    nothing unless they are all there, with `--yes` to override. The check has to skip
    `HALFWAY` destinations, which are not supposed to exist at rest.

## Renaming Images

- `Rename Images.bat` and `rename_images.py`, asked for on 2026-08-24: renumber
  `input\images` to `001`, `002`, `003` in date created order. The user already had a
  standalone `input\images\rename_images_by_date.bat` doing this, dropped in the folder
  and double clicked. It is still there, it is theirs, and it was left alone.
- It is a helper, not a third step. The header of README still says two steps.
- The paths it renames through are unique temporary names, and the moves are done in two
  full passes: everything to a temporary name, then everything to its number. A single
  pass breaks the ordinary case, a folder already numbered `001` and `002` where the two
  have to swap, because `os.rename` onto an existing name fails on Windows and leaves the
  folder half renumbered. The user's own script has the same two pass shape but sorts by
  date a second time in pass two, so files sharing a timestamp can come back in a
  different order than they went in.
- Ties in the timestamp are broken by `natural_key`, the renderer's own filename order.
  Copying a folder stamps every file in it with the same creation time, often to the
  second, so without a tie break the result would depend on the order `os.listdir`
  happens to return. That is check 4 of the harness.
- `st_ctime` is the creation time on Windows, the one Explorer calls Date created. It is
  when the file arrived on this machine, not when the picture was taken, which is why
  `--by modified` exists.
- Every run writes its moves to `temp\renames\<stamp>.json` and `--undo` replays them
  backwards. `--undo` takes an optional record path, which is what lets the harness undo
  only its own runs and never touch the user's records. A record is written even when a
  rename fails halfway, in the `finally`, because that is exactly when undo matters.
- Exit codes follow `run.py`: 0 done or already in order, 2 nothing to do, which covers
  an empty folder, `--dry-run`, and answering the prompt with no, and 1 for a real
  failure. Both step files treat 2 as not a failure, so none of those print an error.
- Without a console it refuses to rename and says to add `--yes`, so a piped or scheduled
  run cannot silently renumber a folder.
- The regression harness is `temp\check_rename_images.ps1`, fifteen checks. It sets
  `CreationTime` from PowerShell, which `os.utime` cannot do, identifies every file by
  its contents rather than its name so a plausible looking wrong order is still caught,
  and deletes the records its own runs produced.

- Every batch file asks before it does anything, because the four launchers sit at the
  top of the folder and a curious or mistaken double click should cost nothing. The
  prompt appears only when `%cmdcmdline%` shows the file was double clicked, the same
  test the closing `pause` already used, so a terminal or a calling script goes straight
  through and automation is unaffected. Verified with a wrapper batch file: no prompt,
  no pause, exit code propagates.
- **`where python` is not a test that Python exists.** All three launchers picked their
  interpreter with `if not defined PY where python >nul 2>&1 && set "PY=python"`. A clean
  Windows keeps a Microsoft Store stub called `python.exe` on the PATH, so that succeeds
  on a machine with no Python at all, and running the stub opens the Store rather than
  the script: the window appears to do nothing and the launcher never reaches its own
  "Run Setup.bat first" message. `Setup.bat` had this right from the start and says so in
  a comment; the launchers now use the same test, running the interpreter and checking
  `sys.version_info>=(3,8)`. Fixed 2026-09-05.
- The answer is read with `set /p`, not `choice`. `set /p` needs a typed Y and Enter,
  so a bare Enter, a closed window or a stray keypress all cancel, which is the whole
  point. `choice` would accept a single accidental Y, and is one more thing that has to
  exist on the machine.
- **A `>` inside `echo` is a redirection operator, not text.** The confirmation in
  `Rename Images.bat` illustrated the rename as `IMG_20260401_182233.jpg -> 001.jpg`,
  and running it silently created empty files called `001.jpg` and `002.png` in the
  project root instead of printing the arrow. They were committed before it was
  noticed. Any `>`, `<`, `|` or `&` in an `echo` line needs a `^` in front of it, the
  same as the `(` and `)` already escaped there. Grep for it after writing any echo
  block: `grep -n "^echo " *.bat | grep -E "[^^][><|&]"`.
- The confirmation was flipped on 2026-08-29, on the user's instruction: Enter now
  continues and `N` cancels, rather than `Y` continuing and Enter cancelling. It still
  shows what it is about to do first, and closing the window still cancels, so an
  accidental open is harmless. A stray Enter now proceeds, which is the cost of the
  flip and was the user's call. `_confirm` grew a `default_yes` for the same reason.
  The one prompt deliberately left at `[y/N]` is the force question in `run.py`, since
  Enter there would silently build a video from mismatched inputs.
- `Setup.bat --check` never asks, since it changes nothing.
- The `:cancelled` label sits after `exit /b`, so the normal path cannot fall into it.

## Setup And Portability

- `Setup.bat` installs nothing system wide, per rule 7. System Python and ffmpeg are
  used when present, otherwise private copies go in `runtime\python` and `bin`.
- The Python embeddable zip is the right vehicle: about 11 MB, no installer, no admin,
  no registry, and it carries the full standard library. Verified 3.12.10 runs this
  project including the ctypes job object, producing a frame exact video.
  It only works because the project has zero pip dependencies.
- Both batch files prefer `runtime\python\python.exe` when it exists, so a folder set up
  portably keeps working on a machine with no Python at all.
- ffmpeg download sources, in the order Setup tries them. gyan.dev was unreachable when
  this was written, so the GitHub mirror is first:
  `github.com/GyanD/codexffmpeg` 7.1 essentials, about 88 MB, then gyan.dev, then
  `github.com/BtbN/FFmpeg-Builds` gpl, about 163 MB. The archives nest the binaries
  under a version named folder, so `for /r` searches for them rather than assuming.
- **The input folders must be created first, not last.** They were originally created at
  the tail of `Setup.bat`, after `setup_check.py` passed. `input/` and `output/` are
  gitignored and git cannot carry an empty folder either way, so a shipped copy has
  neither, and every one of the six `goto :finish` early exits left the recipient with
  no input folder and no explanation. Reproduced on a `git ls-files` copy: break the
  `i2v` import, run Setup, and no folders appear. They are now made before any network
  work, in `:make_folders`, which reports a failure instead of hiding it behind `2>nul`.
  `Transcribe Audio.bat` and `Create Video.bat` make them too, because their own Python
  and ffmpeg guards bail out before `run.py` and `transcribe.py` ever get to run.
  `--check` still creates nothing, it reports, because it promises to change nothing.
  The regression harness is `temp\check_setup_folders.ps1`, six checks.
- **Explorer runs a batch file straight out of a zip**, unpacking it under
  `%TEMP%\Temp1_<name>.zip\` and discarding that folder afterwards. Setup then appears
  to have done nothing at all, input folder included. Guarded by testing `%~dp0` for
  `\AppData\Local\Temp\`. Batch substring replacement is case insensitive, verified, so
  a lowercase path is caught too, and a legitimate `D:\Temp\` is not.
- **`exit /b %CODE%` with `CODE` unset exits 0**, measured. Both step files bailed that
  way on every early error, reporting success to anything that called them. They now
  mirror Setup.bat and default `CODE` to 1 at `:finish`.
- **`powershell -Command` strips a layer of quoting, so a path with a space in it cannot
  be written into its command line.** `:fetch` and `:unzip` did exactly that, passing
  `%1` and `%2` straight through, so `Expand-Archive -LiteralPath "E:\YT\Images to
  Video\..."` reached PowerShell unquoted and died on `to` with
  `PositionalParameterNotFound`. Every path in this project has a space in it. Measured,
  not deduced: the extraction failed on every path tried. The paths now travel in the
  environment, `$env:ZIP_SRC` and `$env:DL_URL`, which has no quoting to get wrong.
- **That is what produced `the ffmpeg download did not contain ffmpeg.exe`** on the
  recipient's machine. The failure was three steps earlier: the download succeeded, the
  extraction failed, `call :unzip` was never checked, and `for /r` then walked an empty
  folder and blamed the archive. Both callers now check it and say which step failed.
  Neither path had ever run on the developer's machine, where ffmpeg, ffprobe and Python
  are all on PATH, so `:python_install` and `:ffmpeg_install` were dead code locally.
  When something only breaks for other people, look for the branch the local machine
  never takes.
- `tar` has shipped in Windows since 2018 and reads zip files. It is now tried before
  `Expand-Archive`, which takes minutes on the 90 MB ffmpeg archive where tar takes
  seconds. `Expand-Archive` stays as the fallback.
- `curl -C -` was removed from `:fetch`. The callers try three different addresses in
  turn, and resume would have appended the start of one archive onto a part finished
  copy of another, giving a file that unpacks to nothing. Each attempt now deletes the
  destination first and verifies the file exists before reporting success.
- `call` runs a second round of percent expansion over its line, after delayed
  expansion. Cost an hour: a `%20` in a test URL came back as the value of `%2` followed
  by `0`. Real `Setup.bat` URLs contain no percent signs, `%PYTHON_VERSION%` is expanded
  long before. Test harnesses that pass URLs must use `!vars!`, not `%1`.
- The regression harness is `temp\check_setup_download.ps1`, eight checks. It lifts the
  `:fetch` and `:unzip` bodies out of `Setup.bat` at run time and calls them, so it
  cannot drift from the code it checks. It runs offline, over `file://` addresses. curl
  cannot be exercised that way here: a `file://` URL needs the spaces percent encoded,
  which `call` then eats, and this volume has 8.3 short names disabled. curl is covered
  by the live run instead, `Setup.bat --local --no-transcribe` in a `git ls-files` copy,
  which fetches and unpacks both Python and ffmpeg and passes every check.
- Two batch traps hit while writing it, both fixed: `findstr /c:"import site"` matches
  the commented out `#import site` line in the embeddable `._pth` file, so `/b` is
  needed to anchor to the start of a line. And `%~dp0` in a helper script under `temp\`
  resolves to `temp\`, which silently doubles paths.

## Speech To Text

Mirrors `E:\YT\Story Video Generator`, on the user's instruction to implement the same
model here. That project was read only and was not modified. What it does, verified by
reading `app/src/transcribe.py`, `app/config.json` and `app/scripts/download_model.py`:

- faster-whisper, CTranslate2 backend, `device="cpu"`, `compute_type="int8"`.
- `Systran/faster-whisper-<size>`, sizes capped at `tiny` / `base` / `small`. Its live
  config is `base`. Larger sizes are rejected there and here, because they run near or
  below realtime on a CPU, which defeats the point.
- `transcribe(audio, language=None, word_timestamps=..., vad_filter=True)`. Everything
  else is library default.
- `HF_HUB_DISABLE_XET=1` must be set **before** `huggingface_hub` is imported. The Xet
  transfer backend stalls on some networks. Carried over here, along with `HF_HOME` and
  `HUGGINGFACE_HUB_CACHE` pointed at the project folder so nothing lands in the user
  profile, per rule 7.
- Multiple audio files are joined with the ffmpeg concat **filter** first, then
  transcribed once, which is what keeps timestamps continuous. The demuxer would not
  cope with mixed formats and rates. Same approach here, into 16 kHz mono, which is what
  whisper resamples to anyway.
- Timestamps are clamped to the real duration, because whisper overshoots the end of the
  file on the final segment.

Deliberate differences here, all for speed or for this project's needs:

- `beam_size` defaults to 1, not the library default of 5.
- `condition_on_previous_text` defaults to off, not on.
- `word_timestamps` defaults to off and is switched on automatically only when cue
  reshaping needs it. It is pure cost otherwise.
- The result cache means a repeat run does not need the engine at all: the cues are
  reread from `temp\transcribe_cache` and the three output files are rewritten from
  them. That is deliberate, but it caught out the verification harness, which renamed
  the engine folder away and then saw a successful run. The missing engine path has to
  be exercised with `--fresh`.
- Cue re-splitting (`--max-chars`, `--max-seconds`, `--min-seconds`) exists because one
  cue becomes one image here, so cue length sets the image count. That project has no
  equivalent, its SRT export is one cue per whisper segment.

Install shape:

- `pip install --target runtime\whisper\lib`, not a venv. One code path for the system
  Python and the embeddable one, which cannot host a venv because it has no `ensurepip`.
  Setup bootstraps pip with `get-pip.py` only in the embeddable case.
- `runtime\whisper\lib\.python-version` records the installing interpreter. Extension
  modules are built per CPython version, so `i2v/speech.py` checks it and says
  "run Setup.bat" instead of letting a bare ImportError surface.
- `i2v/speech.py` imports `faster_whisper` inside functions, never at module level, so
  `i2v` stays standard library only and the video path works without the engine.
- ctranslate2 4.8.1 does ship a `cp314` wheel, so the user's system Python 3.14.6 works.
  This was checked rather than assumed after a PyPI listing suggested cp313 was the
  ceiling.

## Findings That Cost Time To Discover

These were all measured on this machine. Do not undo them without re-measuring.

0. **Never patch a file in this project through a shell quoted Python one liner or
   heredoc. Use the Edit tool.** Cost time three separate times. Two distinct failures,
   both silent:
   - Doubled backslashes collapse before Python sees them, so `"app\\run.py"` becomes
     `app` plus a carriage return, `"app\\transcribe.py"` becomes `app` plus a tab, and
     `"temp\\transcribe_cache"` in AGENTS.md became a tab as well. `\s` and `\i` survive
     only because they are not valid escapes. The batch files then failed with names like
     `appename_images.py`. Build any backslash as `chr(92)` if a script is unavoidable,
     and scan afterwards for bytes 0x07 to 0x0D.
   - A double quote inside a `python -c "..."` argument ends the shell string, so
     `` `cd /d "%~dp0"` `` was written without its quotes.
   Also note `io.open(path)` translates a lone carriage return to a newline on read, so
   repairing that damage needs `newline=""` on both the read and the write.

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

10. **The batched pipeline silently destroys the segmentation this project needs.**
    `BatchedInferencePipeline` is about 25 percent faster, but it defaults to
    `without_timestamps=True`, so it emits one cue per speech region the voice detector
    found rather than one per sentence. Measured on the 399.4s narration that is
    **15 cues instead of 86**, a longest cue of 29.7s, and therefore one image every
    26 seconds. Passing `without_timestamps=False` restores sentence level cues (90,
    longest 10.5s) and keeps most of the speedup.
    It is still not the default, because accuracy is measurably worse: word error rate
    against the reference transcript is **4.3 percent batched against 0.9 percent
    sequential**. For a transcript that is both the timing source and the on screen
    script, 11 seconds is not worth five times the errors. `--batch 8` is offered and
    documented instead.

11. **A model folder existing does not mean the model is there.** An interrupted
    HuggingFace download leaves the folder, the refs and the metadata behind with only
    a `.incomplete` part file where `model.bin` should be. The first version of
    `model_is_local()` checked for the folder, so Setup reported "already here, nothing
    to download", `local_files_only=True` was then passed, and the run died with
    `IncompleteSnapshotError` instead of simply resuming. This reproduced here for real:
    the `small` download stalled at 60 MB of 484 MB and every retry claimed success.
    `model_is_local()` now looks for a non empty `model.bin` inside `snapshots/`, and
    `setup_speech.py` re-checks after downloading rather than trusting the return.

12. **This machine throttles hard under sustained decoding, so transcription
    benchmarks need more care than render benchmarks.** The i7-8650U has a 15W budget
    and int8 GEMM is exactly the AVX heavy work that exhausts it. The same decode of
    the same file measured **46.5s on an idle machine and 343.1s after a run of back to
    back jobs**, a factor of seven. Four consecutive full runs did not finish inside a
    ten minute timeout. Any transcription measurement has to start from an idle,
    cooled machine, and the published figure is the idle one with the degradation
    stated separately. This is a much larger effect than the 25 percent wall clock
    noise already documented for rendering.

13. **Measured speech settings, best of 3 on 399.4s of real narration, base int8.**
    Baseline is greedy, no word timestamps, engine chosen thread count.

    | change | decode | cues | notes |
    | ------ | ------ | ---- | ----- |
    | baseline | 45.7s | 86 | 0.9 percent word error rate |
    | `beam_size=5` | 53.0s | 88 | the library default, 16 percent slower for nothing |
    | `word_timestamps=True` | 46.0s | 83 | 23 percent, so it is enabled only when reshaping needs it |
    | `cpu_threads=2` | 44.9s | 86 | 20 percent slower |
    | `cpu_threads=8` | 43.4s | 86 | 16 percent slower, hyperthreads do not help |
    | `batch_size=8` | 34.3s | 90 | fastest, but see finding 10 |

    Conclusions baked into the defaults: greedy decoding, word timestamps off unless
    reshaping asks for them, and `cpu_threads=0` so CTranslate2 picks the physical core
    count itself. Pinning the thread count measured slower in both directions.

14. **`small` is a bad deal on this machine, and only measuring showed it.** Measured on
    a 120s excerpt so all three models fit in one sitting without throttling distorting
    the comparison:

    | model | decode | realtime | word error rate |
    | ----- | ------ | -------- | --------------- |
    | tiny | 17.1s | 7.0x | 5.5 percent |
    | base | 19.8s | 6.0x | 2.7 percent |
    | small | 140.6s | 0.9x | 2.7 percent |

    `small` is seven times slower than `base`, drops below realtime, and was **no more
    accurate at all** on this narration. The intuition that a bigger model is a
    straightforward accuracy upgrade does not survive contact with a 15W CPU. `base`
    stays the default and the README says plainly that `small` is usually not worth it.
    `tiny` is barely faster than `base` for double the errors, so it has no sweet spot
    here either.
