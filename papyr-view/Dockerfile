FROM python:3.12-slim

# Pillow's wheels are manylinux, so there is nothing to compile.
RUN pip install --no-cache-dir "pillow>=10.0"

WORKDIR /app
COPY app.py .

EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8081/healthz',timeout=3)"

CMD ["python", "-u", "app.py"]
