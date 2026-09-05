# img2vid

Turn narration audio and a folder of images into a finished MP4. Each image is held on
screen from its own timestamp until the next one, and the last image runs until the
audio ends.

Two steps, both offline and both built for speed:

```
Transcribe Audio.bat      narration        ->  timestamped transcript
Create Video.bat          transcript + images + audio  ->  MP4
```

Transcription runs a local Whisper model on the CPU, so nothing is uploaded and there
is no API key. Assembly delegates every heavy operation to ffmpeg, spreads the work
across CPU cores, and picks the fastest encoder your machine has by timing them rather
than by guessing.

If you already have a transcript, skip step one and run **Create Video.bat**. For full
control, both steps have a normal command line:

```
python app\transcribe.py --max-chars 90
python app\img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
```

## Contents

- [Why this exists](#why-this-exists)
- [Installation](#installation)
- [What Setup.bat installs](#what-setupbat-installs)
- [Transcribe Audio.bat](#transcribe-audiobat)
- [Create Video.bat](#create-videobat)
- [Rename Images.bat](#rename-imagesbat)
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
- [Contributing](#contributing)
- [License](#license)
- [The developer](#the-developer)

## Why this exists

Assembling a narrated slideshow by hand in a video editor is slow and repetitive work.
Once you have a transcript, the edit is fully determined: the timing is in the
transcript and the images are already in the right order. Nothing about it needs a
human. This tool does that assembly in one command.

Producing the transcript used to be the manual step that remained, which is why the
speech to text step exists. It runs a Whisper model locally, so the timing that drives
the whole edit is derived from the narration itself rather than typed out.

Accuracy is the point as much as speed. Every image lands on an exact frame boundary,
and the total video length matches the total audio length to the frame.

## Installation

Written for someone who has never used GitHub or a command prompt. Follow it in order
and you will have a finished video at the end.

You do **not** need to install Python, ffmpeg, or anything else beforehand. You do not
need administrator rights. Everything lands inside one folder, and deleting that folder
removes every trace.

Requirements: Windows 10 or 11, about 1 GB of free disk space, and an internet
connection for the first setup only.

### Step 1: Get the files

Pick one of the two options below. Option A needs no tools at all.

**Option A: download the ZIP**

1. Open **https://github.com/m-abdullah-awais/img2vid** in your browser.
2. Click the green **Code** button near the top right.
3. Click **Download ZIP**. A file called `img2vid-main.zip` lands in your Downloads.
4. Right click the ZIP file and choose **Properties**. If you see an **Unblock**
   checkbox at the bottom, tick it and click **OK**. This saves Windows from warning
   you about every file inside it later.
5. Right click the ZIP again, choose **Extract All**, then **Extract**.
6. You now have a folder named `img2vid-main`. Rename it to `img2vid` if you like, and
   move it somewhere simple such as `C:\Tools\img2vid` or `D:\img2vid`.

Extract it before you run anything. Double clicking inside the ZIP window works, but
Windows unpacks the file into a temporary folder first and throws that folder away
afterwards, so the setup appears to do nothing and no `input` folder ever shows up.
`Setup.bat` detects this and says so rather than letting you find out later.

**Option B: clone with Git**, if you already have Git installed:

```
git clone https://github.com/m-abdullah-awais/img2vid.git
cd img2vid
```

A note on where you put the folder. Choose a normal local folder. Avoid putting it
inside OneDrive, Dropbox or Google Drive: those sync every temporary file the tool
writes while it works, which makes it slower and can lock files mid render.

### Step 2: Run Setup.bat

1. Open the folder. Everything you ever double click is one of the four `.bat` files
   sitting at the top: **Setup.bat**, **Transcribe Audio.bat**, **Rename Images.bat**
   and **Create Video.bat**. The `app` and `i2v` folders are the program itself and you
   never need to open them.
2. Double click **Setup.bat**.
3. If Windows shows a blue box saying *"Windows protected your PC"*, click
   **More info**, then **Run anyway**. Windows shows this for any script downloaded
   from the internet. Step 1 point 4 usually prevents it.
4. A black window opens and explains what it is about to do. Press **Enter** to
   start, or type `N` and press Enter to cancel.
5. It reports progress as it goes. Leave it alone and let it finish.

**Every one of the four batch files asks first**, and tells you what it is about to do
before it does it. Nothing happens until you answer, so opening one out of curiosity
costs nothing: read the summary, then close the window or type `N`.

The first run downloads up to about 280 MB and takes a few minutes on a normal
connection. It only downloads what your machine is actually missing, so if you already
have Python and ffmpeg it will be much quicker.

You are looking for this at the end:

```
  ============================================================
  Setup complete. Nothing was installed system wide.
```

6. Press any key to close the window.

You only ever do this once per machine. If the download is interrupted, just run
**Setup.bat** again: it picks up where it left off and skips anything already done.

### Step 3: Put your narration in

Setup created an `input` folder for you. Open `input\audio` and copy your narration
audio into it. Setup creates `input\audio`, `input\images` and `output` as its very
first action, before it downloads anything, so they are there even if the rest of the
setup did not get to finish.

Accepted: `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.opus`, `.wma`.

If your narration is split across several files, put them all in and name them so they
sort in the right order, for example `part1.mp3`, `part2.mp3`, `part3.mp3`. They are
joined into one continuous recording.

### Step 4: Run Transcribe Audio.bat

Double click **Transcribe Audio.bat** and press **Enter** when it asks. It listens to
your narration and writes down what is said and exactly when, entirely on your
computer.

Expect roughly one minute of processing for every eight minutes of audio. A progress
bar shows how far along it is.

The last line is the one that matters:

```
  Next: put 86 images in input\images\ then run Create Video.bat
```

**Write that number down.** It is how many images your video needs, because each line
of the transcript gets one image.

Already have a transcript of your own? Put it in the `input` folder as `script.srt` and
skip this step entirely.

### Step 5: Put your images in

Copy exactly that many images into the `input\images` folder.

Accepted: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`.

**Name them so they sort in order**: `1.jpg`, `2.jpg`, `3.jpg` and so on. Plain numbers
are safest. The first image is shown for the first line of the transcript, the second
for the second line, and so on to the end.

Already have names like `IMG_20260401_182233.jpg`? Double click **Rename Images.bat**.
It renumbers the folder `001`, `002`, `003` in the order the files were created, shows
the whole list before it changes anything, and can put the old names back. See
[Rename Images.bat](#rename-imagesbat).

If you end up with the wrong number of images, that is fine and recoverable. See
[When the counts do not match](#when-the-counts-do-not-match).

### Step 6: Run Create Video.bat

Double click **Create Video.bat** and press **Enter** when it asks. A progress bar runs
while it works. A ten minute video takes roughly 90 to 110 seconds on an average
machine.

```
  done in 96.4s  ->  output\2026-08-29_14-30-22.mp4  (78.2 MB, 600.000s, 6.2x realtime)
```

### Step 7: Watch it

Your finished video is in the `output` folder, named for the date and time it was
built, such as `2026-08-29_14-30-22.mp4`. Double click to play it.

Naming each render by the moment it finished means a second attempt never quietly
replaces the first, and the folder stays in the order you made them. To choose the
name yourself, pass one: `Create Video.bat -o output\my-video.mp4`.

That is the whole process. Setup is a one time thing, so for every video after this one
you only repeat steps 3 to 6.

### The short version

Once you have done it once, this is all there is to it:

```
input\
  audio\              your narration            <- you provide
  script.srt          written for you in step 4
  images\             one image per line        <- you provide
output\
  2026-08-29_14-30-22.mp4    your finished video, named for when it was built
```

| | do this |
| --- | --- |
| once per machine | run `Setup.bat` |
| every video | drop audio in `input\audio\`, run `Transcribe Audio.bat` |
| | drop that many images in `input\images\`, run `Create Video.bat` |
| | collect the video from `output\` |

## What Setup.bat installs

Setup checks what the machine already has and fills in only what is missing:

| dependency | if already present | if missing |
| --- | --- | --- |
| `input\audio`, `input\images`, `output` | left alone | created first, before anything else |
| Python 3.8 or newer | uses the one on `PATH` | unpacks a private copy into `runtime\python` |
| ffmpeg and ffprobe | uses the ones on `PATH` | unpacks them into `bin` |
| speech to text engine | uses the copy in `runtime\whisper` | installs it there, about 140 MB |
| speech model | uses the copy in `runtime\whisper\models` | downloads `base`, about 140 MB |

**Nothing is installed system wide.** No installer runs, no `PATH` is modified, no
registry keys are written, and administrator rights are not needed. Anything Setup has
to fetch lands inside this project folder, so deleting the folder removes every trace.

The video side has no `pip` packages at all and is Python standard library only, which
is why a bare embeddable Python is enough to run it. The speech engine is the one
exception, and it is installed with `pip --target` into `runtime\whisper\lib` rather
than into a virtual environment or the system `site-packages`. One code path covers
both a system Python and the embeddable one, which cannot host a virtual environment
because it ships without `ensurepip`.

Options:

```
Setup.bat                  use what the machine has, fetch only what is missing
Setup.bat --local          ignore the system copies and fetch Python and ffmpeg
                           locally, so the folder is fully self contained
Setup.bat --check          report what is installed and change nothing
Setup.bat --no-transcribe  skip the speech engine, video assembly only
Setup.bat --model tiny     pre-download a different model size (see Performance,
                           the default base is usually the right choice)
```

The folders come first deliberately. `input` and `output` are in `.gitignore`, and Git
cannot carry an empty folder in any case, so a fresh clone or a downloaded ZIP arrives
without them. Creating them before anything that needs a network means a setup that
stops early, on a slow download or a machine that fails a check, still leaves you with
somewhere to put your files.

If the speech engine cannot be installed, Setup says so and carries on. Video assembly
is unaffected, and you can supply your own transcript instead.

Setup finishes by rendering a small test video, checking it frame by frame, and
running a decode through the speech model, so it only reports success if the machine
can genuinely do the work:

```
     [x] img2vid modules import
     [x] ffmpeg and ffprobe found  using PATH
     [x] child process guard available
     [x] an H.264 encoder works  libx264 selected
     [x] renders a video end to end
     [x] frame count is exact  120 frames, expected 120
     [x] each image is shown for the right number of frames
     [x] speech engine imports
     [x] a speech model is present  base, from runtime\whisper\models
     [x] the model loads
     [x] a decode runs end to end
     [x] the transcript it writes feeds the renderer  2 cues, second starts at 1.370s
```

An internet connection is only needed if something is actually missing. Setup downloads
roughly 11 MB for Python, roughly 90 MB for ffmpeg, and roughly 280 MB for the speech
engine and its model, and only for the ones it needs.

### Moving to another machine

Copy the whole folder across and run `Setup.bat` on the new machine. If you want a copy
that works with no internet on the far side, run `Setup.bat --local` before you move it,
which brings Python and ffmpeg into the folder itself.

The speech engine is the exception: it must be installed on the machine that will run
it, because its packages contain compiled extensions built for one CPython version.
Setup records which interpreter installed them and asks you to run it again if that
changes, rather than failing later with an import error.

## Transcribe Audio.bat

Double click it. It reads everything in `input\audio\` and writes three files that all
describe the same cues:

| file | what it is for |
| --- | --- |
| `input\script.srt` | the transcript Create Video.bat reads |
| `input\script.txt` | the same thing, readable at a glance |
| `temp\script.json` | `start`, `end` and `text`, for any other tool |

```
  transcribe
  ------------------------------------------------------------
  audio 1    : input\audio\narration.mp3
  duration   : 399.4s
  output     : input\script.srt
  model      : base (int8, cpu)
  [##############################] 100.0%   49.6s
  language   : en
  done in 49.6s  ->  input\script.srt  (86 cues, 8.1x realtime)

  Next: put 86 images in input\images\ then run Create Video.bat
```

**One cue becomes one image**, so that final count is the number of images you need.
It is the number you control with `--max-chars` and `--max-seconds`.

**Several audio files are joined into one continuous transcript** by default, in
natural filename order, which is exactly how Create Video.bat joins them too. So the
timestamps line up with the finished video rather than restarting on each file. When
the folder holds alternative takes rather than consecutive parts, `--pick` offers the
choice instead:

```
  Which audio should be transcribed?

    a) all 3 files, joined into one continuous transcript
    1) take-one.mp3
    2) take-two.mp3
    3) take-three.mp3

  Choose a number, or a for all [a]
```

An existing transcript is never silently destroyed. If `input\script.srt` is already
there it is copied into `temp\replaced\` first and the run tells you where the copy
went.

Repeating a transcription of the same audio with the same settings is free: the result
is cached under `temp\transcribe_cache\`, keyed on the file and the settings. `--fresh`
ignores the cache.

Flags work the same way as the other batch file, either on the command line or on the
`FLAGS` line inside it:

```
Transcribe Audio.bat --model small --max-chars 90
```

## Create Video.bat

Double click **Create Video.bat**. It says what it is about to build and waits for you
for an answer, so opening it by accident does nothing. The first run creates the folders it
needs and tells you what to put in them:

```
input\
  script.srt          your transcript, any of .srt .vtt .txt
  images\             one image per transcript line
  audio\              one or more audio files
```

Drop your files in, run it again, and the finished video appears in `output\`,
named for the date and time it was built so a rerun never replaces the last one.
Audio files are joined in natural filename order, so `part1.mp3`, `part2.mp3`,
`part10.mp3` play in the order you would expect.

It also forwards any flags you give it, so this works too:

```
Create Video.bat --fps 10
Create Video.bat --force
```

If you launch it by double clicking there is nowhere to type a flag, so open the file
in a text editor and put what you want on the `FLAGS` line near the top:

```
set "FLAGS=--force --fps 15"
```

It checks for Python and ffmpeg up front and tells you exactly what is missing rather
than failing with a stack trace.

## Rename Images.bat

Optional, and the only part of this project that changes files you brought in. The video
is built from the images in filename order, one per transcript line, so the names decide
which image lands on which line. Camera and download names do not sort that way.

Double click **Rename Images.bat**. It asks twice: once before it does anything at all,
and again after it has shown you the exact list of renames. It offers two things:

```
    1) renumber them in this order       (just press Enter)
    2) insert an image at a number, then renumber
    3) put them in a different order first
```

Option 1 puts everything in order, oldest file first by the date each one was created:

```
  rename images
  ------------------------------------------------------------
  folder    : input\images
  images    : 86
  order     : date created, oldest first

    IMG_20260401_182233.jpg                  ->  001.jpg
    screenshot (10).png                      ->  002.png
    scene 2.jpeg                             ->  003.jpeg
    ... and 83 more

  Rename 86 files? [Y/n]
```

### Choosing the order

Option 3 asks what to sort by, then whether to reverse it:

```
  Put them in order by:

    1) created   date created, oldest first  (now)
    2) modified  date modified, oldest first
    3) name      filename, A to Z
    4) size      file size, smallest first
    5) type      file type, then filename
    6) random    random shuffle

  Choose 1 to 6 [1]:
  Reverse it, so the last one becomes 001? [y/N]
