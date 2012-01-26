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
            # Since we are in change view and not handling any POST,
            # try to lock instance
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
        """
        Before actually saving an existing model, check that model was actually
        locked by user (and in the "window" sending the POST).

        If something goes wrong, hide a private error flag in the form and
        raise a ValidationError. Private error flag will be used later by JS.
        """
        obj = self.instance
        if obj.pk is not None:
            original_modified_at = self.cleaned_data.get('original_modified_at', None)
            original_locked_at = self.cleaned_data.get('original_locked_at', None)
            if not obj.is_locked:
                if original_modified_at == obj.modified_at.replace(microsecond=0):
                    # obj was surprisingly not locked by user, but since it has
                    # not been modified, don't warn user, just lock and pretend
                    # everything is ok
                    obj.lock_for(obj._request_user)
                else:
                    self._locking_error_when_saving = 'not_locked_and_modified'
                    raise forms.ValidationError('Locking problem !')
            elif not obj.is_locked_by(obj._request_user):
                # obj is locked by someone else!
                self._locking_error_when_saving = 'locked_by_someone_else'
                raise forms.ValidationError('Locking problem !')
            elif original_locked_at != obj.locked_at.replace(microsecond=0):
                # obj has been locked by current user in another window!
                self._locking_error_when_saving = 'was_already_locked'
                raise forms.ValidationError('Locking problem !')

        return self.cleaned_data