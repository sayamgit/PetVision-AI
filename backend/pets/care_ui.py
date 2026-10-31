"""Owner-only display context. Contact data never enters the AI subject."""
import re
def vet_contact(pet, user):
    if not pet or pet.owner_id != user.pk:
        return None
    digits = re.sub(r'[^0-9]', '', pet.vet_phone)
    if not 7 <= len(digits) <= 15:
        return None
    return {'name': pet.vet_name or 'Saved veterinarian', 'phone': pet.vet_phone,
            'dial': ('+' if pet.vet_phone.strip().startswith('+') else '') + digits}
