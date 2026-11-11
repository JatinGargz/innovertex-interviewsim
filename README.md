# InterviewSim

**GitCoders · InnoVertex 4.0 · Best AI Agent on Nonilion**

InterviewSim is a timed debugging interview agent concept for students preparing for machine-coding rounds. It gives a candidate a small, deliberately broken service, answers clarification questions as a senior engineer, accepts a code submission, and returns a private scorecard. The first round is a Python sliding-window rate limiter.

**Pitch deck:** [`submission/InterviewSim-InnoVertex-7slides.pptx`](submission/InterviewSim-InnoVertex-7slides.pptx) · **Deployment guide:** [`submission/START-HERE.md`](submission/START-HERE.md)

The project uses Render Workflows to coordinate grading. Candidate code is sent to a Judge0 sandbox with network access disabled; it is never executed by the web service or a Render Workflow task. A separate review step grades the candidate's explanation and code quality, and the workflow combines both results into a scorecard.

## Implemented in the MVP code

- A 45-minute session with a server-side deadline and a visible countdown.
- A challenge brief and starter file for the rate-limiter debugging round.
- An interviewer chat backed by an OpenAI-compatible chat-completions endpoint, with a useful local fallback.
- Submission handoff to a Render Workflow.
- Isolated code execution through a configurable Judge0-compatible API.
- A scorecard with hidden-case results, rubric dimensions, and written feedback.
- A downloadable PDF scorecard.
- A canonical Nonilion webhook adapter boundary.

The Render and external-provider paths require configuration before online grading works. The Nonilion adapter is not yet verified against the platform's real import/API schema; see [`submission/START-HERE.md`](submission/START-HERE.md) for the manual setup and the remaining integration step.

When both grading steps complete, the overall score weights hidden-case correctness at 60% and the four evidence-checked rubric dimensions at 40%. If the sandbox or rubric provider is unavailable, the report labels the missing part instead of inventing a score.

The MIT-licensed starter repository is credited below and its license is retained. Its unrelated practice-problem bank is not included in this submission.

## Run locally

Use Python 3.11 or later. On Windows, double-click `START-INTERVIEWSIM.bat`; it installs the requirements if needed, starts the app, and opens the browser. Keep its server window open while using the app. Do not open `interviewsim/static/index.html` directly; the app needs its local server.

To start it from a terminal instead:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn interviewsim.app:app --reload
```

Open `http://127.0.0.1:8000`. Set `OPENAI_API_KEY` to enable the live interviewer. To grade submissions, also configure the Render API, Judge0, and callback settings in `.env`; the app deliberately does not run candidate code locally.

## Deploy on Render

`render.yaml` defines a web service, a Render Workflow service, and a small free Render Postgres database for hackathon use. The free database expires after 30 days; upgrade it in the Render dashboard if the project needs to keep its data longer.

Follow the click-by-click steps in [`submission/START-HERE.md`](submission/START-HERE.md). The Blueprint creates the web service, Render Workflow service, and a free Postgres database. Add the provider and Render API credentials after the services exist; never commit them to GitHub.

The Render Workflow is a required part of the judging path, not an optional background process. Render's Python SDK starts it from the FastAPI app, and the workflow runs the isolated grader and rubric review as separate tasks.

## Nonilion adapter

The app exposes `POST /api/nonilion/webhook` for the canonical event shape documented in `docs/nonilion-integration.md`. That route is a boundary for the platform adapter, not a claim that Nonilion already sends this exact JSON. The public Nonilion docs currently list the API reference as “Soon.” Confirm the current agent import process and map its verified fields and authentication rule before claiming a live Nonilion integration. The hackathon problem statement requires the final demo to run inside Nonilion.

## Design notes

- The timer deadline is stored in the database, so refreshing the page does not reset the round.
- Reports are private by default. There is no public team-channel score posting in this MVP.
- The interviewer's generated advice cannot change the hidden evaluator or its result.
- Workflow arguments contain the candidate's source and short transcript; do not put secrets in them.
- The callback is authenticated with a shared secret.

## Upstream starter

This project is adapted from [`azizu06/ai-coding-interview-practice`](https://github.com/azizu06/ai-coding-interview-practice), licensed under MIT. The upstream `LICENSE` is retained. InterviewSim's application, challenge brief, adapter, UI, workflow, and grading integration are new project code.
