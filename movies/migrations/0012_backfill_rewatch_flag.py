"""Mark anything already rewatched as a rewatch.

The boolean is new, but ``rewatch_count`` has been counting since long
before it. A count above one means the member had rewatched that film, so
the flag should say so rather than starting everyone at False.
"""

from django.db import migrations


def set_flag_from_count(apps, schema_editor):
    Watched = apps.get_model("movies", "Watched")
    Watched.objects.filter(rewatch_count__gt=1).update(rewatch=True)


def clear_flag(apps, schema_editor):
    # Reversing drops only the flag; the count it was derived from remains.
    Watched = apps.get_model("movies", "Watched")
    Watched.objects.update(rewatch=False)


class Migration(migrations.Migration):

    dependencies = [
        ("movies", "0011_watched_rewatch"),
    ]

    operations = [
        migrations.RunPython(set_flag_from_count, clear_flag),
    ]
