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

      - name: Commit and push updated database
        if: always()
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Auto-update sent_news.db [skip ci]"
          file_pattern: "sent_news.db"
          add_options: '-f'
          push_options: '--force'
