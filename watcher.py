name: NHL News Parser Workflow

on:
  repository_dispatch:
    types: [run-watcher]
  workflow_dispatch:

concurrency:
  group: nhl-parser-${{ github.ref }}
  cancel-in-progress: true

jobs:
  run-watcher-and-parser:
    runs-on: ubuntu-latest

    permissions:
      contents: write

    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4 playwright
          playwright install chromium

      - name: Run Watcher
        run: |
          python watcher.py

      # Подтягиваем последние изменения веток перед коммитом базы
      - name: Pull latest changes
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git pull origin main --rebase || true

      - name: Commit and push updated database
        if: always()
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Auto-update sent_news.db [skip ci]"
          file_pattern: "sent_news.db"
          add_options: '-f'
          push_options: '--force'