```

| order | what it does | reversed |
| --- | --- | --- |
| `created` | date created, oldest first. The default, unless the names are already numbered | newest first |
| `modified` | date modified, oldest first | newest first |
| `name` | filename, A to Z, numerically aware so `2` sorts before `10` | Z to A |
| `size` | file size, smallest first | largest first |
| `type` | groups `.jpg` together, then `.png`, each group by name | groups reversed |
| `random` | shuffle | no effect |

On the command line that is `--by` and `--desc`:

```
Rename Images.bat --by modified --desc
Rename Images.bat --by size
Rename Images.bat --by random --seed 7
```

**Date created is not always the date the photo was taken.** Windows sets it to when the
file arrived on this machine, so copying a folder stamps everything with the time of the
copy. When that has happened, `--by modified` is usually closer to the truth, and
`--by name` is exact if the names already carry the order.

There is a specific trap here worth knowing about. A folder copied in one go is written
in a single burst, which stamps the creation times milliseconds apart in whatever order
the copy happened to run, and that order is not always the one you would guess. A copy
that runs backwards makes `170.jpg` the oldest file in the folder, so `--by created`
faithfully replays it and renames `170.jpg` to `001.jpg`, reversing everything.

So filenames that are already numbered win. Those names are an order somebody chose, and
a copy date is not. When the default would disagree with them, the run keeps the names
and says why:

```
  [i] these filenames are already numbered, so that order was kept.
      date created, oldest first would have started with
        170.jpg
      A folder copied in one go is stamped with the time of the copy,
      not the time the pictures were taken, and a copy can run in any
      order. Add --by created to sort by date anyway.
