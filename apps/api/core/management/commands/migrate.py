"""``migrate`` that tolerates databases created by the earlier SQLAlchemy-based version.

If the ``jobs``/``users``/... tables already exist with matching columns, the initial
migration is recorded instead of re-creating them (``--fake-initial``), so a plain
``python manage.py migrate`` works on both fresh and legacy databases.
"""
from django.core.management.commands.migrate import Command as BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        options["fake_initial"] = True
        return super().handle(*args, **options)
