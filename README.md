# THUVTM HCMC Attendance

A public English-language form for collecting student attendance information. Students can securely edit their own response using a private link. The password-protected admin dashboard supports search, filtering, and UTF-8 CSV export.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ThiMinhThuVu/thuvtm-hcmc-attendance)

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
SECRET_KEY="local-secret" ADMIN_PASSWORD="choose-a-password" .venv/bin/python app.py
```

Open `http://localhost:8000`. The admin dashboard is at `/admin`.

## Publish on Render

1. Push this folder to a GitHub repository.
2. In Render, choose **New → Blueprint** and select the repository.
3. Render reads `render.yaml` and proposes the service name `thuvtm-hcmc-attendance`.
4. Set a strong `ADMIN_PASSWORD` when prompted, then deploy.
5. The public URL will be similar to `https://thuvtm-hcmc-attendance.onrender.com` if the name is available.

The included persistent disk prevents SQLite data from disappearing during redeploys. The Render `starter` plan is specified because persistent disks are not available on free web services. Back up the CSV regularly.

## Environment variables

- `ADMIN_PASSWORD` — required to access the response list and CSV.
- `SECRET_KEY` — long random string used to secure admin sessions.
- `DATABASE_PATH` — defaults to `data/students.db`.
- `PORT` — defaults to `8000`.

Do not publish `.env` or the SQLite database. Student edit tokens are stored only as SHA-256 hashes in the database.