```

That only overrules a default nobody asked for. Type `--by created` and you get date
order, with a `[!]` warning naming the first place it disagrees with the names.

Files sharing a timestamp are ordered by filename, and that tie break stays A to Z even
under `--desc`, so reversing the order does not scramble the files that were tied.

A shuffle reports the seed it used, so an order you liked can be repeated:

```
  order     : random shuffle, seed 182913  (repeat it with --seed 182913)
```

### Inserting an image

Option 2 is for when the video is nearly right and one shot is missing, or one needs to
move. It asks for the picture and the number it should take, then everything from that
number on shifts up one and the whole folder is renumbered:

```
  Image to insert, or leave blank to finish:  C:\shots\the-missing-one.png
  Put it at which number? 1 to 87:  5

  inserting :
    the-missing-one.png                      ->  005.png
```

You can give it a full path, drag the file into the window, or type the name of an image
already in `input\images` to move it somewhere else in the order. Ask for more than one
by answering again instead of leaving it blank.

**An image from outside the folder is copied in, not moved**, so the original stays where
you left it. `--undo` removes the copy again rather than leaving it behind under a name
you never chose.

On the command line the same thing is two flags, repeatable in pairs:

```
Rename Images.bat --insert "C:\shots\the-missing-one.png" --at 5
```

Each file keeps its own extension, and anything in the folder that is not an image is
left alone. Every run records what it did under `temp\renames`, so the previous names can
be put back:

```
Rename Images.bat --undo
```

Double clicking leaves nowhere to type a flag, so open `Rename Images.bat` in a text
editor and put what you want on the `FLAGS` line near the top, the same way the other two
step files work:

```
set "FLAGS=--undo"
```

| flag | what it does |
| --- | --- |
| `--by created\|modified\|name\|size\|type\|random` | what to put them in order by |
| `--desc` | reverse whichever order you picked |
| `--seed N` | repeat a particular shuffle |
| `--insert FILE --at N` | put an image in at number N, then renumber |
| `--dry-run` | show the list and change nothing |
| `--by modified` | order by date modified instead of date created |
| `--by created` | force date order on a folder whose names are already numbered |
| `--by name` | order by the current filenames |
| `--start 0` | number from `000` instead of `001` |
| `--digits 1` | name them `1`, `2`, `3` instead of `001`, `002`, `003` |
| `--undo` | put back the names from the previous run |
| `--folder PATH` | renumber a folder other than `input\images` |

A word on date created. Windows sets it when the file arrives on the machine, not when
the picture was taken, so a folder that was copied carries the time of the copy and every
file in it can share one timestamp down to the second. Files that tie are ordered by
filename, the same natural order the renderer itself reads them in, so the result is
never left to chance. `--by modified` is often closer to when the images were really
made.

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
python app\img2vid.py -t script.srt -i .\images -a narration.mp3 -o video.mp4
```

