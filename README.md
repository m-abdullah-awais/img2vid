# img2vid

Turn a timestamped transcript, a folder of images and one or more audio files into a
finished MP4. Each image is held on screen from its own timestamp until the next one,
and the last image runs until the audio ends.

Built for speed. All heavy lifting is delegated to ffmpeg, work is spread across CPU
cores, and hardware encoding is used when the machine has it.

```
python img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
```

Or just double click **Run.bat** and let it find your files for you.

## Contents

- [Why this exists](#why-this-exists)
- [Requirements](#requirements)
- [Run.bat, the no arguments way](#runbat-the-no-arguments-way)
- [Quick start](#quick-start)
- [Transcript formats](#transcript-formats)
- [Matching images to timestamps](#matching-images-to-timestamps)
- [Command reference](#command-reference)
- [How it works](#how-it-works)
- [Performance](#performance)
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

## Requirements

- Python 3.8 or newer. The standard library only, no third party packages.
- ffmpeg and ffprobe on `PATH`, or placed in a `bin` folder next to `img2vid.py`.

There is nothing to install. No virtual environment, no `pip install`, no
`node_modules`. Clone or copy the folder and run it.

Verify your setup:

```
ffmpeg -version
python img2vid.py --version
```

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
  3  3.png                               7.100     20.000  12.900      387
  -----------------------------------------------------------------------
  segments: 3   audio: 20.000s   video: 20.000s   frames: 600 @ 30 fps
  encoder: qsv   chunks: 1   jobs: 1
```

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
| `--encoder` | `auto` | `auto`, `qsv` (hardware) or `x264` (software) |
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

### Colour handling

Every image is forced to `rgb24` on the way in and converted to limited range bt709
on the way out. This matters because a JPEG decodes as full range `yuvj420p` while a
PNG decodes as limited range `yuv420p`. Without pinning both ends, chunks built from
different source formats end up with different colour ranges, and stream copying them
together produces a visible brightness jump partway through the video.

## Performance

Measured on the included 300 image, 10 minute benchmark fixture at 1920x1080 and
30fps, which is 18000 output frames. Machine: 8 logical cores, Intel Quick Sync
available, no discrete GPU.

BENCHMARK_TABLE_PLACEHOLDER

Reproduce it yourself:

```
python temp/make_fixture.py --big
python temp/benchmark.py
```

Notes on tuning:

- **Quick Sync is one fixed function engine.** Running many sessions against it does
  not make it finish sooner, so `--jobs 0` caps hardware encoding at a small number
  of processes. Software encoding is the case that scales with cores.
- **Lowering `--fps` is the single biggest lever.** A still slideshow loses nothing
  visually at a lower frame rate, and `--fps 10` cuts the frame count by two thirds.
  YouTube accepts it.
- **`--chunk-size` trades process startup against filter graph size.** Each image in
  a chunk costs one decoder, so very large chunks slow the graph down while very
  small ones pay process startup repeatedly. The default sits in the flat part of
  that curve.

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

**`ffmpeg was not found`**
Install ffmpeg and put it on `PATH`, or drop `ffmpeg.exe` and `ffprobe.exe` into a
`bin` folder next to `img2vid.py`. The local copy takes priority.

**`Count mismatch: N transcript timestamps but M images`**
There must be exactly one image per transcript line. Check for a stray file in the
images folder, or a blank line that was parsed as a cue.

**`The audio is Xs long but the last transcript timestamp is at Ys`**
The audio has to run past the final timestamp, since the last image is held until the
audio ends. Check that you passed every audio file, and in the right order.

**`Timestamps N and N+1 are less than one frame apart`**
Two transcript lines are closer together than a single frame at the chosen frame
rate. Raise `--fps` or merge the two lines.

**Hardware encoding is not being picked up**
The result of the hardware probe is cached in `temp/.encoder.json`. Delete that file
to force a fresh probe, or pass `--encoder qsv` or `--encoder x264` to skip detection
entirely.

## Developer

**Muhammad Abdullah Awais**
Full Stack Developer

- Website: [www.abdullahawais.com](https://www.abdullahawais.com)
- Email: [contact@abdullahawais.com](mailto:contact@abdullahawais.com)
- LinkedIn: [m-abdullah-awais-programmer](https://www.linkedin.com/in/m-abdullah-awais-programmer)
- GitHub: [m-abdullah-awais](https://github.com/m-abdullah-awais)
- YouTube: [@m\_abdullah\_awais](https://www.youtube.com/@m\_abdullah\_awais)
- Instagram: [m\_abdullah\_awais](https://www.instagram.com/m\_abdullah\_awais)
