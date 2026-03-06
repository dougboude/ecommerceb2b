from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0005_alter_user_skin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="skin",
            field=models.CharField(
                choices=[("warm-editorial", "Warm Editorial"), ("simple-blue", "Simple Blue")],
                max_length=20,
                verbose_name="theme",
            ),
        ),
    ]
