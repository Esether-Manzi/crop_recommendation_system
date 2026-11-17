# CropAI — Crop Recommendation System

A Django web app that helps smallholder farmers in Uganda decide what to plant. A farmer records their farms and soil tests, and CropAI recommends the crops best suited to that soil and climate, plans a 4-season rotation, and guides them through the growing season.

## Features

- **Crop recommendations**: the top 5 crops for a soil test, each with a confidence score, a check against the crop's ideal ranges, a "why this crop" breakdown, and a "what if you fertilized" comparison.
- **Input checks**: impossible values are rejected. Values that look like unit slips (for example monthly rainfall entered as annual) or soils unlike anything in the training data get a warning shown above the results.
- **Soil-test guide**: a "How do I fill this in?" panel on the soil forms, with a converter for common lab and kit units.
- **Crop rotation planner**: simulates 4 seasons and tracks how each crop drains or rebuilds soil nutrients.
- **Crop advisory library and season tracker**: stage-by-stage growing guides for 38 crops. The tracker shows the advice for the current week of growth.
- **Harvest feedback**: records the harvest outcome and writes a new, calculated soil record, so the soil state changes over time without a new test.
- **AI farming assistant**: a chat assistant powered by Google Gemini. It can search the web for current information, preferring Ugandan sources such as MAAIF, NARO, UNMA and local farming news, and shows the sources it used. It remembers the conversation and the selected farm. Without an API key, or if Gemini can't be reached, it answers from the advisory library.
- **Farming notes, profile with photo, and self-service password reset.**
- **Farmer dashboard**: counts, active seasons, recent predictions, a 6-month chart, and alerts for low nutrients or out-of-range pH.
- **Branded admin dashboard**: system-wide stats, plus a **Model Information** page showing how the deployed model was trained and how well it scores.

## The model

| | |
|---|---|
| Algorithm | Gaussian Naive Bayes, chosen automatically as the best of 8 compared models |
| Data | 3,800 rows, 38 crops (22 from the Kaggle crop recommendation dataset + 16 synthetic Uganda crops) |
| Inputs | Nitrogen, Phosphorus, Potassium (mg/kg), temperature (°C), humidity (%), pH, rainfall |
| Test accuracy | 97.5% (macro F1 0.975) on a held-out 20% split |
| 10-fold CV accuracy | 96.7% ± 0.8% |

Farmers enter **annual** rainfall in mm. The model works with monthly rainfall, and `backend/ml/features.py` does the conversion. The full training record is in `backend/ml/model/model_card.json` and on the admin's Model Information page.

## Tech stack

- **Backend**: Python 3.12+ (developed on 3.14), Django 6.0, MySQL (`mysqlclient`), `python-decouple` for configuration
- **Machine learning**: scikit-learn, XGBoost, SHAP, pandas, NumPy, joblib
- **Frontend**: Django templates, Bootstrap 5.3 and Font Awesome 6 from CDN. There is no JavaScript build step.
- **Serving**: gunicorn + whitenoise. Pillow handles profile-picture uploads.

## Getting started

### 1. Prerequisites

- Python 3.12 or newer
- MySQL server
- MySQL client headers, needed to build `mysqlclient`. On Ubuntu: `sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config`

### 2. Create the database

```sql
CREATE DATABASE crop_recommendation_db CHARACTER SET utf8mb4;
CREATE USER 'crop_admin'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL ON crop_recommendation_db.* TO 'crop_admin'@'localhost';
-- Needed for `manage.py test`:
GRANT ALL ON test_crop_recommendation_db.* TO 'crop_admin'@'localhost';
```

### 3. Install

```bash
git clone https://github.com/Esether-Manzi/crop_recommendation_system.git
cd crop_recommendation_system
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Configure

Create `backend/.env`:

```ini
SECRET_KEY=change-me
DEBUG=True
DB_NAME=crop_recommendation_db
DB_USER=crop_admin
DB_PASSWORD=choose-a-password
DB_HOST=localhost
DB_PORT=3306

