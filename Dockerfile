FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir pip-tools

COPY requirements/base.in requirements/base.in
RUN pip-compile requirements/base.in -o requirements/base.txt \
    && pip install --no-cache-dir -r requirements/base.txt

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "tax_copilot.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
