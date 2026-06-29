from django.db import migrations


def add_sample_media(apps, schema_editor):
    DecorationItem = apps.get_model("events", "DecorationItem")
    sample_media = {
        "birthday": "/static/media/photos/birthday-balloons.jpg",
        "wedding": "/static/media/photos/wedding-stage.jpg",
        "baby": "/static/media/photos/birthday-balloons.jpg",
        "corporate": "/static/media/photos/luxury-reception.jpg",
        "proposal": "/static/media/photos/birthday.jpg",
        "entries": "/static/media/photos/wedding-stage.jpg",
    }
    for category_slug, image_url in sample_media.items():
        DecorationItem.objects.filter(category__slug=category_slug).update(
            image_url=image_url,
            video_url="/static/media/videos/wedding-showcase.mp4",
        )


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [migrations.RunPython(add_sample_media, migrations.RunPython.noop)]

