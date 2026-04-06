# MovieBuff

MovieBuff is a [fork of retiolus' MovieBuff](https://codeberg.org/retiolus/moviebuff). MovieBuff is a Django-based web application that allows users to manage their movie watchlists, track watched movies, and share reviews with other users. It integrates with ActivityPub for federated social features, enabling users to follow each other and share activities across different servers.

See it in action at: [https://moviebuff.silversaucer.com](https://moviebuff.silversaucer.com)

With the assistance of Claude, significant changes have been made:

- Federation has been added and is working. Upon rating a movie, a message to the Fediverse is sent with the rating and movie poster.
- Added Dark Mode and made it the default.
- Disabled registration making it a single user instance.
- Update the home page to display Recent Ratings, a Legend, and movie posters for the last four movies rated. Using HTMX, users can browse through the movies rated on the home page and click through to see movie details.
- Made Movie Ratings visible in the movie cards.

MovieBuff is free and open-source software. It is licensed under the GNU General Public License Version 3.

Todo:

- [ ] Make single user an option with an environment variable.
- [ ] Enable and disable user registration with an environment variable.
- [ ] Add a link back to the Home Page from the top left
- [ ] Add a Code of Conduct and CONTRIBUTING

