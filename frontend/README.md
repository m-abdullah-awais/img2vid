# img2vid web app

The browser side of img2vid. Everything a user does happens here: upload the
narration, transcribe it or upload a transcript, add one image per transcript
line, arrange them, build the video, play it and download it. The work itself is
done by the local engine, a Python API on `http://127.0.0.1:8765`; this app only
talks to it.

## Running it

`Run.bat` at the project root starts the engine and this app together, rebuilds
the app when its sources change, and opens it at `http://127.0.0.1:3000`.
`Run.bat --dev` runs the development server instead, for working on the app.

To work on it directly, open a terminal in this folder and keep npm's cache and
Next.js telemetry inside the project, as the rest of img2vid does:

```bat
set "npm_config_cache=E:\path\to\img2vid\backend\runtime\npm-cache"
set NEXT_TELEMETRY_DISABLED=1
```

Then `npm run dev` for the development server, `npm run lint` for ESLint and
`npm run build` for a production build. Lint and build are expected to be clean.

The build never needs the engine: every page is a static shell that fetches its
data in the browser. Without the engine, the app says so and offers Retry.

The API address is `http://127.0.0.1:8765`, set in `src/lib/api.ts`. Set
`NEXT_PUBLIC_API_URL` at build time to point it elsewhere.

## Layout

| Path | What it is |
| --- | --- |
| `src/app/page.tsx` | Projects: create, rename, delete with Undo |
| `src/app/projects/[id]/page.tsx` | The studio for one project |
| `src/app/system/page.tsx` | Tools, speech models, storage and the self-test |
| `src/app/about-developer/page.tsx` | The developer, and how img2vid is built |
| `src/components/studio/` | Status strip, storyboard, videos, banners, drag and drop |
| `src/components/editor/` | The live preview, its transport, the timeline with image clips and waveform, the inspector, undo and redo |
| `src/components/dialogs/` | Narration, transcript, images, renumber and build dialogs |
| `src/components/job/` | The job provider, which polls `GET /api/job`, and the job dock |
| `src/components/ui/` | Dialog on the native `<dialog>`, Button, Field, Toast, Thumb, ProgressBar |
| `src/lib/types.ts` | The API contract's shapes, field for field |
| `src/lib/api.ts` | Fetch wrapper, `ApiError`, and the XHR upload that reports progress |
| `src/lib/arrange.ts` | What a drop will do, worked out before the drop |

## Rules this app keeps

- Rendering speed comes first. While a job runs, only `GET /api/job` is polled,
  every 500 ms, and nothing moves on screen except the progress bar.
- Images are placed by the number their filename starts with. A line with no
  image is built black only after the user has confirmed every such line.
- Colour means state: amber for a line with no image, green for done, red for
  Build video and for errors. Everything else is graphite, hairlines and type.
- Type is Barlow at three widths, served from this app. The app makes no request
  outside this computer.

## Developer

Muhammad Abdullah Awais, Full Stack Developer

- Website: www.abdullahawais.com
- Email: contact@abdullahawais.com
- LinkedIn: https://www.linkedin.com/in/m-abdullah-awais-programmer
- GitHub: https://github.com/m-abdullah-awais
- YouTube: https://www.youtube.com/@m_abdullah_awais
- Instagram: https://www.instagram.com/m_abdullah_awais
