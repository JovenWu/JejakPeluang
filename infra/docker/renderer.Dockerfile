ARG RENDERER_IMAGE
FROM ${RENDERER_IMAGE}
# Browser binaries ship in the image under /ms-playwright; the Python
# package must match that Playwright release exactly.
RUN pip install --no-cache-dir --break-system-packages playwright==1.62.0 httpx==0.28.1
WORKDIR /srv
# Only the fetch/render code — no settings, models, or database access.
COPY services/backend/app/__init__.py app/__init__.py
COPY services/backend/app/renderer.py app/renderer.py
COPY services/backend/app/services/__init__.py services/backend/app/services/fetch.py services/backend/app/services/render.py app/services/
USER pwuser
EXPOSE 9000
CMD ["python3", "-m", "app.renderer"]