Check the timing before committing to a render:

```
python app\img2vid.py -t script.srt -i .\images -a narration.mp3 --dry-run
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
python app\img2vid.py -t script.srt -i .\images -a part1.mp3 part2.mp3 part3.mp3 -o video.mp4
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

### transcribe.py, the speech to text step

| Flag | Default | Description |
| --- | --- | --- |
| `-a`, `--audio` | everything in `input\audio` | Audio files to transcribe |
| `--pick` | off | Choose one file interactively instead of joining them all |
| `--name` | `script` | Base name for the written files |
| `--out-dir` | `input` | Where the transcript is written |
| `--model` | `base` | `tiny`, `base` or `small`, larger is slower and more accurate |
| `--language` | auto detect | Force a language code such as `en` |
| `--beam` | `1` | Beam width, `1` is greedy and fastest |
| `--batch` | `0` | Decode this many speech regions at once, `0` is sequential |
| `--threads` | `0` | Decoder CPU threads, `0` lets the engine choose |
| `--compute` | `int8` | Numeric precision, `int8` is fast and light on a CPU |
| `--words` | off | Also record a timestamp for every word |
| `--condition` | off | Feed each segment the previous text, slower and can loop |
| `--max-chars` | `0` | Split cues longer than this many characters, `0` is off |
| `--max-seconds` | `0` | Split cues longer than this many seconds, `0` is off |
| `--min-seconds` | `0` | Merge cues shorter than this many seconds, `0` is off |
| `--fresh` | off | Ignore the cached result for this audio |
| `--keep-temp` | off | Keep intermediate files in `temp/` |
| `--quiet` | off | Suppress progress output |

**Controlling how many images you need.** Left alone, the cue boundaries are the ones
the model chose, which follow natural pauses. `--max-chars` and `--max-seconds` split
long cues at word boundaries, and `--min-seconds` merges cues too short to hold an
image. Splitting never loses or reorders a word, and never moves the outer edges of the
cue it split. On a 399 second narration that yields 86 natural cues:

| setting | cues |
| --- | --- |
| none | 86 |
| `--max-chars 100` | 90 |
| `--max-chars 90` | 108 |
| `--max-chars 60` | 143 |
| `--max-seconds 4` | 143 |
| `--max-seconds 3` | 179 |

### img2vid.py, the video assembly step

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

### Speech to text

1. **Gather the audio** from `input\audio\` in natural filename order. Several files
   are concatenated with the ffmpeg concat filter into one 16 kHz mono track first.
   The filter is used rather than the demuxer because the inputs can be any mix of
   formats and sample rates, and joining before decoding is what keeps timestamps
   continuous across files instead of restarting at zero on each one. 16 kHz mono is
   what the model resamples to anyway, so the conversion happens once.
2. **Decode with faster-whisper** on the CPU with `int8` weights, and with voice
   activity detection filtering out silence so the model is not asked to transcribe it.
3. **Hold every timestamp inside the audio.** Whisper predicts timestamps and routinely
   overshoots the true end of the file on the final segment, so times are clamped to the
   measured duration and any cue left empty or zero length is dropped.
4. **Reshape the cues** if `--max-chars`, `--max-seconds` or `--min-seconds` was given.
   Short cues are merged before long ones are split, because the other order would
   split a cue and immediately merge the pieces back together.
5. **Write SRT, TXT and JSON.** The SRT is what the assembly step reads back.

The model runs entirely on this machine. No audio leaves it, there is no API key, and
after the first download no network access is needed.

### Video assembly

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

Machine for every number below: Intel i7-8650U, 4 cores and 8 threads at 15W, Intel
Quick Sync available, no discrete GPU. Each configuration was run three times and the
fastest run is reported, because wall clock on this machine is noisy enough that a
single measurement can be a quarter out.

### Speech to text speed

Material: a real 399.4 second narration. Default settings are `base`, `int8`,
greedy decoding, voice activity filtering on.

| phase | seconds |
| --- | --- |
| import the engine | 0.9 |
| load the model | 1.9 |
| probe the audio | 0.2 |
| decode 399.4s of audio | 46.5 |
| **total** | **49.6** |

That is **about 8x realtime**, so roughly a minute of processing for eight minutes of
narration. Everything except the decode is a fixed cost of about three seconds, so it
matters on a short clip and disappears on a long one.

**What each setting is worth**, measured one at a time from that baseline:

| change | decode | against baseline | cues | word error rate |
| --- | --- | --- | --- | --- |
| **baseline** | **45.7s** | | **86** | **0.9%** |
| `--beam 5` | 53.0s | 16% slower | 88 | not measured |
| `--words` | 46.0s | 23% slower | 83 | not measured |
| `--threads 2` | 44.9s | 20% slower | 86 | not measured |
| `--threads 8` | 43.4s | 16% slower | 86 | not measured |
| `--batch 8` | 34.3s | 25% faster | 90 | 4.3% |

Notes on the defaults these produced:

- **Greedy decoding is the default.** A beam of 5, which is what the library does
  unprompted, costs 16 percent for no visible gain on clear narration.
- **Word timestamps are off unless something needs them.** They cost 23 percent, and
  nothing needs them until you ask for cue reshaping, at which point they are switched
  on automatically.
- **Thread count is left to the engine.** Pinning it either way measured slower. The
  engine already picks the physical core count, which is the right answer here.
- **`--batch 8` is faster but less accurate, so it is not the default.** It is 25
  percent quicker and much steadier run to run, but word error rate against the
  reference transcript went from 0.9 percent to 4.3 percent, and the longest cue grew
  from 7.2 to 10.5 seconds. For a transcript that is both the timing source and the
  script on screen, that is the wrong trade. Use it when you want a rough transcript
  quickly.

Accuracy is measured against `input\script.srt`, a transcript of the same audio that
was not produced by this tool. At the default settings the output differed from it by
**0.9 percent of words**, 1041 words against 1043.

**Which model to use.** Measured on a 120 second excerpt, so that all three fit in one
sitting without the throttling described below distorting the comparison:

| model | decode | realtime | word error rate | on disk |
| --- | --- | --- | --- | --- |
| `tiny` | 17.1s | 7.0x | 5.5% | 75 MB |
| **`base` (the default)** | **19.8s** | **6.0x** | **2.7%** | **140 MB** |
| `small` | 140.6s | 0.9x | 2.7% | 484 MB |

`base` is the default for a reason that only shows up when you measure it. `small` is
seven times slower here and drops **below realtime**, meaning two minutes of audio take
longer than two minutes to transcribe, and on this material it was **no more accurate
than `base`**. `tiny` saves a little time for twice the errors. Unless you have
difficult audio and time to spare, leave it alone.

These excerpt error rates read higher than the 0.9 percent above because the cut at 120
seconds slices a sentence in half. The full file figure is the fair one.

**One caveat specific to thin laptops.** This CPU has a 15W budget, and sustained
decoding is exactly the AVX heavy work that exhausts it. A single run on an idle
machine takes the 50 seconds above, but four back to back runs of the same file did
not finish inside ten minutes. If you are transcribing a batch, expect the later ones
to take two to three times longer than the first. A desktop with real cooling does not
behave this way.

Reproduce it yourself:

```
python temp/benchmark_transcribe.py                    sweep, single runs
python temp/benchmark_transcribe.py --repeat 3         best of 3
python temp/benchmark_transcribe.py --only batch beam  one group at a time
```

### Video assembly speed

Fixture: 100 images rendered to 200 seconds of 1920x1080, which is 6000 frames.

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
python app\img2vid.py -t script.srt -i .\images -a narration.mp3 --force
```

