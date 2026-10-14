# Groq setup

Upload these files into your existing GitHub repository, retaining folder paths.
In Render > AI-Interviewer > Environment add:

AI_PROVIDER=groq
GROQ_API_KEY=your private Groq key
GROQ_MODEL=llama-3.3-70b-versatile

Save and deploy the latest commit. Keep keys out of GitHub. To return to Gemini set AI_PROVIDER=gemini.

This switches question generation and text answer evaluation. MCQs and camera models are unchanged. Audio transcription is unchanged. Free-plan limits can return 429; questions retain the existing template fallback, and failed scoring remains unavailable for retry instead of invented marks. JSON responses still pass the existing schema and evidence validation.

Tests use mocked HTTP; live Groq authentication, latency, and scoring quality must be checked after deployment. API reference: https://console.groq.com/docs/structured-outputs
