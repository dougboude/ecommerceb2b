from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0004_add_deleted_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="skin",
            field=models.CharField(
                choices=[("warm-editorial", "Warm Editorial"), ("simple-blue", "Simple Blue")],
                default="simple-blue",
                max_length=20,
                verbose_name="theme",
            ),
        ),
    ]