Create Video.bat will also offer it. If the counts do not match it prints the problem and asks
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
`start /b python app\img2vid.py ...`.

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

The speech step has its own harness:

```
python temp/verify_transcribe.py
```

It runs against whatever is in `input\audio\`, writes only into `temp\`, and checks:

1. Cues are ordered, do not overlap, and every timestamp lies inside the audio.
2. The emitted SRT parses back through the same reader the renderer uses, to the same
   start times to the millisecond. That is the contract between the two steps, so it is
   asserted rather than assumed.
3. Word error rate and timestamp drift against `input\script.srt` when one is present.
   These are reported as measurements, not asserted against a threshold, because a hand
   made reference is not ground truth in the strict sense.
4. Reshaping honours its limits, and the text is unchanged when the pieces are joined
   back together, so a split cannot lose or reorder a word.
5. Two audio files produce one continuous timeline, with the second file offset rather
   than restarted.
6. The transcript is accepted by the renderer and the frame counts add up to the audio.
7. With the engine folder renamed away, the failure is a message naming `Setup.bat`
   rather than a traceback.

## Project layout

```
Setup.bat             one time provisioning, nothing system wide
Transcribe Audio.bat  step 1, audio -> transcript
Create Video.bat      step 2, transcript + images + audio -> MP4
Rename Images.bat     optional, renumbers input\images by date created

