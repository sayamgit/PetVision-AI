from django import forms
from .care_content import TOPICS, EMERGENCY_DESCRIPTION

class CareStartForm(forms.Form):
    concern = forms.CharField(max_length=1200, label='What would you like help with?', widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'For example: My cat slept for 10 hours. What should I check?'}))
    topic = forms.ChoiceField(choices=[('', 'Choose a topic')] + TOPICS, label='Which topic fits best?')
    safety = forms.ChoiceField(label='Is any of the following happening now?', help_text=EMERGENCY_DESCRIPTION, choices=[('yes', 'Yes — a possible emergency sign'), ('unsure', 'I am not sure'), ('no', 'No, none of these signs')], widget=forms.RadioSelect)

class FollowupForm(forms.Form):
    duration = forms.ChoiceField(label='How long has this concern been present?', choices=[('', 'Choose an answer'), ('today', 'Started today'), ('days', 'More than a day'), ('weeks', 'A week or longer'), ('unknown', 'Not sure')])
    changed = forms.ChoiceField(label='Is this a change from their usual behavior?', choices=[('', 'Choose an answer'), ('yes', 'Yes'), ('no', 'No'), ('unknown', 'Not sure')])
    activity = forms.ChoiceField(label='How are they behaving when awake?', choices=[('', 'Choose an answer'), ('usual', 'Alert and active as usual'), ('reduced', 'Less active or reluctant to play'), ('extreme', 'Extremely weak or hard to wake'), ('unknown', 'Not sure')])
    intake = forms.ChoiceField(label='How are eating and drinking?', choices=[('', 'Choose an answer'), ('usual', 'Both are normal for this pet'), ('reduced', 'Eating or drinking less'), ('none_recent', 'Not eating or not drinking, for less than 24 hours'), ('none24', 'No food or no water for 24 hours or longer'), ('unknown', 'Not sure')])

    def __init__(self, *args, topic, **kwargs):
        super().__init__(*args, **kwargs)
        if topic == 'skin':
            self.fields['skin_signs'] = forms.ChoiceField(label='Is there persistent scratching, licking, a rash, or hair loss?', choices=[('', 'Choose an answer'), ('yes', 'Yes'), ('no', 'No'), ('unknown', 'Not sure')])
        if topic == 'appetite':
            self.fields['intake'].help_text = 'Use the more concerning answer if food and water intake differ.'
