# MovieBuff

## About

MovieBuff is a [fork of retiolus' MovieBuff](https://codeberg.org/retiolus/moviebuff). MovieBuff is a Django-based web application that allows users to manage their movie watchlists, track watched movies, and share reviews with other users. It integrates with ActivityPub for federated social features, enabling users to follow each other and share activities across different servers.

See it in action at: [https://moviebuff.silversaucer.com](https://moviebuff.silversaucer.com)

With the assistance of Claude, significant changes have been made. The changes can be found in the [`Federation` branch](https://codeberg.org/prcutler/moviebuff/src/branch/federation):

- Federation has been added and is working. Upon rating a movie, a message to the Fediverse is sent with the rating and movie poster.
- Added Dark Mode and made it the default.
- Disabled registration making it a single user instance.
- Update the home page to display Recent Ratings, a Legend, and movie posters for the last four movies rated. Using HTMX, users can browse through the movies rated on the home page and click through to see movie details.
- Made Movie Ratings visible in the movie cards.

MovieBuff is free and open-source software. It is licensed under the GNU General Public License Version 3.

## Installation

1. Fork this repository
2. Clone the repository locally to your computer: `git clone ssh://git@codeberg.org/prcutler/moviebuff.git`
3. Switch to the Federation branch: `git checkout federation`
4. Create a Python virtual environment: `python -m venv .venv`
5. Activate it: `source .venv/bin/activate`
6. Install requirements: `pip install -r requirements.txt`
7. Create your Django secret key: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
8. Copy the `env-example.txt` and save it as `.env` - you'll need the Django secret key for line 1 of your .env
9. Fill out the .env file and remove the parantheses and text after each entry
10. Start the Django server: `python manage.py runserver`

Deploying a Django app is out of scope for this documentation.