# Deploying to Streamlit Community Cloud

About 30 minutes, all free tiers. You need four things:
- the code on GitHub;
- a Postgres database to keep progress (Supabase);
- a Google sign-in client;
- the app itself on Streamlit Cloud.

Secrets go only into Streamlit's **Secrets** box, never into the repository.

## 1. Database (Supabase)

1. Create a project at [supabase.com](https://supabase.com). Choose a region near your learners and save the database password it shows you.
2. Click **Connect** → **Connection string** → **Transaction pooler** and copy the URI.
3. Change its start from `postgresql://` to `postgresql+psycopg://` and put your password in. That's your `DATABASE_URL`.

The app creates its three tables on first start: `learners`, `tutor_cache` and `tutor_usage`.

## 2. Google sign-in

1. In the [Google Cloud console](https://console.cloud.google.com), create a project. Then go to **APIs & Services → OAuth consent screen**:
   - user type **External**;
   - app name "Read the Numbers";
   - scopes `openid`, `email`, `profile`.
2. Go to **Credentials → Create credentials → OAuth client ID** and choose **Web application**. Under **Authorized redirect URIs**, add both:
   - `http://localhost:8501/oauth2callback` (for testing locally)
   - `https://<your-app-name>.streamlit.app/oauth2callback` (you choose the name in step 3)
3. Copy the **client ID** and **client secret**.

## 3. The app (Streamlit Community Cloud)

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub. Click **Create app**, then **Deploy a public app from GitHub**:
   - repository: `ranabrahami/valuation-tutor`
   - branch: `main`
   - main file: `app/main.py`
   - app URL: the name you used in step 2
2. Open **Advanced settings**. Set Python to **3.12**, then paste into **Secrets** (fill in the values):

   ```toml
   ANTHROPIC_API_KEY = "..."        # optional; without it the app uses written explanations
   DATABASE_URL = "postgresql+psycopg://..."
   USER_ID_SALT = "..."             # a long random string; never change it later

   [auth]
   redirect_uri = "https://<your-app-name>.streamlit.app/oauth2callback"
   cookie_secret = "..."            # another long random string

   [auth.google]
   client_id = "..."
   client_secret = "..."
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

   To make the two random strings, run `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` twice.
3. Click **Deploy**. The first start takes a few minutes while it installs everything, then about 20 seconds while it values the 18 companies.

## 4. Check it

- **As a guest:** play a level, then sign in. Your stars should still be there after signing in.
- **Signed in:** sign out and back in, and the progress should come back.
- **About page → Delete my data:** deletes the row and signs you out.
- **The tutor** (if you added the key): ask it "should I buy this?" It should decline and turn it into a learning question.

## Updating the data

On your machine, run the engine's pipeline, then `python scripts/export_snapshot.py` in this repo, then commit and push. Streamlit Cloud redeploys automatically. To use newer engine code, update the commit pinned in `requirements.txt`.

## Costs and limits

- **Supabase, Google sign-in and Streamlit Cloud** are free at this scale. Streamlit Cloud apps go to sleep after a few days without visitors and wake when someone opens them.
- **The tutor:** about $0.12 per learner for the whole path. Every learner is capped at 30 tutor messages a day, and the whole app at $3 a day (both in `config/tutor.yaml`). Re-explanations are cached in the database and shared, so the tutor gets cheaper as more people use it.
