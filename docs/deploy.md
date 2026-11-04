# Putting the MediOps Copilot online (free)

The live demo has three parts. Everything is free and all data is simulated.

| Part | Where | Why |
|---|---|---|
| App | Streamlit Community Cloud | Runs `python/app.py` from this GitHub repo |
| Data | Neon (free PostgreSQL) | Holds only the 9 report-level tables the app needs (about 305,000 claims) |
| AI | Visitor's own free Gemini key (optional) | Keeps the owner's key and daily quota safe |

## Why it is safe to share
- The app connects with a **read-only database user** (`mediops_reader`) that can only SELECT.
- The raw patient-level tables are **not copied** to the cloud.
- Questions the AI writes SQL for still pass the guard (SELECT only, approved views only, row limit)
  and run in a read-only transaction with a timeout.
- The owner's AI key is **not** put in the cloud. Visitors can paste their own key in the sidebar.
  It is kept only for that visitor's session (see `llm.set_session_credentials`) and never stored.

## Steps
1. Create a free Neon project and copy its connection string.
2. Add `CLOUD_DATABASE_URL=...` to the private `.env` file.
3. Run `python python/export_to_cloud.py`. It copies the tables, checks row counts, adds indexes and
   creates the read-only user. The read-only connection string is saved in `.env` as `CLOUD_READER_URL`.
4. On https://share.streamlit.io choose **Create app**, pick this repository, branch `main`,
   main file `python/app.py`.
5. In **Advanced settings > Secrets** add one line: `DATABASE_URL = "<the CLOUD_READER_URL value>"`.
6. Deploy. Free apps go to sleep after inactivity; the first visit may take about 30 seconds to wake it.
