FROM joyzoursky/python-chromedriver:3.8

RUN useradd flathunter
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=flathunter:flathunter . /app
WORKDIR /app

RUN export PATH=$PATH:/usr/lib/chromium-browser/

RUN mkdir ./config
COPY --chown=flathunter:flathunter ./config.yaml.dist /app/config/config.yaml

RUN mkdir database && chown flathunter:flathunter -R database
VOLUME /app/database
VOLUME /app/config

USER flathunter

CMD [ "python3", "-u", "flathunt.py", "-c", "/app/config/config.yaml" ]