# img2vid

Turn narration audio and one image per spoken line into a finished MP4, from your
browser, entirely on your own machine.

img2vid listens to the narration, writes down what is said and exactly when, and holds
each image on screen from its own line's timestamp until the next one. You see every
line of the narration next to its image before anything is built, fix what is missing
by dragging images into place, then build the video and download it.

```
Run.bat  ->  your browser  ->  narration + images  ->  finished MP4
```

- **Offline and private.** The speech model runs on your CPU. No audio or image leaves
  the machine, there is no account and no API key.
- **Exact.** Every image lands on an exact frame boundary, and the video is exactly as
  long as the narration.
- **Fast.** All heavy work goes to ffmpeg, spread over your CPU cores, with the fastest
  encoder your machine has chosen by timing them. A 3.5 minute narration with 54 images
  builds in under a minute on a 15 watt laptop.
- **Safe with gaps.** Each image is placed on the line its filename number names, so a
  missing image leaves one gap instead of shifting every later image onto the wrong
  words. Nothing is built with a black gap until you say so.

## Contents

- [Why this exists](#why-this-exists)
- [Installation](#installation)
- [Using img2vid](#using-img2vid)
- [How images are matched to lines](#how-images-are-matched-to-lines)
- [Naming images from an image generator](#naming-images-from-an-image-generator)
- [Transcript formats](#transcript-formats)
- [What Setup.bat installs](#what-setupbat-installs)
- [How it works](#how-it-works)
- [Performance](#performance)
- [Project layout](#project-layout)
- [For developers](#for-developers)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [The developer](#the-developer)

## Why this exists

Assembling a narrated slideshow by hand in a video editor is slow and repetitive work.
Once you have a transcript, the edit is fully determined: the timing is in the
transcript and each line already has its picture. Nothing about it needs a human, so
img2vid does that assembly for you.

Producing the transcript used to be the manual step that remained, which is why the
speech to text step exists. It runs a Whisper model locally, so the timing that drives
the whole edit comes from the narration itself rather than being typed out.

The web app exists because the one thing that still needed a person was checking that
every image sat on the right line. The storyboard shows exactly that, line by line,
before a single frame is encoded.

## Installation

Written for someone who has never used GitHub or a command prompt. Follow it in order.

You do **not** need to install Python, ffmpeg, Node.js or anything else beforehand, and
you do not need administrator rights. Everything lands inside one folder, and deleting
that folder removes every trace.

Requirements: Windows 10 or 11, about 2 GB of free disk space, and an internet
connection for the first setup only.

### Step 1: Get the files

**Option A: download the ZIP**

1. Open **https://github.com/m-abdullah-awais/img2vid** in your browser.
2. Click the green **Code** button, then **Download ZIP**.
3. Right click the ZIP file and choose **Properties**. If you see an **Unblock**
   checkbox at the bottom, tick it and click **OK**. This stops Windows warning you
   about every file inside it later.
4. Right click the ZIP again, choose **Extract All**, then **Extract**.
5. Move the extracted folder somewhere simple, such as `D:\img2vid`.

Extract it before you run anything. Double clicking a file inside the ZIP window makes
Windows unpack it into a temporary folder that it throws away afterwards, so setup
would appear to do nothing. `Setup.bat` detects this and tells you.

**Option B: clone with Git**, if you already have Git:

```
git clone https://github.com/m-abdullah-awais/img2vid.git
```

Choose a normal local folder. Avoid OneDrive, Dropbox or Google Drive: they sync every
temporary file written while a video builds, which slows it down and can lock files
mid render.

### Step 2: Run Setup.bat, once

1. Open the folder. The only two things you ever double click are **Setup.bat** and
   **Run.bat**.
2. Double click **Setup.bat**. If Windows shows *"Windows protected your PC"*, click
   **More info**, then **Run anyway**.
3. It explains what it is about to do. Press **Enter** to start, or type `N` to cancel.
4. Leave it to finish. You are looking for:

```
  ============================================================
  Setup complete. Nothing was installed system wide.
```

The first run downloads up to about 450 MB, and only what your machine is missing. If
it is interrupted, run it again: it carries on from where it stopped.

### Step 3: Run Run.bat

Double click **Run.bat**. A window opens, and a few seconds later img2vid opens in your
browser:

```
  img2vid
  ------------------------------------------------------------
  engine    : http://127.0.0.1:8765
  web app   : http://127.0.0.1:3000

  img2vid is running. Keep this window open while you work.
  Close it, or press Ctrl+C, to stop img2vid.
```

Keep that window open while you work. Closing it stops img2vid, including any video
still being built. Double clicking Run.bat again while it runs simply opens the app.

## Using img2vid

Everything happens in the browser. You never need to open a project folder.

### Projects

The first page lists your projects, newest first, each with its state in plain words:
*Needs narration*, *3 images missing*, *Ready to build*, *Video built*. Click
**New project**, give it a name, and it opens.

Each video is its own project with its own narration, transcript, images and finished
videos, so starting the next video never touches the last one.

### The four steps

A project opens on a strip of four steps, in the order you work through them. Each one
says what it has and offers what to do next:

| step | what it holds | what you can do |
| --- | --- | --- |
| **1 Narration** | the audio, with its length | **Upload narration**: one or more audio files, joined in name order |
| **2 Transcript** | the timed lines | **Transcribe** the narration, **Upload** your own, **Edit** it, **Download** it as SRT or TXT |
| **3 Images** | how many lines have their image | **Add images**, or drop them straight onto lines |
| **4 Video** | the newest video, or what stands in the way | **Build video** |

### Previewing the video while you arrange it

Below the strip is the **editor**: a live preview of the video with a timeline under it,
so you can watch the result of every change without building anything.

- **The preview** plays your narration and shows each line's image the moment that line
  is spoken, exactly as the finished video will: same shape, same letterbox or crop, and
  black on a line with no image. The line being spoken is shown under the picture, so
  you can check that words and image belong together.
- **The controls** play and pause, step to the previous or next line, and show the time
  and *Line 12 of 54*. **Undo** and **redo** cover every arrangement.
- **The timeline** shows the whole narration at first. Zoom in with **+** and **-**, or
  hold Ctrl and scroll. The *Images* track has one clip per line, as wide as the line
  lasts, with its length and start time, and a line still waiting for its image is
  hatched in amber. The *Voice* track is the narration's waveform, so pauses are easy to
  see. Click or drag anywhere on the timeline to jump there.
- **Arrange right on the timeline.** Drag a clip onto another to swap them, or onto the
  line between two clips to insert it. Drop a file from your computer onto a clip to put
  it on that line. The preview updates at once and keeps playing from the same moment.
- **The panel beside the preview** shows the selected line in full: its time, image,
  narration and file name, with **Replace**, **Remove** and **Move to line**.

Keyboard: **Space** plays and pauses, **Left** and **Right** step between lines,
**Home** and **End** jump to the start and end, **Ctrl+Z** undoes, **Ctrl+Y** or
**Ctrl+Shift+Z** redoes, **+** and **-** zoom.

The preview renders nothing: your browser plays the narration and shows the images. It
is instant, keeps working while a video builds, and never slows a build down. Timing
always comes from the narration, and the video cuts straight from one image to the next,
as it is built.

### Transcribing

**Transcribe** opens a short dialog:

- **Model.** `base` is the right choice almost always. `tiny` is a little faster and
  makes about twice the mistakes. `small` is several times slower and, on the machines
  measured, no more accurate. See [Performance](#performance).
- **Language.** Detected automatically, or set it yourself.
- **Line length.** One line becomes one image, so this is how many images the video
  needs. Longer lines mean fewer images.

It runs on your computer, at roughly one minute of work for every six to eight
minutes of narration. A previous transcript is kept in the trash and can be restored.

### Adding and arranging images

The **storyboard** lists every line with its number, timecode, narration and image, as
a list or as a contact sheet grid. **Missing** filters it to the lines still waiting.

- **Add images** uploads any number at once. Files whose names start with a number go
  onto that line (see [How images are matched to lines](#how-images-are-matched-to-lines)).
- **Drop a file from your computer onto a line** and it lands on exactly that line.
- **Drag an image onto a line** to move it there. If that line already has an image,
  the two swap and nothing else moves.
- **Drag an image between two lines** to insert it there. The images below move down
  one line each, and the shift stops at the first empty line, so nothing past a gap
  is disturbed. If there is no empty line to absorb it, the drop is refused and the
  app says why.
- While you drag, the target says exactly what will happen: *Move to line 12*,
  *Swap with line 12*, *Insert here, lines 13 to 20 move down*.
- From the keyboard: **Alt+Up** and **Alt+Down** swap an image with its neighbour, and
  each image's menu has **Move to line**.
- **Renumber** renames every image `001`, `002`, `003` in an order you choose: date
  created, date modified, name, size, type or a repeatable shuffle. It previews every
  rename first and warns if any image would change lines.

Every arrangement, removal and replacement shows an **Undo**. Removed files go to the
trash for seven days rather than being deleted.

### Building the video

**Build video** asks for the frame rate, size and fit:

- **Frame rate** 30, 25, 24 or 15. 15 builds noticeably faster and looks identical for
  still images.
- **Size** 1920x1080, 1280x720, or 1080x1920 for vertical video.
- **Fit** letterbox, which shows the whole image on a coloured background, or fill and
  crop.

If any line has no image, the build stops and lists every such line with its timecode
and narration, and offers **Add images first** or **Build with 3 black lines**. A black
screen is a real edit to your video, so it is never assumed.

While it builds, a bar at the bottom of every page shows the progress, the time left
and the engine's log, with **Cancel**. When it finishes you get **Play** and
**Download** right there, and the video is listed in the project with its length and
size. Videos are named for when they were built, so a second attempt never replaces
the first.

### System

The **System** page shows what img2vid is running on: Python, ffmpeg, Node.js, the
encoder it chose, the speech engine and its models, and the space used. It can download
another speech model and run a self test that builds a short video and checks it frame
by frame. Installing Python, ffmpeg or the speech engine is Setup.bat's job.

## How images are matched to lines

**A numbered image goes on the line its number names.** `004.jpg` is the image for the
fourth transcript line, whether or not `003.jpg` exists. Only the number at the front is
read, so the rest of the name is yours: `004. two men talking.jpg` is line 4 as well.

That matters when an image is missing. Pairing purely by position has no error detection
in it: an image that was never made is not a hole in the list, it is an absence, so
every later image slides one line earlier and the rest of the video runs against the
wrong narration. Numbering by line keeps the gap local. The line with no image is a
black screen for its full length, and every other line stays where it belongs.

**An unnumbered folder is paired by position.** Images are sorted in natural filename
order, so `2.png` comes before `10.png`, and the first image goes with the first line.
Numbering needs every name to start with a number and no name to claim a line past the
end of the transcript, so a folder of camera names such as `IMG_20260401_182233.jpg` is
read in order rather than scattered. The app shows a banner naming the file that put the
folder in this mode, and offers **Renumber**. The first time you drag an image in such a
folder, it offers to number the images in their current order first.

Two images cannot claim the same line. `4.jpg` and `004.png` together are flagged on
that line and block the build until one is moved or removed.

Supported: `png`, `jpg`, `jpeg`, `webp`, `bmp`, `tif`, `tiff`. Sizes, formats and
orientations can be mixed freely.

## Naming images from an image generator

If you generate images from a list of prompts, ask the generator to start each file
name with the prompt's line number, padded to three digits: `001`, `002`, `003`. A name
such as `004._00-08.png_202609061351.jpeg` still lands on line 4, because only the
leading number is read.

Two things worth adding to such a prompt:

- The number is for the file name only. Tell it never to draw the number, the
  timestamp or the file name inside the picture, especially if your style asks for
  hand lettered text.
- A timestamp alone is not a good file name. Two lines can start in the same second,
  and then both images claim one line.

## Transcript formats

Transcripts you upload can be any of these, detected automatically.

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

- Only the **start** time of each line is used. Each image runs until the next line
  starts, which guarantees there are no gaps between images.
- The **last** line runs until the narration ends, which is why the audio fixes the
  total length of the video.

## What Setup.bat installs

Setup checks what the machine already has and fills in only what is missing:

| dependency | if already present | if missing |
| --- | --- | --- |
| Python 3.8 or newer | uses the one on `PATH` | unpacks a private copy into `backend\runtime\python` |
| ffmpeg and ffprobe | uses the ones on `PATH` | unpacks them into `backend\runtime\bin` |
| Node.js 20 or newer | uses the one on `PATH` | unpacks a private copy into `backend\runtime\node` |
| the web app | | installs its packages into `frontend\node_modules` and builds it |
| speech to text engine | uses the copy in `backend\runtime\whisper` | installs it there, about 140 MB |
| speech model | uses the copy in `backend\runtime\whisper\models` | downloads `base`, about 140 MB |

**Nothing is installed system wide.** No installer runs, no `PATH` is changed, no
registry keys are written, and administrator rights are not needed. npm's download
cache goes to `backend\runtime\npm-cache` and Next.js telemetry is switched off, so
nothing is written to your user profile either.

```
Setup.bat                  use what the machine has, fetch only what is missing
Setup.bat --local          ignore the system copies and fetch everything locally,
                           so the folder is fully self contained
Setup.bat --check          report what is installed and change nothing
Setup.bat --no-transcribe  skip the speech engine, video assembly only
Setup.bat --model tiny     pre-download a different model size
```

Setup finishes by building a small test video, checking it frame by frame, and running
a decode through the speech model, so it only reports success if the machine can
genuinely do the work.

A copy set up before the web app kept its private tools in `runtime\` and `bin\` at the
top of the folder, and its files in `input\` and `output\`. Setup.bat and Run.bat move
the tools into `backend\runtime` instead of downloading them again, and the first start
imports the old files as a project named after the narration.

**Moving to another machine.** Copy the whole folder across and run `Setup.bat` there.
The speech engine contains compiled extensions built for one Python version, so Setup
reinstalls it if the interpreter differs.

## How it works

### Three pieces

```
browser                      frontend\     Next.js web app, served on 127.0.0.1:3000
  |  JSON over HTTP
  v
backend\api\                 the API, Python standard library only, on 127.0.0.1:8765
  |  runs the same scripts a terminal would
  v
backend\cli\ + backend\i2v\  the engine: ffmpeg orchestration and speech to text
```

`Run.bat` starts the API in a thread and the web app as a child process, in one window,
and both stop when it closes. The API only answers requests addressed to `127.0.0.1` or
`localhost`, from a local page, and anything that changes state must be sent as JSON.
Nothing on your network can reach it.

Builds and transcriptions run as child processes of the same scripts you can run from a
terminal, with the same default settings, one at a time. The web app only starts them
and reads their progress, which is why a video builds just as fast from the browser as
from the command line.

### Speech to text

1. **Gather the narration** in name order. Several files are joined with the ffmpeg
   concat filter into one 16 kHz mono track first, which keeps timestamps continuous
   across files and matches what the model resamples to anyway.
2. **Decode with faster-whisper** on the CPU with `int8` weights, with voice activity
   detection skipping silence.
3. **Hold every timestamp inside the audio.** Whisper routinely overshoots the true end
   of the file on the final segment, so times are clamped to the measured duration.
4. **Reshape the lines** when a line length is set, merging short lines before
   splitting long ones.
5. **Write SRT, TXT and JSON.** The SRT is what the video step reads.

### Video assembly

1. **Parse the transcript** into start times, and **probe the audio** with ffprobe. The
   total audio length is the end of the final line.
2. **Place each image** on the line its number names, or by position for an unnumbered
   folder.
3. **Quantise to frames.** Each boundary is rounded to a frame once and shared by the
   lines on either side of it:

   ```
   frames[i] = round(end[i] * fps) - round(start[i] * fps)
   ```

   Rounding error cannot accumulate, and the frames sum to exactly
   `round(total_audio * fps)`.
4. **Encode chunks of consecutive images concurrently** to MPEG-TS. Within a chunk each
   image is decoded and scaled once, then repeated for an exact number of frames by the
   `loop` filter, with the frame count pinned by `-frames:v`.
5. **Join and mux.** The parts are joined with a stream copy, which re-encodes nothing,
   and the audio is laid over the top.

**Why not a single concat demuxer pass.** It was built, measured and rejected. The
concat demuxer stores durations in whole microseconds, and a 30 fps frame boundary
falls at 33333.33 microseconds, which is not representable. Boundaries moved by a frame
either way, the final entry ignored its duration outright, and the whole stream came out
one frame early. The chunked approach is exact by construction, and it is also what
makes the work parallel.

**Choosing the encoder.** On first use every H.264 encoder the machine has is timed on a
short burst of still frames, and the faster one is kept. On the development machine
software `libx264` beat Intel Quick Sync, 393 fps against 255, which is the opposite of
what you would guess. The software encoder runs at `-preset ultrafast`, twice as fast as
`veryfast` for a file about 7 percent larger, because consecutive frames are identical
and the slower presets only buy better motion estimation.

**Colour.** Every image is forced to `rgb24` on the way in and converted to limited
range bt709 on the way out. A JPEG decodes as full range and a PNG as limited range, so
without pinning both ends a video mixing them shows a visible brightness jump.

## Performance

Machine for every number below: Intel i7-8650U, 4 cores and 8 threads at 15 W, no
discrete GPU. Each configuration was run several times and the fastest run is reported,
because wall clock on this machine is noisy enough that a single measurement can be a
quarter out.

### The web app costs nothing measurable

A 3 minute 27 second narration with 54 images at 1920x1080 and 30 fps, built alternately
from the terminal and from the browser so that heat affected both equally:

| | best of 4 |
| --- | --- |
| terminal, `img2vid.py` | 52.0 s |
| browser, Build video | 52.9 s |

Transcribing the same narration, best of 2: 29.5 s from the terminal and 29.6 s from the
browser. Both differences are smaller than the spread between identical runs.

### Speech to text

Material: a real 399.4 second narration, `base` model, `int8`, greedy decoding.

| change | decode | against baseline | lines | word error rate |
| --- | --- | --- | --- | --- |
| **baseline** | **45.7 s** | | **86** | **0.9%** |
| beam of 5 | 53.0 s | 16% slower | 88 | not measured |
| word timestamps | 46.0 s | 23% slower | 83 | not measured |
| 2 threads | 44.9 s | 20% slower | 86 | not measured |
| 8 threads | 43.4 s | 16% slower | 86 | not measured |
| batch of 8 | 34.3 s | 25% faster | 90 | 4.3% |

That is about 8x realtime. Greedy decoding is the default because a beam of 5 costs 16
percent for no visible gain. Word timestamps are only switched on when line reshaping
needs them. Batched decoding is faster but makes nearly five times the mistakes, which
is the wrong trade for a transcript that is both the timing and the script.

**Which model to use**, on a 120 second excerpt:

| model | decode | realtime | word error rate | on disk |
| --- | --- | --- | --- | --- |
| `tiny` | 17.1 s | 7.0x | 5.5% | 75 MB |
| **`base` (the default)** | **19.8 s** | **6.0x** | **2.7%** | **140 MB** |
| `small` | 140.6 s | 0.9x | 2.7% | 484 MB |

`small` is seven times slower here, drops below realtime, and was no more accurate than
`base`. `tiny` saves a little time for twice the errors.

**Thin laptops throttle.** Sustained decoding is exactly the heavy work that exhausts a
15 W budget. A single run on an idle machine takes the time above, but back to back runs
can take two to three times longer. A desktop with real cooling does not behave this way.

### Video assembly

Fixture: 100 images rendered to 200 seconds of 1920x1080, 6000 frames.

**How many encoder processes to run.** One per core is the intuitive answer and it is
wrong, because libx264 already threads across every core by itself:

| jobs | best | spread over 3 runs | realtime |
| --- | --- | --- | --- |
| 1 | 40.3 s | 37% | 5.0x |
| 2 | 41.3 s | 6% | 4.8x |
| **4 (the default, half the cores)** | **37.2 s** | **2%** | **5.4x** |
| 8 | 43.5 s | 8% | 4.6x |

**Frame rate is the biggest lever you control:**

| configuration | best | realtime |
| --- | --- | --- |
| 30 fps | 31.8 s | 6.3x |
| 15 fps | 24.7 s | 8.1x |
| 10 fps | 21.8 s | 9.2x |
| forced Quick Sync, 3 jobs | 44.7 s | 4.5x |

A still slideshow loses nothing visually at a lower frame rate, so 15 fps is close to
free. Halving the frame rate does not halve the time, because decoding the images,
starting processes and muxing are fixed costs.

## Project layout

```
Run.bat                 start img2vid, the one thing to double click day to day
Setup.bat               the one time setup
README.md  LICENSE
backend\
  api\                  the HTTP API the web app talks to, standard library only
  cli\                  the scripts the API runs, also usable from a terminal
    img2vid.py          build a video
    transcribe.py       narration to transcript
    rename_images.py    renumber a folder of images
    setup_check.py      the self test
    setup_speech.py     fetch a speech model
    start.py            what Run.bat runs
  i2v\                  the engine: transcript parsing, placement, timeline, ffmpeg,
                        speech to text, and paths.py, which names every folder
  runtime\              private Python, ffmpeg, Node.js and speech engine, if needed
  storage\              your projects, their uploads and videos, and the trash
frontend\
  src\app\              the pages: projects, a project, system, about the developer
  src\components\       the editor (preview and timeline), storyboard, dialogs and job dock
  src\lib\              the API client, its types and formatting
```

`backend\runtime` and `backend\storage` are created on your machine and are not part of
the repository. Everything you make lives in `backend\storage\projects`, one folder per
project.

## For developers

**Run the web app in development mode** with live reload:

```
Run.bat --dev
```

**Use the engine directly**, without the web app:

```
python backend\cli\transcribe.py -a narration.wav --out-dir .\transcript
python backend\cli\img2vid.py -t script.srt -i .\images -a narration.wav -o video.mp4
python backend\cli\rename_images.py -f .\images --dry-run
```

`img2vid.py --help` lists every option, including `--fps`, `--size`, `--fit`, `--bg`,
`--dry-run` to print the timeline without encoding, `--allow-black` to confirm missing
lines in advance, and `--force` to build an unnumbered folder whose count does not
match. `--force` deliberately does not cover missing lines.

**Run the API on its own**, against a scratch storage folder so your projects are not
touched:

```
python backend\api --port 8765 --storage D:\scratch
```

**Stack.** Next.js 16 with the App Router, React 19, TypeScript and Tailwind CSS 4 for the
frontend, with `@dnd-kit/core` for dragging and `lucide-react` for icons. The backend is
Python 3.8 or newer and its standard library, driving ffmpeg, with faster-whisper for
speech to text.

## Troubleshooting

**"The img2vid engine is not running"**
The browser tab outlived the Run.bat window. Double click **Run.bat** again, then press
**Retry**.

**Run.bat says Python, ffmpeg or Node.js was not found**
Run **Setup.bat**. It uses whatever the machine already has and fetches only the missing
piece, into this folder.

**Run.bat says port 8765 is in use**
Another program is using the port img2vid needs. Close it, or restart Windows. A second
copy of img2vid is detected and simply reopened, so that is not the cause.

**"The speech engine is not installed"**
Run **Setup.bat**. If you only want to build videos from transcripts you already have,
this does not affect you: upload the transcript instead.

**"The speech engine was installed for Python 3.12 but this is Python 3.14"**
The engine is built for one Python version. This happens after installing or removing a
system Python, or copying the folder from another machine. Run **Setup.bat** again.

**"429 Too Many Requests" while fetching a model**
huggingface.co is rate limiting. img2vid waits this out for you, six attempts over about
four minutes. If it still fails, try again later, or copy the folder
`backend\runtime\whisper\models\models--Systran--faster-whisper-base` from a machine
where it works.

**"No speech was found"**
Check that the audio really is narration rather than music or silence, and that it plays.

**The transcript has too few or too many lines for the images you have**
Lines follow natural pauses. Transcribe again with a different line length.

**Build asks about black lines you did not expect**
Those lines have no image, usually because a file name does not start with that line's
number. Filter the storyboard to **Missing** to see them, then drop the right images
onto them.

**"This folder is paired by position"**
At least one image name does not start with a number, or its number is past the last
line. The banner names the file. Use **Renumber**, or rename that one file.

**"Two images claim this line"**
Two files start with the same number. Drag one of them to its correct line, or remove it.

**"The audio is Xs long but the last transcript timestamp is at Ys"**
The narration has to run past the last line. Check that every narration file is
uploaded, and that the transcript belongs to this narration.

**The wrong encoder seems to be chosen**
The timing result is kept in `backend\storage\work\.encoder.json`. Delete that file to
time the encoders again. Software x264 legitimately beats Quick Sync on many machines
for still images.

---

## Contributing

Issues and pull requests are welcome. If a transcript comes out wrong, a build fails,
or Setup cannot get going on your machine,
[open an issue](https://github.com/m-abdullah-awais/img2vid/issues) with what you did and
what it said. For a timing problem, the log from the job dock is the most useful thing
you can paste in.

## License

Released under the [MIT License](LICENSE). Use it, learn from it, build on it.

Nothing third party is redistributed in this repository. ffmpeg, Node.js, the npm
packages and the speech model are downloaded at install time and stay in your copy of
the folder, so their licences are between you and them: ffmpeg builds are GPL, Next.js,
React, faster-whisper and the Whisper models are MIT.

---

<div align="center">

## The developer

### Muhammad Abdullah Awais

**Full Stack Developer**

I build fast, clean, practical tools that scratch a real itch. img2vid came straight out
of one of mine. I had the narration, I had the images, and I was still sitting in a video
editor dragging clips around to line them up by hand. The timing was already sitting in
the transcript, so the computer should have been doing that work. Now it does, in about a
minute, and every image lands on an exact frame.

🌐 [www.abdullahawais.com](https://www.abdullahawais.com) &nbsp;&nbsp;|&nbsp;&nbsp; 📧 [contact@abdullahawais.com](mailto:contact@abdullahawais.com)

<p>
  <a href="https://www.abdullahawais.com"><img src="https://img.shields.io/badge/Website-05A081?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website" /></a>
  <a href="https://github.com/m-abdullah-awais"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub" /></a>
  <a href="https://www.linkedin.com/in/m-abdullah-awais-programmer"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>
  <a href="https://www.youtube.com/@m_abdullah_awais"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube" /></a>
  <a href="https://www.instagram.com/m_abdullah_awais"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram" /></a>
  <a href="mailto:contact@abdullahawais.com"><img src="https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white" alt="Email" /></a>
</p>

The app has the same details on its **About the developer** page.

</div>

---

<div align="center">

### Found img2vid useful?

If it saved you an afternoon in a video editor, a star on the repo genuinely helps other
people find it.

<a href="https://github.com/m-abdullah-awais/img2vid">
  <img src="https://img.shields.io/github/stars/m-abdullah-awais/img2vid?style=for-the-badge&logo=github&color=05A081&labelColor=181717" alt="Star this repo on GitHub" />
</a>

<br />
<br />

<sub>Built with care by <a href="https://www.abdullahawais.com"><b>Muhammad Abdullah Awais</b></a></sub>

<br />

<sub><b>Runs entirely on your machine.</b> Your narration and images are never uploaded
anywhere, there is no account and no API key, and the speech model runs locally. img2vid
is an independent tool and is not affiliated with OpenAI, the ffmpeg project, Vercel, or
any other party whose work it builds on.</sub>

</div>
