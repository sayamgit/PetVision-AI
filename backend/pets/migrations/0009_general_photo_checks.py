from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion

def preserve_owners(apps,schema_editor):
    db=schema_editor.connection.alias
    for model_name in ('PhotoCheck','Conversation'):
        Model=apps.get_model('pets',model_name)
        for row in Model.objects.using(db).select_related('pet').iterator():
            values={'owner_id':row.pet.owner_id}
            if model_name=='Conversation':
                values['species']=row.photo_check.species if row.photo_check_id else row.pet.species
            Model.objects.using(db).filter(pk=row.pk).update(**values)

class Migration(migrations.Migration):
    dependencies=[('pets','0008_photo_checks'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='photocheck',name='owner',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.CASCADE,related_name='photo_checks',to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='conversation',name='owner',field=models.ForeignKey(null=True,on_delete=django.db.models.deletion.CASCADE,related_name='pet_conversations',to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='conversation',name='species',field=models.CharField(max_length=3,blank=True,default='',choices=[('cat','Cat'),('dog','Dog')])),
        migrations.AddField(model_name='conversation',name='photo_focus',field=models.CharField(max_length=80,blank=True,default='')),
        migrations.RunPython(preserve_owners,migrations.RunPython.noop),
        migrations.AlterField(model_name='photocheck',name='owner',field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='photo_checks',to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name='conversation',name='owner',field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='pet_conversations',to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name='photocheck',name='pet',field=models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.SET_NULL,related_name='photo_checks',to='pets.pet')),
        migrations.AlterField(model_name='conversation',name='pet',field=models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.SET_NULL,related_name='conversations',to='pets.pet')),
    ]
