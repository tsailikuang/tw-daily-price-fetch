name: Daily Taiwan prices

on:
  schedule:
    # 每天 23:00 UTC 執行，等於台灣時間早上 07:00（+8）
    # 你可以按需要改時間，例如：
    # 30 0 * * *  = 每天 00:30 UTC（台灣 08:30）
    - cron: '0 23 * * *'
  workflow_dispatch:  # 手動觸發用，方便測試

jobs:
  fetch-and-save:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install yfinance pandas

      - name: Run fetch script
        run: |
          python fetch_prices.py

      - name: Commit and push daily report
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "chore: update daily price report"
          file_pattern: daily_reports/**
