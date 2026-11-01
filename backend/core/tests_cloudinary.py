"""Production configuration (Cloudinary on, DEBUG off) exercised with Cloudinary's network calls mocked.
Proves the code path works on this Django/library combination; it cannot prove your real account credentials."""
import os
import subprocess
import sys
import tempfile
from django.conf import settings as dj
from django.test import TestCase

BASE = dict(ELLA_SKIP_DOTENV='1', DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='false', DJANGO_SECRET_KEY='x',
            DATABASE_URL='postgres://u:p@localhost:5432/db', FRONTEND_ORIGIN='https://shop.example.com',
            CLOUDINARY_URL='cloudinary://123456:fakesecret@demo-cloud')


def run(code, **extra):
    env = {k: v for k, v in os.environ.items() if k not in BASE and k != 'ALLOW_LOCAL_MEDIA'}
    env.update(BASE, **extra)
    return subprocess.run([sys.executable, '-c', code], cwd=dj.BASE_DIR, env=env, capture_output=True, text=True)


class CloudinaryProductionPathTests(TestCase):
    def test_collectstatic_works_with_cloudinary_enabled(self):
        # Regression: listing cloudinary_storage before staticfiles broke the Render build on Django 5.1
        with tempfile.TemporaryDirectory() as d:
            code = f"import django;django.setup();from django.conf import settings as s;s.STATIC_ROOT={d!r};" \
                   "from django.core.management import call_command;call_command('collectstatic', interactive=False, verbosity=0);print('OK')"
            r = run(code)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'OK'), r.stderr[-500:])

    def test_images_and_videos_use_the_right_cloudinary_storage(self):
        code = '''
import django; django.setup()
from unittest import mock
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from core.models import _video_storage
def fake_upload(f, **o): return {"public_id": (o.get("folder", "") + "/file_abc123").lstrip("/")}
with mock.patch("cloudinary.uploader.upload", side_effect=fake_upload) as up, mock.patch("cloudinary.uploader.destroy", return_value={"result": "ok"}) as de:
    n = default_storage.save("products/lip.png", ContentFile(b"x"))
    print("IMG", n, default_storage.url(n), up.call_args.kwargs["resource_type"])
    v = _video_storage(); vn = v.save("slides/videos/clip.mp4", ContentFile(b"x"))
    print("VID", vn, v.url(vn), up.call_args.kwargs["resource_type"])
    default_storage.delete(n); print("DEL", de.call_args.kwargs["resource_type"])
'''
        r = run(code)
        self.assertEqual(r.returncode, 0, r.stderr[-600:])
        out = {line.split()[0]: line.split() for line in r.stdout.splitlines() if line.split()}
        self.assertTrue(out['IMG'][2].startswith('https://res.cloudinary.com/demo-cloud/image/upload/'), out['IMG'])
        self.assertEqual(out['IMG'][3], 'image')
        self.assertTrue(out['VID'][2].startswith('https://res.cloudinary.com/demo-cloud/video/upload/'), out['VID'])
        self.assertEqual(out['VID'][3], 'video')
        self.assertEqual(out['DEL'][1], 'image')

    def test_invalid_cloudinary_url_is_reported_clearly(self):
        r = run('import django;django.setup()', CLOUDINARY_URL='KEY:SECRET@demo')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cloudinary://", r.stderr)
