# GitCoders · InterviewSim submission setup

This is the quick path from the local prototype to a live demo. Keep API keys in Render’s dashboard only; never paste them into this repository or a chat.

## 1. Redeem the hackathon Render credits

The problem statement says **each participant** must redeem their own Render credit. Open:

https://credits-portal-mmdm.onrender.com/claim/innovortex-4-oscode

Use the participant’s Render account and complete the claim.

## 2. Deploy the Blueprint

1. Sign in at [Render Dashboard](https://dashboard.render.com/) using GitHub.
2. In Render, choose **New → Blueprint**.
3. Connect/select `JatinGargz/innovertex-interviewsim` and create the Blueprint instance.
4. Render reads `render.yaml` and creates the web service, `interviewsim` Workflow, and Postgres database. Wait for the first deploys to finish.
5. Open the web service’s `https://…onrender.com` URL and confirm the page loads. The `/health` endpoint should return `{"status":"ok","service":"interviewsim"}`.

The web service and database use Render’s Free plan. The web service sleeps after 15 minutes without traffic and can take about a minute to wake. The database expires after 30 days. Render Workflow task runs are metered; use the claimed $50 credit for these runs and monitor its balance. If Render requests a payment method or shows a charge beyond your existing credit, stop before continuing.

## 3. Add the model and grader settings

Open the `interviewsim-settings` environment group in Render. Add these values there so the web app and Workflow both receive them:

| Variable | Value |
| --- | --- |
| `OPENAI_API_KEY` | A Gemini API key created in [Google AI Studio](https://aistudio.google.com/app/apikey). Keep it secret. |
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `OPENAI_MODEL` | `gemini-3.8-flash` |
| `JUDGE0_BASE_URL` | `https://ce.judge0.com` for the initial demo; omit the trailing slash. |
| `APP_PUBLIC_URL` | The full deployed web-service URL, including `https://`. |

`JUDGE0_LANGUAGE_ID=71`, the workflow slug, session length, and internal callback secret are already set in the Blueprint. Try the Judge0 CE endpoint with its key fields blank first; authentication depends on that instance’s configuration. If it returns 401 or 429, pause and ask for help—do not subscribe to a paid API plan or add billing details. The code supports Judge0 auth headers if a no-cost endpoint requires them.

Next, open the **web service’s** Environment page and add:

| Variable | Value |
| --- | --- |
| `RENDER_API_KEY` | A Render API key from your Render account settings. The web app uses it to start the grading Workflow. |

Do not add that Render API key to the Workflow service. The `INTERNAL_CALLBACK_SECRET` is generated for the shared environment group; leave it as generated.

## 4. Confirm the grading path

1. Open the public web URL and start a short demo session.
2. Ask one clarification question; the staff-engineer interviewer should answer.
3. Submit a candidate solution only after the Judge0 settings are active.
4. In the Render dashboard, confirm a run appears under `interviewsim/grade_submission`.
5. Return to the app and confirm a scorecard appears and its PDF downloads.

If a service setting changes after deploy, trigger a redeploy for that service. Never show a secret value while screen sharing.

## 5. Finish the Nonilion import

The official track requires the agent to be imported into the team’s Nonilion office and demonstrated working there. The two supplied hackathon documents do not include the Bot API payload/authentication guide; Nonilion’s public docs currently label the API reference “Soon.” The current `/api/nonilion/webhook` accepts an internal canonical shape and is **not** proof of a working Nonilion integration.

Before the final demo, ask the Nonilion track contact for the current import method, webhook URL format, signature/auth rule, and file-submission format. Then map those verified details in `interviewsim/nonilion.py` and confirm the full start → clarification → file submission → scorecard flow inside Nonilion. Do not send candidate source to an unverified webhook.

## 6. Render track visibility

The Blueprint includes Render Workflows in the submission path. The event screenshot also asks participants to share the finished project on social media and tag Render (LinkedIn, Discord, or Reddit). GitCoders should choose a channel and post the public project link after the deployed demo is ready.

## Current project status

- Built: browser challenge, persistent 45-minute timer, interviewer endpoint with a local fallback, Render Workflow tasks, Judge0 adapter, report/PDF path, and this seven-slide pitch.
- Requires account setup: a Render deploy, model key, Judge0 endpoint access, and Render API key.
- Requires platform confirmation: actual Nonilion import/webhook mapping and a live demo inside Nonilion.