# Optional
# ALLOWED_HOSTS=127.0.0.1,localhost
# GEMINI_API_KEY=...            # live AI chat; without it the offline fallback answers
# GEMINI_MODEL=gemini-3.5-flash-lite
# GEMINI_WEB_SEARCH=True        # web search needs a key with billing on (5,000 free searches/month)
# GEMINI_DAILY_LIMIT=50         # AI replies per farmer per day
# USE_HTTPS=False               # set True only once the site is served over https://
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=  EMAIL_PORT=587  EMAIL_HOST_USER=  EMAIL_HOST_PASSWORD=  EMAIL_USE_TLS=True
# DEFAULT_FROM_EMAIL=
```

Without SMTP settings, password-reset emails are printed to the server console.

Get a Gemini API key at https://aistudio.google.com/. Web search only works on a key with billing turned on: Google gives 5,000 free searches a month, then charges per search. With a free-tier key the assistant still answers, just without searching.

### 5. Set up and run

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py loaddata advisory_seed
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py runserver
```

`loaddata advisory_seed` loads the crop advisory library. Open http://127.0.0.1:8000/ for the app and http://127.0.0.1:8000/admin/ for the admin dashboard.

## Retraining the model

The trained model is checked in under `backend/ml/model/`, so nothing trains on deploy. To retrain from the datasets in `backend/ml/datasets/`, run from `backend/`:

```bash
../.venv/bin/python manage.py train_model
```

This compares 8 models with 10-fold cross-validation, grid search and significance tests, deploys the best one, and writes the model card. A full run takes about 12 minutes. Useful options:

- `--no-tune --folds 3`: a quick check
- `--output-dir <dir>`: experiment without replacing the live model
- `--deploy <model name>`: deploy a specific model instead of the best

Restart the server after retraining, because the model is loaded at startup.

## Running tests

```bash
cd backend
../.venv/bin/python manage.py test
```

The test database needs the `test_crop_recommendation_db` grant from step 2. Without it, `manage.py test recommendations` still runs, because those tests don't use the database.

## Deploying

- Set `DEBUG=False`, a strong `SECRET_KEY`, and `ALLOWED_HOSTS`. With `DEBUG=False`, the basic security headers turn on automatically.
- Set `USE_HTTPS=True` once the site is served over HTTPS. This turns on the SSL redirect, HSTS and secure cookies.
- Run `manage.py collectstatic`. whitenoise then serves the static files.
- Serve with gunicorn, e.g. `gunicorn config.wsgi` from `backend/`.
- Django serves uploaded media (`/media/`) only when `DEBUG=True`. In production, configure your web server (e.g. nginx) to serve `backend/media/`.

## Project structure

```
crop_recommendation_system/
├── requirements.txt
├── documentation/          # developer notes
├── raw/                    # original Kaggle CSVs (reference only)
└── backend/                # Django project (manage.py)
    ├── config/             # settings, URLs, custom admin site
    ├── accounts/           # users, roles, profile, password reset
    ├── farms/              # farms and soil records
    ├── recommendations/    # predictions and recommendation service
    ├── rotation/           # 4-season rotation planner
    ├── advisory/           # crop guides and season tracker
    ├── feedback/           # harvest feedback and soil updates
    ├── dashboard/          # farmer dashboard and landing page
    ├── ai/                 # chat assistant
    ├── notes/              # private farming notes
    ├── ml/                 # training pipeline, predictor, explainer, datasets, model
    ├── templates/
    └── static/
```

`PROJECT_SUMMARY.md` has a longer module-by-module write-up.

## Credits

Crop photos are from Wikimedia Commons. Attribution is on the app's `/credits/` page. The base crop dataset is the Kaggle crop recommendation dataset.

## License

MIT. See [LICENSE](LICENSE).