app\                  what the four .bat files above actually run
  transcribe.py       zero argument launcher that Transcribe Audio.bat calls
  run.py              zero argument launcher that Create Video.bat calls
  rename_images.py    the renumbering that Rename Images.bat calls
  img2vid.py          CLI entry point for the assembly step
  setup_check.py      end to end proof that a fresh setup works
  setup_speech.py     records the interpreter and fetches the speech model
i2v\                  the library, imported by everything in app\
  cli.py              argument parsing, orchestration, progress output
  captions.py         cue type, SRT/VTT/TXT/JSON writers, cue re-splitting
  speech.py           faster-whisper wrapper, the only third party touch point
  transcript.py       SRT, WebVTT and plain timestamp parsing
  probe.py            ffprobe helpers, encoder detection with an on disk cache
  render.py           timeline, filter graphs, chunked encoding and muxing
input\                created on first run, your source files
output\               created on first run, finished videos
runtime\
  python\             only if Setup had to fetch Python, a private copy
  whisper\lib\        the speech engine, installed with pip --target
  whisper\models\     the speech model weights
bin\                  only if Setup had to fetch ffmpeg
temp\
  make_fixture.py     fixture generator, small and benchmark sizes
  verify.py           end to end frame accurate verification of the video step
  verify_transcribe.py  end to end verification of the speech step
  benchmark.py        render performance measurement
  benchmark_transcribe.py  speech performance measurement
  transcribe_cache\   past transcriptions, keyed on the audio and the settings
  replaced\           transcripts that were overwritten, kept just in case
