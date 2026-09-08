# FootballLife — the web app in one container.
#   docker build -t footballlife .
#   docker run -p 8000:8000 -e FL_SECRET=change-me -v $PWD/donnees_serveur:/data footballlife
# The game base lives in /data (a volume): copy jeu/demo.sqlite or the live
# base there as /data/jeu.sqlite before the first start (see docs/SITE.md).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi "uvicorn[standard]" python-multipart
COPY jeu ./jeu
COPY moteur ./moteur
COPY web ./web
COPY donnees ./donnees
ENV FL_JEU=/data/jeu.sqlite FL_SAISON=2025/26 FL_SECRET=change-me PORT=8000
VOLUME ["/data"]
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn web.app.serveur:app --host 0.0.0.0 --port ${PORT}"]
