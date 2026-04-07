# MovieBuff

## About

MovieBuff is a [fork of retiolus' MovieBuff](https://codeberg.org/retiolus/moviebuff). MovieBuff is a Django-based web application that allows users to manage their movie watchlists, track watched movies, and share reviews with other users. It integrates with ActivityPub for federated social features, enabling users to follow each other and share activities across different servers.

See it in action at: [https://moviebuff.silversaucer.com](https://moviebuff.silversaucer.com)

With the assistance of Claude, significant changes have been made. The changes can be found in the [`Federation` branch](https://codeberg.org/prcutler/moviebuff/src/branch/federation):

- Added dark mode and made it the default with a toggle to change light or dark mode on the home page
- Added working Federation based on the buiding blocks present in the app
- Changed Federation to only post when a movie is rated. Also added a Share to Fediverse button using HTMX that appears when a movie is added to the Watched Movies list
- Add an environment variable and code to enable or disable registration (to avoid spammers)
- Disabled the registration pages if the user is unauthenticated and registration is disabled
- Updated the home page to show a legend, the five most recent movies rated, movie posters for the four most recent movies rated, and HTMX to page through the rated movies
- In the Dashboard, added HTMX to page through all the Watched Movies
- In each movie card, added the star ratings for the movie
- Updated the datetime fields to be MON/DAY/YEAR and added commas to the movie's budget
- Added a Font Awesome film icon in the upper left and made it and Moviebuff clickable to return to the home page
- Added a custom footer that matches [silversaucer.com](https://silversaucer.com)
- Added a CONTRIBUTING.md and CODE_OF_CONDUCT.md
- Added installation instructions in the README

MovieBuff is free and open-source software. It is licensed under the GNU General Public License Version 3.

## Installation

1. Fork this repository
2. Clone the repository locally to your computer: `git clone ssh://git@codeberg.org/yourusername/moviebuff.git` (or you can clone this repo if you reall want to: `git clone ssh://git@codeberg.org/prcutler/moviebuff.git`)
3. Switch to the Federation branch: `git checkout federation`
4. Create a Python virtual environment: `python -m venv .venv`
5. Activate it: `source .venv/bin/activate`
6. Install requirements: `pip install -r requirements.txt`
7. Create your Django secret key: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
8. Copy the `env-example.txt` and save it as `.env` - you'll need the Django secret key for line 1 of your .env
9. Fill out the .env file and remove the parantheses and text after each entry
10. Start the Django server: `python manage.py runserver`

Deploying a Django app is out of scope for this documentation.