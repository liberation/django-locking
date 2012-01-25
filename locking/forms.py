# -*- coding: utf-8 -*-

from django import forms
from django.forms.util import ErrorList

class LockableForm(forms.ModelForm):
    original_locked_at = forms.DateTimeField(required=False)
    original_modified_at = forms.DateTimeField(required=False)

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, instance=None):
        super(LockableForm, self).__init__(data=data, files=files, auto_id=auto_id, prefix=prefix,
                 initial=initial, error_class=error_class, label_suffix=label_suffix,
                 empty_permitted=empty_permitted, instance=instance)
        if data is None and self.instance.pk is not None:
            # We are in change view and not handling any POST
            obj = self.instance
            if not obj.is_locked:
                obj.lock_for(obj._request_user)
                obj._is_a_locking_request = True
                self.fields['original_locked_at'].initial = obj.locked_at
                self.fields['original_modified_at'].initial = obj.modified_at
            elif obj.is_locked_by(obj._request_user):
                # obj is already locked by user, do not refresh lock, user
                # will be warned that he is probably editing something twice
                obj._was_already_locked_by_user = True

    def clean(self):
        obj = self.instance
        if obj.pk is not None:
            original_modified_at = self.cleaned_data.get('original_modified_at', None)
            original_locked_at = self.cleaned_data.get('original_locked_at', None)
            if not obj.is_locked:
                if original_modified_at == obj.modified_at.replace(microsecond=0):
                    # obj was not locked, but since it has not been modified,
                    # don't warn user, just lock and pretend everything is right
                    obj.lock_for(obj._request_user)
                else:
                    raise forms.ValidationError('Model was no longer locked and it has been modified since you extracted it (at %s, probably by %s)' % (str(obj.modified_at), str(obj.modified_by)))
            elif not obj.is_locked_by(obj._request_user):
                # obj is locked by someone else!
                raise forms.ValidationError('Model is locked by %s !' % (str(obj.locked_by),))
            elif original_locked_at != obj.locked_at.replace(microsecond=0):
                # obj has been locked by current user in another window!
                raise forms.ValidationError("Model is locked by yourself at %s in another tab !" % (str(obj.locked_at),))

        return self.cleaned_data