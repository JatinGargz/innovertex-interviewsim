# InterviewSim architecture

```mermaid
sequenceDiagram
    actor Candidate
    participant Web as FastAPI app
    participant DB as Render Postgres
    participant WF as Render Workflow
    participant J0 as Judge0 sandbox
    participant LLM as OpenAI-compatible model

    Candidate->>Web: Choose and start a 45-minute round
    Web->>DB: Save challenge ID + server deadline
    Web-->>Candidate: Selected challenge and starter file
    Candidate->>Web: Clarification question
    Web->>LLM: Interviewer context + conversation
    LLM-->>Web: Concise in-character response
    Web-->>Candidate: Interviewer reply
    Candidate->>Web: Submit source
    Web->>WF: Start grade_submission with challenge ID
    par Isolated checks
        WF->>J0: Candidate source + hidden evaluator
        J0-->>WF: Case results
    and Interview rubric
        WF->>LLM: Source + transcript + evidence rubric
        LLM-->>WF: Structured scorecard review
    end
    WF->>DB: Callback with private scorecard
    Web-->>Candidate: Scorecard
```

The web service stores session state and never executes candidate source. Render Workflow tasks coordinate the grader and written rubric review. Candidate code is sent only to the configured Judge0-compatible service with CPU, memory, and network controls. The Nonilion route accepts a canonical event model until its official event schema and reply method are verified.

