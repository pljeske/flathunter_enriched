# Flathunter

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat)](https://github.com/RichardLitt/standard-readme)
[![Lint Code Base](https://github.com/flathunters/flathunter/actions/workflows/linter.yml/badge.svg)](https://github.com/flathunters/flathunter/actions/workflows/linter.yml)
[![Tests](https://github.com/flathunters/flathunter/actions/workflows/tests.yml/badge.svg)](https://github.com/flathunters/flathunter/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/flathunters/flathunter/branch/master/graph/badge.svg)](https://codecov.io/gh/flathunters/flathunter)

A Telegram bot to help people with their flat search

## Description

Flathunter is a Python application which periodically [scrapes](https://en.wikipedia.org/wiki/Web_scraping) property listings sites that the user has configured to find new apartment listings, and sends notifications of the new apartment to the user via [Telegram](https://en.wikipedia.org/wiki/Telegram_%28software%29).

## Table of Contents

- [Background](#background)
- [Install](#install)
    - [Installation on Linux](#installation-on-linux)
- [Usage](#usage)
	- [Command-line Interface](#command-line-interface)
	- [Web Interface](#web-interface)
- [Testing](#testing)
- [Credits](#credits)
- [Contributing](#contributing)
- [License](#license)

## Background

There are at least four different rental property marketplace sites that are widely used in Germany - [ImmoScout24](https://www.immobilienscout24.de/), [immowelt](https://www.immowelt.de/), [WG-Gesucht](https://www.wg-gesucht.de/) and [ebay Kleinanzeigen](https://www.ebay-kleinanzeigen.de/). Most people end up searching through listings on all four sites on an almost daily basis during their flat search.
In Italy on the other hand, [Idealista](https://www.idealista.it), [Subito](https://www.subito.it) and [Immobiliare.it](https://www.immobiliare.it) are very common for flat and property hunting.

With Flathunter, instead of visiting the same pages on the same four sites every day, you can set the system up to scan every site, filtering by your search criteria, and notify you when new flats become available that meet your criteria.

## Install

Flathunter is a Python (v3.7+) project - you will need Python3 installed to run the code. We recommend using [pipenv](https://pipenv-fork.readthedocs.io/en/latest/) to setup and configure your project. Install `pipenv` according to the instructions on the `pipenv` site, then run:

```sh
$ pipenv install
```

from the project directory to install the dependencies. Once the dependencies are installed, and every time you come back to the project in a new shell, run:

```sh
$ pipenv shell
```

to launch a Python environment with the dependencies that your project requires.

Note that a `requirements.txt` file is included in this repository for compatibilty with Google Cloud. It should not be treated as canonical.

For development purposes, you need to install the flathunter module in your current environment. Simply run:

```sh
pip install -e .
```

### Installation on Linux
(tested on CentOS Stream)

First clone the repository
```
cd /opt
git clone https://github.com/flathunters/flathunter.git
```
add a new User and configure the permissions
```
useradd flathunter
chown flathunter:flathunter -R flathunter/
```
Next install pipenv for the new user
```
sudo -u flathunter pip install --user pipenv
cd flathunter/
sudo -u flathunter /home/flathunter/.local/bin/pipenv install
```
Next configure the config file and service file to your liking. Then move the service file in place:
```
mv flathunter/sample-flathunter.service /lib/systemd/system/flathunter.service
```
At last you just have to start flathunter
```
systemctl enable flathunter --now
```
If you're using SELinux the following policy needs to be added:
```
chcon -R -t bin_t /home/flathunter/.local/bin/pipenv
```

### Configuration

Before running the project for the first time, copy `config.yaml.dist` to `config.yaml`. The `urls` and `telegram` sections of the config file must be configured according to your requirements before the project will run. 

#### URLs

To configure the searches, simply visit the property portal of your choice (e.g. ImmoScout), configure the search on the website to match your search criteria, then copy the URL of the results page into the config file. You can add as many URLs as you like, also multiple from the same website if you have multiple different criteria (e.g. running the same search in multiple different Bezirke).

 * Currently, ebay-kleinanzeigen, immowelt WG-Gesucht and Idealista only crawl the first page, so make sure to **sort by newest offers**.
 * Your links should point to the German version of the websites (in the case of ebay-kleinanzeigen, immowelt, immoscout and wggesucht), since it is tested only there. Otherwise you might have problems.
 * For Idealista, the link should point to the Italian version of the website, for the same reason reported above.
 * For Immobiliare, the link should point to the Italian version of the website, for the same reasons reported above.
 * For Subito, the link should point to the Italian version of the website, for the same reasons reported above.

#### Telegram

To be able to send messages to you over Telegram, you need to register a new bot with the [BotFather](https://telegram.me/BotFather) for `flathunter` to use. Through this process, a "Bot Token" will be created for you, which should be configured under `bot_token` in the config file.

To know who should Telegram messages should be sent to, the "Chat IDs" of the recipients must be added to the config file under `receiver_ids`. To work out your own Chat ID, send a message to your new bot, then run:


```
$ curl https://api.telegram.org/bot[BOT-TOKEN]/getUpdates
```

to get list of messages the Bot has received. You will see your Chat ID in there.

#### 2Captcha
Some sites (including ImmoScout24) implement Captcha to avoid being crawled by evil web scrapers. Since our crawler is not an evil one, the people at [2captcha](https://2captcha.com) provide us a service that helps you solve them. Head to the `2captchas` website, register and pay 3$ for 1000 solved captcha's! Check the `config.yaml.dist` on how to configure `2captcha` with `flathunter`. You will also be required to install a [chrome-web-driver](https://chromedriver.chromium.org/downloads) on your system that runs `flathunter`. The installation procedure varies depending on your system, a quick search on the internet should answer this question. **At this time, ImmoScout24 cannot be crawled by flathunter without using 2Captcha**.

#### Proxy
It's common that websites use bots and crawler protections to avoid being flooded with possibly malicious traffic. This can cause some issues when crawling, as we will be presented with a bot-protection page.
To circumvent this, we can enable proxies with the configuration key `use_proxy_list` and setting it to `True`.
Flathunt will crawl a [free-proxy list website](https://free-proxy-list.net/) to retrieve a list of possible proxies to use, and cycle through the so obtained list until an usable proxy is found.  
*Note*: there may be a lot of attemps before such an usable proxy is found. Depending on your region or your server's internet accessibility, it can take a while.

#### Google API

To use the distance calculation feature a [Google API-Key](https://developers.google.com/maps/documentation/javascript/get-api-key) is needed and requires the Distance Matrix API to be enabled. (This is NOT free)

Since this feature is not free, it is "disabled". Read line 62 in hunter.py to re-enable it.

### Google Cloud Deployment

You can run `flathunter` on Google's App Engine, in the free tier, at no cost. To get started, first install the [Google Cloud SDK](https://cloud.google.com/sdk/docs) on your machine, and run:

```
$ gcloud init
```

to setup the SDK. You will need to create a new cloud project (or connect to an existing project). The Flathunters organisation uses the `flathunters` project ID to deploy the application. If you need access to deploy to that project, contact the maintainers.

```
$ gcloud config set project flathunters
```

You will need to add the project ID to `config.yaml` under the key `google_cloud_project_id`.

Google Cloud [doesn't currently support Pipfiles](https://stackoverflow.com/questions/58546089/does-google-app-engine-flex-support-pipfile). To work around this restriction, the `Pipfile` and `Pipfile.lock` have been added to `.gcloudignore`, and a `requirements.txt` file has been generated using `pip freeze`. 

If the Pipfile has been updated, you will need to remove the line `pkg-resources==0.0.0` from `requirements.txt` for a successful deploy.

To deploy the app, run:

```
$ gcloud app deploy
```

Your project will need to have the [Cloud Build API](https://console.developers.google.com/apis/api/cloudbuild.googleapis.com/overview) enabled, which requires it to be linked to a billing-enabled account. It also needs [Cloud Firestore API](https://console.cloud.google.com/apis/library/firestore.googleapis.com) to be enabled for the project. Firestore needs to be configured in [Native mode](https://cloud.google.com/datastore/docs/upgrade-to-firestore).

Instead of running with a timer, the web interface depends on periodic calls to the `/hunt` URL to trigger searches (this avoids the need to have a long-running process in the on-demand compute environment). You can configure Google Cloud to automatically hit the URL by deploying the cron job:

```
$ gcloud app deploy cron.yaml
```

## Usage

### Command-line Interface

By default, the application runs on the commandline and outputs logs to `stdout`. It will poll in a loop and send updates after each run. The `processed_ids.db` file contains details of which listings have already been sent to the Telegram bot - if you delete that, it will be recreated, and you may receive duplicate listings.

```
usage: flathunt.py [-h] [--config CONFIG]

Searches for flats on Immobilienscout24.de and wg-gesucht.de and sends results
to Telegram User

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG, -c CONFIG
                        Config file to use. If not set, try to use
                        '~git-clone-dir/config.yaml'
  --heartbeat INTERVAL, -hb INTERVAL
			Set the interval time to receive heartbeat messages to check that the bot is
                        alive. Accepted strings are "hour", "day", "week". Defaults to None.
```

### Web Interface

You can alternatively launch the web interface by running the `main.py` application:

```
$ python main.py
```

This uses the same config file as the Command-line Interface, and launches a web page at [http://localhost:8080](http://localhost:8080).

Alternatively, run the server directly with Flask:

```
$ FLASK_APP=flathunter.web flask run
```

## Testing

The test suite can be run with `pytest`:

```sh
$ pytest
```

from the project root. If you encounter the error `ModuleNotFoundError: No module named 'flathunter'`, run:

```sh
pip install -e .
```

to make the current project visible to your pip environment.

## Maintainers

This project is maintained by the members of the [Flat Hunters](https://github.com/flathunters) Github organisation, which is a collection of individual unpaid volunteers who have all had their own processes with flat-hunting in Germany. If you want to join, just ping one of us a message!

## Credits

The original code was contributed by [@NodyHub](https://github.com/NodyHub), whose original idea this project was.

### Contributers

Other contributions were made along the way by

- Bene
- [@tschuehly](https://github.com/tschuehly)
- [@Cugu](https://github.com/Cugu)
- [@GerRudi](https://github.com/GerRudi)
- [@xMordax](https://github.com/xMordax)
- [@codders](https://github.com/codders)

## Contributing

If you want to make a contribution, please check out the contributor code of conduct ([en](CODE_OF_CONDUCT.en.md)/[de](CODE_OF_CONDUCT.de.md)) first. Pull requests are very welcome, as are [issues](https://github.com/flathunters/flathunter/issues). If you file an issue, please include as much information as possible about how to reproduce the issue.
