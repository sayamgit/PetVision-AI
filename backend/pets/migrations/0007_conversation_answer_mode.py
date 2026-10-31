from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pets', '0006_conversation_gemini_consent_at')]
    operations = [migrations.AddField(model_name='conversation', name='answer_mode', field=models.CharField(blank=True, choices=[('gemini', 'Automatic'), ('reference', 'Local reference guide')], default='', max_length=10))]
