FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MEAL_PLANNER_DB=/data/meal_planner.db

# Version / release channel, injected by CI and shown in the app's footer badge.
ARG APP_VERSION=""
ARG APP_CHANNEL=""
ENV MEAL_PLANNER_VERSION=$APP_VERSION
ENV MEAL_PLANNER_CHANNEL=$APP_CHANNEL

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import ingredient_parser"

COPY . /app

EXPOSE 8717

RUN mkdir -p /data

CMD ["gunicorn", "-b", "0.0.0.0:8717", "--timeout", "120", "--preload", "meal_planner.app:app"]
