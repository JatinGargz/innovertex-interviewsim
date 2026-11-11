# Nonilion Bot API integration boundary

The hackathon problem statement asks for an agent that can run inside Nonilion. The Bot API developer guide is not yet in the project, so this app does not guess at Nonilion's real endpoint, event signature, or file-upload schema.

## Canonical adapter contract

The app currently accepts this normalized event at `POST /api/nonilion/webhook`:

```json
{
  "event_id": "evt-123",
  "room_id": "team-room",
  "user_id": "candidate-7",
  "user_name": "Candidate",
  "text": "start",
  "event_type": "message",
  "source_code": null
}
```

The route returns a `NonilionReply` object containing the response text and session state. The intended commands are `start`, `status`, ordinary clarification questions, and a `file_submission` event containing `source_code`.

## What to map when the guide arrives

Implement the official webhook verification and field mapping in `interviewsim/nonilion.py`, then connect its verified response mechanism in `interviewsim/app.py`. Confirm whether Nonilion expects an inline webhook response or a separate send-message call, how room and user IDs are represented, and how code files are delivered. Do not accept an unverified webhook in a public deployment.

