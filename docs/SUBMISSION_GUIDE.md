# Submission guide - Assignment 1

Required: **public GitHub repository + explanatory video**. No API keys in the repository.

## Step 1 - Run everything once (30 min)
```bash
pip install -r requirements.txt
cp .env.example .env            # add your free Groq key (never commit this file)
pytest -q                       # expect: 37 passed
python eval.py                  # real model; creates results/eval_report.md
```
Open `results/eval_report.md`: these are YOUR real numbers. If a test fails, explain it honestly in the video (for example the model skipped a tool). Paste the summary table into the "Evaluation" section of `README.md`.
Optional but recommended: set up LangSmith first (docs/LANGSMITH.md) so the evaluation traces appear in your project.

## Step 2 - Put the code on GitHub
1. Create a new repository (suggested name `aidtm-student-support-agent-assignment-1`) -> **Public** -> do NOT tick "Add a README".
2. In the project folder:
```bash
git init
git add .
git status                      # CHECK: .env and data/runtime/ must NOT be listed
git commit -m "Assignment 1 - Intelligent Student Support Agent"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```
3. Open the repository link in a **private/incognito window**. If you can see the code, it is public.
4. Search the repository for your key (`gsk_`, `lsv2_`): nothing should be found. If a key was ever committed, **delete it on the provider's website and create a new one**.

## Step 3 - Record the video (10-11 minutes)
Follow `docs/VIDEO_SCRIPT.md`. Your voice must explain the system; a silent screen recording does not meet the requirement. Do not show `.env`. Upload as YouTube **Unlisted** or Google Drive "Anyone with the link", and test the link in incognito.

## Step 4 - Final checklist
- [ ] Repository is public and opens in incognito
- [ ] `.env` and `data/runtime/` are not in the repository; no key anywhere
- [ ] README has setup + run steps and your own evaluation table
- [ ] `results/eval_report.md` is committed (your real run)
- [ ] Video link works in incognito, audio is clear
- [ ] Video covers: architecture, agent flow, tools, memory, retrieval, context handling, tracing, evaluation (accuracy, latency, tokens), code walkthrough, and the five scenarios
