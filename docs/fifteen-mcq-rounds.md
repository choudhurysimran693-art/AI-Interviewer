# Fifteen MCQs per aptitude and technical round

Newly generated aptitude and technical round sessions each contain 15 distinct multiple-choice questions. Aptitude draws from quantitative and reasoning content. Technical uses a general software fundamentals bank (data structures, algorithms, SQL, databases, HTTP, testing, security and concurrency). This technical bank is foundational, not role-specific or seniority-calibrated. System-design/deep technical and HR rounds retain their existing formats.

Candidates select options, review or change the selection, and submit. Answer keys stay on the server and scoring uses exact option IDs. Progress, resume, completion and aptitude threshold decisions use the actual saved question set rather than five answers.

Upload the package contents to the repository root and deploy the latest commit in Render. No migration or environment change is required. The package also preserves the earlier optional-device-monitoring fix. Already generated interviews keep their saved questions; use a new assigned session to verify the 15-question format. Do not reset active attempts.

Verify both rounds show 15 questions and clickable options, can proceed beyond question five, and complete after all answers. The automated walkthrough checks incomplete-round rejection and completion after all 15 answers. Production browser verification remains required.
