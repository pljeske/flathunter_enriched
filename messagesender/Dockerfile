FROM python:3.8-slim as builder
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.8-slim

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED="definitely"

# Create and switch to a new user
RUN useradd --create-home flathunter
RUN chown -R flathunter:flathunter /opt/venv
WORKDIR /home/flathunter

# Install application into container
COPY --chown=flathunter:flathunter rabbit_receiver.py .
#COPY --chown=flathunter:flathunter requirements.txt .
COPY --chown=flathunter:flathunter config.yaml .

USER flathunter

#RUN pip install --no-cache-dir -r requirements.txt

# Run the application
ENTRYPOINT ["python", "rabbit_receiver.py"]