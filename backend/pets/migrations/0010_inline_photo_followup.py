from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pets', '0009_general_photo_checks')]
    operations = [
        migrations.AddField(model_name='conversation', name='inline_photo', field=models.BooleanField(default=False)),
        migrations.AddConstraint(model_name='conversation', constraint=models.UniqueConstraint(fields=('photo_check','photo_focus'), condition=models.Q(inline_photo=True), name='unique_inline_photo_focus')),
    ]
