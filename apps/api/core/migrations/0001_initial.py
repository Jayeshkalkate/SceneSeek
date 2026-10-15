from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Job",
            fields=[
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("status", models.CharField(default="queued", max_length=16)),
                ("input_kind", models.CharField(max_length=8)),
                ("input_path", models.TextField(blank=True, null=True)),
                ("mime", models.CharField(max_length=120)),
                ("bytes", models.IntegerField()),
                ("sha256", models.CharField(db_index=True, max_length=64)),
                ("attempts", models.IntegerField(default=0)),
                ("max_attempts", models.IntegerField(default=3)),
                ("user_id", models.CharField(blank=True, db_index=True, max_length=36, null=True)),
                ("error", models.TextField(blank=True, null=True)),
                ("result", models.JSONField(blank=True, null=True)),
                ("latency_ms", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "jobs", "indexes": [models.Index(fields=["status", "created_at"], name="ix_jobs_status_created")]},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.CharField(max_length=36, primary_key=True, serialize=False)),
                ("google_sub", models.CharField(db_index=True, max_length=64, unique=True)),
                ("email", models.CharField(max_length=320)),
                ("name", models.CharField(blank=True, max_length=200, null=True)),
                ("picture", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_login", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"db_table": "users"},
        ),
        migrations.CreateModel(
            name="TakedownRequest",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("source_url", models.TextField()),
                ("reason", models.TextField()),
                ("contact_email", models.CharField(blank=True, max_length=320, null=True)),
                ("status", models.CharField(default="open", max_length=16)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"db_table": "takedown_requests"},
        ),
        migrations.CreateModel(
            name="MetadataCache",
            fields=[
                ("title_id", models.CharField(max_length=128, primary_key=True, serialize=False)),
                ("data", models.JSONField()),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"db_table": "metadata_cache"},
        ),
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("predicted_title_id", models.CharField(blank=True, max_length=128, null=True)),
                ("correct_title_id", models.CharField(blank=True, max_length=128, null=True)),
                ("verdict", models.CharField(max_length=16)),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("job", models.ForeignKey(blank=True, db_column="job_id", null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.job")),
            ],
            options={"db_table": "feedback"},
        ),
    ]
