# WHOOP Health AI Agent

AI-powered health coach that analyzes your WHOOP wearable data and generates personalized weekly health schedules using Claude AI.

## What it does

- Connects to your WHOOP account via OAuth2
- Fetches your recovery, sleep, strain, and workout data
- Analyzes trends with Claude AI (recovery patterns, sleep quality, training load)
- Generates a weekly schedule with specific workout recommendations, rest days, and sleep targets

## Setup

### 1. WHOOP Developer App

1. Go to [developer.whoop.com](https://developer.whoop.com/) and sign in
2. Create a Team, then create an App
3. Set the redirect URI to `http://localhost:1234`
4. Note your **Client ID** and **Client Secret**

### 2. Anthropic API Key

Get an API key from [console.anthropic.com](https://console.anthropic.com/)

### 3. Install

```bash
cp .env.example .env
# Edit .env with your credentials

pip install -e .
```

### 4. Authenticate with WHOOP

```bash
whoop-agent login
```

This opens your browser to authorize the app. After approval, tokens are saved locally.

## Usage

### Generate Weekly Schedule

```bash
whoop-agent schedule
```

Analyzes your last 14 days of data and generates a personalized weekly plan with:
- Day-by-day workout recommendations
- Sleep targets (bedtime and wake time)
- Recovery strategies
- Overtraining warnings

### Health Summary

```bash
whoop-agent summary
```

Quick overview of your recovery trends, sleep quality, and training load.

### Interactive Chat

```bash
whoop-agent chat
```

Ask questions about your health data in a conversational interface.

### Options

All commands support `--days N` to change the analysis window (default: 14):

```bash
whoop-agent schedule --days 7
whoop-agent summary --days 30
```
