import io
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from core.models import HeroSlide

MP4 = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom' + b'\x00' * 200
WEBM = b'\x1a\x45\xdf\xa3' + b'\x00' * 200


def video(data=MP4, name='clip.mp4'):
    return SimpleUploadedFile(name, data, content_type='video/mp4')


def png():
    b = io.BytesIO(); Image.new('RGB', (20, 10), (180, 90, 110)).save(b, 'PNG')
    return SimpleUploadedFile('s.png', b.getvalue(), content_type='image/png')


class SlideTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng-pass!x', name='A', is_staff=True)
        self.cust = User.objects.create_user(email='c@example.com', password='Str0ng-pass!x', name='C')
        self.c = APIClient(); self.c.force_login(self.admin)

    def add(self, media=None, **extra):
        return self.c.post('/api/admin/slides/', {'video': media or video(), **extra}, format='multipart')

    def test_upload_video_slide_and_it_appears_publicly(self):
        r = self.add(title='New season', subtitle='Fresh lip colours', button_label='Shop makeup', link_url='/shop?category=makeup')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['media_type'], 'video')
        pub = APIClient().get('/api/slides/').json()
        self.assertEqual(len(pub), 1)
        self.assertEqual((pub[0]['title'], pub[0]['media_type']), ('New season', 'video'))
        self.assertTrue(pub[0]['video'].startswith('/media/slides/videos/'))
        self.assertNotIn('is_active', pub[0]); self.assertNotIn('sort_order', pub[0])

    def test_newest_slide_is_first_in_admin_and_public_order(self):
        self.add(title='Earlier')
        self.add(title='Latest')
        self.assertEqual(
            [slide['title'] for slide in self.c.get('/api/admin/slides/').json()],
            ['Latest', 'Earlier'],
        )
        self.assertEqual(
            [slide['title'] for slide in APIClient().get('/api/slides/').json()],
            ['Latest', 'Earlier'],
        )

    def test_webm_and_image_slides_accepted(self):
        self.assertEqual(self.add(video(WEBM, 'a.webm')).status_code, 201)
        r = self.c.post('/api/admin/slides/', {'image': png()}, format='multipart')
        self.assertEqual((r.status_code, r.json()['media_type']), (201, 'image'))

    def test_rejects_fake_videos_oversize_and_missing_or_double_media(self):
        self.assertEqual(self.add(video(b'<?php echo 1; ?>' + b'x' * 50, 'evil.mp4')).status_code, 400)
        big = SimpleUploadedFile('big.mp4', MP4 + b'0' * (30 * 1024 * 1024), content_type='video/mp4')
        r = self.add(big); self.assertEqual(r.status_code, 400); self.assertIn('30 MB', str(r.json()))
        self.assertEqual(self.c.post('/api/admin/slides/', {'title': 'x'}, format='multipart').status_code, 400)
        self.assertEqual(self.c.post('/api/admin/slides/', {'video': video(), 'image': png()}, format='multipart').status_code, 400)
        self.assertEqual(HeroSlide.objects.count(), 0)

    def test_link_must_be_safe_and_button_needs_link(self):
        for bad in ('javascript:alert(1)', 'http://insecure.example', '//evil.example', 'shop'):
            self.assertEqual(self.add(link_url=bad).status_code, 400, bad)
        self.assertEqual(self.add(button_label='Shop').status_code, 400)
        self.assertEqual(self.add(button_label='Shop', link_url='https://example.com/x').status_code, 201)

    def test_only_active_slides_in_order_and_reorder(self):
        ids = [self.add(title=t).json()['id'] for t in ('one', 'two', 'three')]
        self.assertEqual([s['title'] for s in APIClient().get('/api/slides/').json()], ['three', 'two', 'one'])
        self.c.patch(f'/api/admin/slides/{ids[1]}/', {'is_active': False}, format='json')
        self.assertEqual([s['title'] for s in APIClient().get('/api/slides/').json()], ['three', 'one'])
        r = self.c.post('/api/admin/slides/reorder/', {'ids': [ids[0], ids[1], ids[2]]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([s['title'] for s in APIClient().get('/api/slides/').json()], ['one', 'three'])
        for bad in ([ids[0]], [ids[0]] * 3, 'x'):
            self.assertEqual(self.c.post('/api/admin/slides/reorder/', {'ids': bad}, format='json').status_code, 400)

    def test_replace_media_switches_type_and_delete_removes_file(self):
        sid = self.add().json()['id']
        r = self.c.patch(f'/api/admin/slides/{sid}/', {'image': png()}, format='multipart')
        self.assertEqual((r.status_code, r.json()['media_type'], r.json()['video']), (200, 'image', None))
        r = self.c.patch(f'/api/admin/slides/{sid}/', {'title': 'Edited'}, format='json')  # text-only edit keeps media
        self.assertEqual((r.json()['title'], r.json()['media_type']), ('Edited', 'image'))
        path = HeroSlide.objects.get(pk=sid).image.path
        import os; self.assertTrue(os.path.exists(path))
        self.assertEqual(self.c.delete(f'/api/admin/slides/{sid}/').status_code, 204)
        self.assertFalse(os.path.exists(path))

    def test_can_add_more_than_ten_slides(self):
        for i in range(12):
            self.assertEqual(self.add(title=str(i)).status_code, 201)
        self.assertEqual(HeroSlide.objects.count(), 12)

    def test_only_staff_can_manage(self):
        sid = self.add().json()['id']
        cc = APIClient(); cc.force_login(self.cust)
        for client in (cc, APIClient()):
            self.assertEqual(client.get('/api/admin/slides/').status_code, 403)
            self.assertEqual(client.post('/api/admin/slides/', {'video': video()}, format='multipart').status_code, 403)
            self.assertEqual(client.patch(f'/api/admin/slides/{sid}/', {'title': 'x'}, format='json').status_code, 403)
            self.assertEqual(client.delete(f'/api/admin/slides/{sid}/').status_code, 403)
            self.assertEqual(client.post('/api/admin/slides/reorder/', {'ids': [sid]}, format='json').status_code, 403)
        self.assertEqual(HeroSlide.objects.count(), 1)

    def test_empty_when_no_slides(self):
        self.assertEqual(APIClient().get('/api/slides/').json(), [])
