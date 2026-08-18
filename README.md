# img2vid

Turn a timestamped transcript, a folder of images and one or more audio files into a
finished MP4. Each image is held on screen from its own timestamp until the next one,
and the last image runs until the audio ends.

Built for speed. All heavy lifting is delegated to ffmpeg, work is spread across CPU
cores, and the fastest encoder your machine has is chosen by timing them rather than
by guessing.

```
python img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
```

Or just double click **Run.bat** and let it find your files for you.

## Contents

- [Why this exists](#why-this-exists)
- [Setup](#setup)
- [Run.bat, the no arguments way](#runbat-the-no-arguments-way)
- [Quick start](#quick-start)
- [Transcript formats](#transcript-formats)
- [Matching images to timestamps](#matching-images-to-timestamps)
- [Command reference](#command-reference)
- [How it works](#how-it-works)
- [Performance](#performance)
- [When the counts do not match](#when-the-counts-do-not-match)
- [Stopping a render](#stopping-a-render)
- [Verification](#verification)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Developer](#developer)

## Why this exists

Assembling a narrated slideshow by hand in a video editor is slow and repetitive work.
The transcript already contains the timing, and the images are already in the right
order, so the edit is fully determined by data you have. This tool does that assembly
in one command.

Accuracy is the point as much as speed. Every image lands on an exact frame boundary,
and the total video length matches the total audio length to the frame.

## Setup

On a new machine, run **Setup.bat** once, then use **Run.bat**. That is the whole
procedure.

Setup checks what the machine already has and fills in only what is missing:

| dependency | if already present | if missing |
| --- | --- | --- |
| Python 3.8 or newer | uses the one on `PATH` | unpacks a private copy into `runtime\python` |
| ffmpeg and ffprobe | uses the ones on `PATH` | unpacks them into `bin` |

**Nothing is installed system wide.** No installer runs, no `PATH` is modified, no
registry keys are written, and administrator rights are not needed. Anything Setup has
to fetch lands inside this project folder, so deleting the folder removes every trace.

There are no `pip` packages to install at any point. The tool is Python standard library
only, which is why a bare embeddable Python is enough.

Options:

```
Setup.bat              use what the machine has, fetch only what is missing
Setup.bat --local      ignore the system copies and fetch both locally, so the
                       folder is fully self contained and portable
Setup.bat --check      report what is installed and change nothing
```

Setup finishes by rendering a small test video and checking it frame by frame, so it
only reports success if the machine can genuinely produce a correct video:

```
     [x] img2vid modules import
     [x] ffmpeg and ffprobe found  using PATH
     [x] child process guard available
     [x] an H.264 encoder works  libx264 selected
     [x] renders a video end to end
     [x] frame count is exact  120 frames, expected 120
     [x] each image is shown for the right number of frames
```

An internet connection is only needed if something is actually missing. Setup downloads
roughly 11 MB for Python and roughly 90 MB for ffmpeg, and only for the ones it needs.

### Moving to another machine

Copy the whole folder across and run `Setup.bat` on the new machine. If you want a copy
that works with no internet on the far side, run `Setup.bat --local` before you move it,
which brings Python and ffmpeg into the folder itself.

## Run.bat, the no arguments way

Double click **Run.bat**. The first run creates the folders it needs and tells you
what to put in them:

```
input\
  script.srt          your transcript, any of .srt .vtt .txt
  images\             one image per transcript line
  audio\              one or more audio files
```

Drop your files in, run it again, and the finished video appears in `output\` named
after the transcript. Audio files are joined in natural filename order, so
`part1.mp3`, `part2.mp3`, `part10.mp3` play in the order you would expect.

Run.bat also forwards any flags you give it, so this works too:

```
Run.bat --fps 10
Run.bat --force
```

If you launch it by double clicking there is nowhere to type a flag, so open Run.bat
in a text editor and put what you want on the `FLAGS` line near the top:

```
set "FLAGS=--force --fps 15"
```

It checks for Python and ffmpeg up front and tells you exactly what is missing rather
than failing with a stack trace.

## Quick start

For full control, call the tool directly. Arrange your inputs like this:

```
project\
  script.srt
  narration.mp3
  images\
    1.png
    2.png
    3.png
```

Then run:

```
python img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
```

Check the timing before committing to a render:

```
python img2vid.py -t script.srt -i .\images -a narration.mp3 --dry-run
```

`--dry-run` prints the resolved timeline and exits without encoding anything:

```
  #  image                              start        end     dur   frames
  -----------------------------------------------------------------------
  1  1.png                               0.000      3.400   3.400      102
  2  2.png                               3.400      7.100   3.700      111
  3  3.png                               7.100     11.900   4.800      144
  4  4.png                              11.900     15.267   3.367      101
  5  5.png                              15.267     20.000   4.733      142
  -----------------------------------------------------------------------
  segments: 5   audio: 20.000s   video: 20.000s   frames: 600 @ 30 fps
  encoder: x264   chunks: 3   jobs: 3
```

Note the frame counts add up to exactly 600, which is 20 seconds at 30fps. That is the
guarantee the frame quantiser gives you: the video cannot drift against the audio.

Several audio files are joined in the order you list them:

```
python img2vid.py -t script.srt -i .\images -a part1.mp3 part2.mp3 part3.mp3 -o video.mp4
```

## Transcript formats

The format is detected automatically. All three of these are accepted.

**SubRip (.srt)**

```
1
00:00:00,000 --> 00:00:03,400
The opening line of the script.

2
00:00:03,400 --> 00:00:07,100
The second line.
```

**WebVTT (.vtt)**

```
WEBVTT

00:00.000 --> 00:03.400
The opening line of the script.
```

**Plain text with leading timestamps**

```
[0:00] The opening line of the script.
[0:03.4] The second line.
1:07 Brackets are optional.
[01:02:03.250] Hours are supported.
```

Two rules apply to every format:

- Only the **start** time of each line is used. Any end times are ignored, and each
  image is extended to the start of the next one. This is deliberate: it guarantees
  there are no black gaps between images.
- The **last** line has no following timestamp, so it runs until the audio ends. This
  is why the audio is what fixes the total length of the video.

## Matching images to timestamps

Images are read from the folder given to `-i` and sorted in natural filename order,
so `2.png` comes before `10.png` rather than after it. The first image goes with the
first timestamp, the second with the second, and so on.

Supported extensions: `png`, `jpg`, `jpeg`, `webp`, `bmp`, `tif`, `tiff`. Formats,
sizes and orientations can be mixed freely within one folder.

The counts must match exactly. If they do not, the run stops with a message telling
you both numbers rather than silently producing a mistimed video.

By default images are letterboxed to fit the output frame without cropping
(`--fit contain`). Use `--fit cover` to fill the frame and crop the overflow instead,
and `--bg` to change the letterbox colour.

## Command reference

| Flag | Default | Description |
| --- | --- | --- |
| `-t`, `--transcript` | required | SRT, VTT, or plain text with leading timestamps |
| `-i`, `--images` | required | Folder of images, one per timestamp |
| `-a`, `--audio` | required | One or more audio files, joined in the order given |
| `-o`, `--output` | `output.mp4` | Output MP4 path |
| `--fps` | `30` | Output frame rate |
| `--size` | `1920x1080` | Output resolution, `WIDTHxHEIGHT` |
| `--fit` | `contain` | `contain` letterboxes, `cover` crops to fill |
| `--bg` | `black` | Letterbox colour used by `--fit contain` |
| `--jobs` | `0` | Concurrent encoder processes, `0` chooses automatically |
| `--chunk-size` | `24` | Images per encoder process |
| `--encoder` | `auto` | `auto` times both once and keeps the faster, or force `qsv` / `x264` |
| `--force` | off | Build anyway when the images and timestamps do not line up |
| `--dry-run` | off | Print the resolved timeline and exit |
| `--keep-temp` | off | Keep intermediate files in `temp/` for inspection |
| `--quiet` | off | Suppress progress output |

## How it works

1. **Parse the transcript** into a list of start times.
2. **Probe the audio** with ffprobe, concurrently across files, and sum the durations.
   That total becomes the end of the final segment.
3. **Quantise to frames.** Each boundary is rounded to a frame once and shared by the
   segments on either side of it:

   ```
   frames[i] = round(end[i] * fps) - round(start[i] * fps)
   ```

   Because a boundary is rounded once rather than per segment, rounding error cannot
   accumulate, and the frame counts sum to exactly `round(total_audio * fps)`.
4. **Split into chunks** of consecutive images, one ffmpeg process per chunk.
5. **Encode chunks concurrently** to MPEG-TS. Within a chunk each image is decoded
   once, scaled and padded once, then repeated for an exact number of frames by the
   `loop` filter. The output frame count is pinned with `-frames:v`, so a segment
   cannot drift.
6. **Join and mux.** The parts are concatenated with a video stream copy, which
   re-encodes nothing, and the audio is laid over the top.

### Why not a single concat demuxer pass

The obvious implementation is an ffconcat list of images with a duration per image.
It was built, measured and rejected. The concat demuxer stores durations in whole
microseconds, and a 30fps frame boundary falls at 33333.33 microseconds, which is not
representable. In testing this moved segment boundaries by a frame in either
direction, the final entry ignored its declared duration outright, and the whole
stream came out shifted one frame early.

The chunked approach is exact by construction instead of approximately right, and it
is also what makes the work parallel. Both goals are served by the same design.

### Choosing the encoder

On first run the tool times every H.264 encoder the machine actually has, on a short
burst of still frames, and keeps the faster one. The result is written to
`temp/.encoder.json` and reused from then on, so the cost is paid once.

This is measured rather than assumed on purpose. "Hardware is faster than software" is
not reliably true for still image content: a modest integrated GPU can lose to a strong
CPU, and the reverse is just as common. On the development machine software `libx264`
won at 393 fps against Quick Sync at 255 fps, which is the opposite of what you would
guess.

The software encoder runs at `-preset ultrafast`. That is deliberate, and measured: on
static 1080p frames it reaches 393 fps against 202 fps for `veryfast`, and the file is
only about 7 percent larger. The slower presets spend their time on motion estimation,
which buys nothing when consecutive frames are byte for byte identical.

### Colour handling

Every image is forced to `rgb24` on the way in and converted to limited range bt709
on the way out. This matters because a JPEG decodes as full range `yuvj420p` while a
PNG decodes as limited range `yuv420p`. Without pinning both ends, chunks built from
different source formats end up with different colour ranges, and stream copying them
together produces a visible brightness jump partway through the video.

## Performance

Machine: 8 logical cores, Intel Quick Sync available, no discrete GPU. Fixture: 100
images rendered to 200 seconds of 1920x1080, which is 6000 frames. Each configuration
was run three times and the fastest run is reported, because desktop wall clock is
noisy enough that a single measurement can be a quarter out.

**How many encoder processes to run.** One process per core is the intuitive answer and
it is wrong, because libx264 already threads across every core by itself.

| jobs | best | spread over 3 runs | realtime |
| --- | --- | --- | --- |
| 1 | 40.3s | 37% | 5.0x |
| 2 | 41.3s | 6% | 4.8x |
| **4 (the default, half the cores)** | **37.2s** | **2%** | **5.4x** |
| 8 | 43.5s | 8% | 4.6x |

Half the cores was both the fastest and by far the steadiest. This is what `--jobs 0`
now picks for software encoding. Hardware encoding is capped at 3 instead, since Quick
Sync is a single fixed function engine and extra sessions only queue up.

**Frame rate is the biggest lever you control.**

| configuration | best | realtime | size |
| --- | --- | --- | --- |
| default, 30fps | 31.8s | 6.3x | 5.7 MB |
| default, 15fps | 24.7s | 8.1x | 5.5 MB |
| default, 10fps | 21.8s | 9.2x | 5.6 MB |
| forced `--encoder qsv`, 3 jobs | 44.7s | 4.5x | 5.3 MB |
| forced `--encoder qsv`, 1 job | 64.0s | 3.1x | 5.3 MB |

A still slideshow loses nothing visually at a lower frame rate and YouTube accepts it,
so `--fps 15` is close to free. Note that halving the frame rate does not halve the
time: decoding and scaling the images, starting processes and muxing are fixed costs
that do not care how many frames come out the other end.

In round numbers on this machine, a **10 minute 1080p30 video renders in about 90 to
110 seconds**, and roughly 70 seconds at 15fps.

Reproduce it yourself:

```
python temp/make_fixture.py --medium
python temp/benchmark.py

python temp/make_fixture.py --big
python temp/benchmark.py --big --reps 2
```

Notes on tuning:

- **The encoder is the wall, not the orchestration.** Measured ceiling for a single
  process on static 1080p is 393 fps for x264 ultrafast and 255 fps for Quick Sync.
  The full pipeline runs close enough to that ceiling that there is no large win left
  in how the work is arranged.
- **`--chunk-size` trades process startup against filter graph size.** Each image in
  a chunk costs one decoder, so very large chunks slow the graph down while very
  small ones pay process startup repeatedly. The default sits in the flat part of
  that curve.
- **Benchmark on a quiet machine.** Anything else encoding at the same time will
  distort the result badly. This was learned the hard way.

## When the counts do not match

Normally the number of images must equal the number of transcript lines, and the run
stops if it does not. That is deliberate. If the tool quietly guessed, every image after
the missing one would be shown against the wrong line, and you would not find out until
you watched the finished video.

When you would rather have the video anyway, pass `--force`:

```
python img2vid.py -t script.srt -i .\images -a narration.mp3 --force
```

Run.bat will also offer it. If the counts do not match it prints the problem and asks
whether to continue, so a double click can recover without editing anything.

`--force` repairs four things, and says what it did each time:

| problem | what `--force` does |
| --- | --- |
| fewer images than timestamps | Pairs off as many as it can. The last image is held until the audio ends, absorbing the leftover timestamps. |
| more images than timestamps | Ignores the extra images at the end and names them. |
| audio stops before the last timestamp | Drops the timestamps that fall past the end of the audio. |
| two timestamps closer than one frame | Drops the shorter of the two. |

For example, 105 timestamps against 104 images gives:

```
  warning: --force: 105 timestamps but 104 images. Using the first 104 timestamps,
           so image 104 holds until the audio ends.
```

Two things worth knowing. `--force` changes nothing at all when the inputs already line
up, so it is safe to leave on. And it never breaks the timing guarantee: the frame counts
still add up to exactly the length of the audio, so the video cannot drift. It is only
the pairing of images to lines that is being repaired, never the clock.

It still refuses genuinely impossible input, such as audio that ends before the first
timestamp.

## Stopping a render

Closing the terminal window, or pressing Ctrl+C, stops everything. There are no
encoders left running in the background afterwards.

This needs saying because it is not what you get for free. Killing a Python process on
Windows does not reliably kill the ffmpeg processes it started, so the naive version of
this tool could leave several encoders burning CPU on a render whose output would never
be assembled. To prevent that, the orchestrator puts itself in a Windows job object with
`KILL_ON_JOB_CLOSE`, which makes the operating system terminate every child process the
moment the parent goes away, however it goes away.

Measured behaviour:

| how it ends | encoders left | temp left | notes |
| --- | --- | --- | --- |
| finishes normally | none | none | output written |
| terminal closed or process killed | none, immediately | one folder | swept on the next run |
| Ctrl+C or Ctrl+Break | none, within a few seconds | none | prints `cancelled`, exit code 130 |

The hard kill case was verified over four consecutive runs: four ffmpeg processes running,
zero remaining, every time.

A hard kill cannot run the normal cleanup, so it leaves one `temp/job_<pid>` folder behind.
The next run deletes any such folder whose process is no longer alive, so they do not
accumulate.

**There is no resume.** A stopped render is abandoned, not paused. Starting again begins
from the first frame. If you want a render to survive closing the window, do not close the
window: leave it open, or launch it detached with something like
`start /b python img2vid.py ...`.

## Verification

The test suite generates its own fixtures with ffmpeg, so no external assets are
needed:

```
python temp/make_fixture.py
python temp/verify.py
```

The fixture is deliberately awkward. It mixes PNG and JPEG, mixes landscape,
portrait and 4:3 images, uses timestamps that do not fall on whole frames, and splits
the narration across two audio files.

Each render is then checked by decoding the whole output and sampling one pixel per
frame, so the checks are exhaustive rather than sampled:

1. Container duration matches the audio.
2. The video holds exactly the expected number of frames.
3. Every single frame shows the image it should. Run length encoding the whole video
   and comparing against the expected frame counts means a boundary that is one frame
   early or late cannot pass.
4. The audio stream is present, AAC, 48kHz, stereo.
5. Serial and chunked runs, on both the hardware and the software encoder, agree
   exactly.

## Project layout

```
Run.bat               double click launcher, finds files in input\
run.py                zero argument launcher that Run.bat calls
img2vid.py            CLI entry point
i2v\
  cli.py              argument parsing, orchestration, progress output
  transcript.py       SRT, WebVTT and plain timestamp parsing
  probe.py            ffprobe helpers, encoder detection with an on disk cache
  render.py           timeline, filter graphs, chunked encoding and muxing
input\                created on first run, your source files
output\               created on first run, finished videos
runtime\              only if Setup had to fetch Python, a private copy
bin\                  only if Setup had to fetch ffmpeg
temp\
  make_fixture.py     fixture generator, small and benchmark sizes
  verify.py           end to end frame accurate verification
  benchmark.py        performance measurement
AGENTS.md             project memory and rules
README.md             this file
```

Everything the tool generates, including intermediates and test output, stays inside
`temp/`. Intermediates are cleaned up after each run unless `--keep-temp` is given.

## Troubleshooting

**`ffmpeg was not found`** or **`Python was not found`**
Run `Setup.bat`. It uses whatever the machine already has and fetches only the missing
piece, into this folder rather than system wide. If the machine has no internet, install
Python from python.org and put a Windows ffmpeg build's `ffmpeg.exe` and `ffprobe.exe`
into a `bin` folder next to `img2vid.py`.

**`Count mismatch: N transcript timestamps but M images`**
There must be exactly one image per transcript line. Check for a stray file in the
images folder, or a blank line that was parsed as a cue. Pass `--force` to build the
video anyway, or put `--force` on the `FLAGS` line in Run.bat.

**`The audio is Xs long but the last transcript timestamp is at Ys`**
The audio has to run past the final timestamp, since the last image is held until the
audio ends. Check that you passed every audio file, and in the right order.

**`Timestamps N and N+1 are less than one frame apart`**
Two transcript lines are closer together than a single frame at the chosen frame
rate. Raise `--fps` or merge the two lines.

**The wrong encoder is being chosen**
The timing trial result is cached in `temp/.encoder.json`, along with the measured
speed of each candidate. Delete that file to force a fresh trial, or pass
`--encoder qsv` or `--encoder x264` to skip detection entirely. Note that software
`x264` legitimately beats Quick Sync on many machines for this kind of content, so a
software pick is not necessarily a misdetection.

## Developer

**Muhammad Abdullah Awais**
Full Stack Developer

- Website: [www.abdullahawais.com](https://www.abdullahawais.com)
- Email: [contact@abdullahawais.com](mailto:contact@abdullahawais.com)
- LinkedIn: [m-abdullah-awais-programmer](https://www.linkedin.com/in/m-abdullah-awais-programmer)
- GitHub: [m-abdullah-awais](https://github.com/m-abdullah-awais)
- YouTube: [@m\_abdullah\_awais](https://www.youtube.com/@m\_abdullah\_awais)
- Instagram: [m\_abdullah\_awais](https://www.instagram.com/m\_abdullah\_awais)
