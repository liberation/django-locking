WARNING: WORK IN PROGRESS

About this fork
===============

Far more intrusive, this fork aims to be lighter and to do less HTTP and DB requests:
- Locking is no longer done through AJAX, it's done directly in admin.py
- JavaScript vars are exported through a template tag, and not through
a JS call to a dynamic view.
- Views are included directly in LockableAdmin (through get_url()), there is
no longer need for custom decorators (to perform permission checks) nor
utils (to fetch lockable models...)

Installation
============

- Add locking to your INSTALLED_APPS.
- Specify settings #FIXME
- Static files
- For any model that requires locking:
    - Specify locking.models.LockableModel as a model base class.
    - Specify locking.admin.LockableAdmin as a ModelAdmin base class.
    - Specify locking.form.LockableForm as a `form` base class of the ModelAdmin.
    - Add `original_locked_at` and `original_modified_at` into your fields of the ModelAdmin.
- Call {% locking_variables %} in the change_form.html (or in a parent).