AGENTS.md             project memory and rules
README.md             this file
```

Everything the tool generates, including intermediates and test output, stays inside
`temp/`. Intermediates are cleaned up after each run unless `--keep-temp` is given.
`runtime\` and `bin\` only exist if Setup had to fetch something into them.

## Troubleshooting

**There is no `input` folder after running Setup.bat**
Two things cause this. Either the copy is still inside the ZIP, in which case Windows
is running it from a temporary folder that it deletes afterwards, so extract the ZIP
properly first and run `Setup.bat` from the extracted folder. Or the folder sits
somewhere Windows will not let you write to, such as `C:\Program Files`, in which case
move the whole project to somewhere like `Documents` and run `Setup.bat` again. Setup
reports both cases by name. Note that `Setup.bat --check` deliberately creates nothing,
it only reports, so use a plain `Setup.bat` run. Failing all that, both
`Transcribe Audio.bat` and `Create Video.bat` also create the folders when they start.

**Setup.bat stops at `the ffmpeg download did not contain ffmpeg.exe`**
Take the current version of the project and run `Setup.bat` again. Earlier versions
could not unpack a download into a folder whose path contains a space, which is every
copy of this project, so the archive arrived, the extraction failed without saying so,
and the step after it blamed the archive contents. If a current copy still stops there,
the download itself is arriving incomplete: run it once more, and if it keeps happening,
download a Windows build from https://www.gyan.dev/ffmpeg/builds/ and copy `ffmpeg.exe`
and `ffprobe.exe` into a `bin` folder next to `Setup.bat`.

**`ffmpeg was not found`** or **`Python was not found`**
Run `Setup.bat`. It uses whatever the machine already has and fetches only the missing
piece, into this folder rather than system wide. If the machine has no internet, install
Python from python.org and put a Windows ffmpeg build's `ffmpeg.exe` and `ffprobe.exe`
into a `bin` folder next to `Setup.bat`.

**`the speech engine is not installed`**
Run `Setup.bat`. It installs the engine into `runtime\whisper\lib` inside this folder.
If you only want to assemble video from a transcript you already have, this does not
affect you: `Create Video.bat` never touches the speech engine.

**`The speech engine was installed for Python 3.12 but this is Python 3.14`**
The engine contains compiled extensions built for one CPython version. This happens
after installing or removing a system Python, or after copying the folder from another
machine. Run `Setup.bat` again and it reinstalls them for the interpreter now in use.

**`429 Too Many Requests`** or **`we cannot find the appropriate snapshot folder`**
The speech model has not finished downloading on this machine, and huggingface.co is
rate limiting or unreachable. Nothing is wrong with your files. Either run `Setup.bat`
again in a few minutes, which carries on from where it stopped, or copy the folder
`runtime\whisper\models` across from a machine where it already works. That folder is
the whole model, so a copied one needs no network at all.

A model already on disk is never checked against the Hub, so once the download has
finished on a machine this cannot happen there again.

**`No speech was found in <file>`**
The voice activity detector found nothing to transcribe. Check that the file really is
narration rather than music, silence or a corrupt download, and that it plays.

**Transcription is slower than you expected**
The first run of a session pays for loading the model, which is a fixed cost of a few
seconds regardless of the length of the audio, so it dominates a short clip and
disappears on a long one. Beyond that, `--model tiny` is the fastest and
`--model small` the most accurate. See [Performance](#performance) for measured
numbers on this machine.

**The transcript has too few or too many lines for the images you want**
The cue boundaries follow natural pauses, which will not match a fixed image count.
Use `--max-chars` to split long lines and `--min-seconds` to merge short ones. The
table in the [Command reference](#command-reference) shows the counts each setting
produced on a real 399 second narration.

**`Count mismatch: N transcript timestamps but M images`**
There must be exactly one image per transcript line. Check for a stray file in the
images folder, or a blank line that was parsed as a cue. Pass `--force` to build the
video anyway, or put `--force` on the `FLAGS` line in Create Video.bat.

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

---

## Contributing

Issues and pull requests are genuinely welcome. If a transcript comes out wrong, a
render fails, or Setup cannot get itself going on your machine,
[open an issue](https://github.com/m-abdullah-awais/img2vid/issues) with what you ran
and what it printed, and I will take a look.

If you are reporting a timing or quality problem, the output of
`python app\img2vid.py ... --dry-run` is the single most useful thing you can paste in.

## License

Released under the [MIT License](LICENSE). Use it, learn from it, build on it.

Nothing third party is redistributed in this repository. ffmpeg and the speech model are
downloaded by `Setup.bat` at install time and stay in your copy of the folder, so their
licences are between you and them: ffmpeg builds are GPL, and faster-whisper and the
Whisper models are MIT.

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
is an independent tool and is not affiliated with OpenAI, the ffmpeg project, or any
other party whose work it builds on.</sub>

</div>
