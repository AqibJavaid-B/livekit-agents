
---

# **LiveKit Outbound Calling Agent**

A Python-based telephony agent built on **LiveKit** for automated outbound calls with **AI assistance**. The agent integrates **STT, LLM, TTS, and SIP telephony** to make calls, transcribe conversations, detect voicemails, and transfer calls. Transcripts are automatically uploaded to **AWS S3**.

---

## **Features**

* Automated outbound calls via **SIP trunk**
* Real-time transcription and session recording
* AI-driven conversation handling using:

  * **STT**: AssemblyAI streaming
  * **LLM**: OpenAI GPT-4.1-mini
  * **TTS**: Cartesia Sonic-3
* Background noise suppression using Krisp (BVCTelephony)
* Turn detection with **EnglishModel**
* Answering machine / voicemail detection
* Call transfer between agents
* Transcript and Recording stores on **AWS S3**
* Configurable via `.env.local`

---

## **Project Structure**

```
.
├── src/
│   ├── agent.py                # Assistant agent class with call functions
│   ├── main.py                 # Entrypoint to start the agent session          
│   └── utils/
│       ├── aws_utils.py        # AWS S3 upload helper
│       ├── env_loader.py       # Environment variable loader
│       ├── logger.py           # Logger setup
│       └── prompt_loader.py    # Dynamic prompt loader            # Transcript JSON uploads
└── README.md
```

---

## **Prerequisites**

* Python 3.11+
* LiveKit Cloud project (URL, API key, API secret)
* AWS account with S3 bucket and IAM credentials
* `uv` Python project manager
* `.env.local` file with the following variables (see `src/.env.example`):

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
SIP_OUTBOUND_TRUNK_ID
AGENT_NAME
ELEVEN_API_KEY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION                # canonical region variable (used by LiveKit log drains and app code)
S3_BUCKET_NAME
# Optional:
# AWS_DEFAULT_REGION      # compatibility for boto3-native tools (same value as AWS_REGION)
# AWS_SESSION_TOKEN       # only if using STS temporary credentials
```

---

## **Local Development (Windows)**

### 1) Install `uv`

Use the official installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify installation:

```powershell
uv --version
```

### 2) Clone the repo

```bash
git clone https://github.com/your-org/your-repo
cd outbound-caller-python
```

### 3) Create the virtual environment and install deps

This project uses `uv.lock`. Sync dependencies and create the `.venv`:

```bash
uv sync
```

### 4) Activate the virtual environment

```powershell
.\.venv\Scripts\activate
```

### 5) Configure environment variables

Copy the example file and update values:

```bash
copy src\.env.example src\.env.local
```

### 5) Run the agent locally (dev)

From the `src/` directory:

```bash
cd src
uv run main.py dev
```

> Your worker is now running and waiting for dispatches to make outbound calls.

---

## **LiveKit Cloud Deployment**

### 1) Install the LiveKit CLI

Follow the official CLI install guide:

https://docs.livekit.io/cli/

### 2) Login to LiveKit Cloud

```bash
lk login
```

### 3) Deploy the agent

From the repo root:

```bash
lk agent deploy
```

### 4) Tail logs

```bash
lk agent logs
```

### References

* https://docs.livekit.io/intro/overview/
* https://docs.livekit.io/agents/

---

## **Managing Secrets with LiveKit CLI**

### Using a secrets file

If you don’t pass any arguments, the CLI will look for an environment file and prompt you to load secrets. Supported files:

* `.env`
* `.env.local`
* `.env.production`

You can explicitly specify a secrets file:

```bash
lk agent create --secrets-file=path/to/secrets.env
```

> The CLI copies all values from the file, except for LiveKit Cloud credentials.

### Providing secrets individually

Use the `--secrets` flag for each secret:

```bash
lk agent update-secrets --secrets "SECRET_A=foo" --secrets "SECRET_B=bar"
```

### Overwriting all secrets

By default, provided secrets are added/updated without removing existing secrets. To overwrite all secrets:

```bash
lk agent update-secrets --secrets-file=new-secrets.env --overwrite
```

---

## **Making a Call**

Dispatch an agent to make a call using the CLI:

```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller \
  --metadata '{"phone_number": "+1234567890", "transfer_to": "+9876543210"}'
```

* The agent will automatically **prewarm the VAD model**
* Outbound calls are triggered by **JobContext metadata**
* Conversations are transcribed and stored on S3
* AI handles call flow, transfers, and voicemail detection

---

## **Configuration**

* **Environment variables**: `utils/env_loader.py` loads all necessary credentials
* **Logging**: Logs are formatted consistently with timestamps

---

## **Functions**

* `Assistant.transfer_call(ctx)` → Transfers the call to another number
* `Assistant.end_call(ctx)` → Ends the call safely
* `Assistant.detected_answering_machine(ctx)` → Detects voicemail and ends the call
* `upload_transcript_to_s3(content, key)` → Saves transcripts to S3
* `load_prompt(metadata)` → Loads and formats prompts for the AI agent

---

## **S3 Directory Notes**

* `recordings/` → S3 storage of room recordings (MP4)
* `transcripts/` → S3 upload key prefix `transcripts/{call_id}.json`

---

## **Logging**

All logs use `utils/logger.py` for consistent formatting:

```
[YYYY-MM-DD HH:MM:SS] [INFO] Message
[YYYY-MM-DD HH:MM:SS] [ERROR] Message
```

---

## **Contributing**

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with des
