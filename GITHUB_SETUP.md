# GitHub Setup

## 1. Create repository
Create a new **Private** repository.
Do not initialize it with GitHub README/license if you are uploading this seed.

## 2. Push seed

```bash
git init
git add .
git commit -m "chore: bootstrap hackathon repository"
git branch -M main
git remote add origin <REPO_URL>
git push -u origin main
```

## 3. Create dev

```bash
git checkout -b dev
git push -u origin dev
```

Use `dev` for active integration; keep `main` demo-stable.

## 4. Daily flow
For a task:

```bash
git checkout dev
git pull --ff-only
git checkout -b feature/<short-name>
```

After work:
- run `make quick`
- commit
- push
- PR into `dev`

Do not wait for full release checks on every small task.

## 5. Demo checkpoint
When `dev` is stable:
- open PR `dev -> main`
- let the Full Gate run
- run benchmark/rehearsal
- merge only after review

## 6. Repository secrets
When Kloudeks credentials arrive, add them under repository/environment secrets if CI genuinely needs them.
Prefer that normal CI **does not** need a real Kloudeks key.

Never commit the key into `.env`, YAML, tests, screenshots, or documentation.
