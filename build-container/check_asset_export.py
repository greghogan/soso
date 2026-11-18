#!/usr/bin/env python3
"""Image/PDF export regressions, run inside the document-builder container."""
import hashlib
import random
import importlib.util
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
import fitz
from PIL import Image
spec=importlib.util.spec_from_file_location('export_site',Path(__file__).with_name('export_site.py'))
exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)

class AssetExportTests(unittest.TestCase):
    def test_jxl_decode_preserves_pixels_without_adding_png_color_chunks(self):
        import json,subprocess
        helper=Path(__file__).resolve().parents[1]/'shared/raster_assets.py'
        spec=importlib.util.spec_from_file_location('raster_fixture',helper)
        raster=importlib.util.module_from_spec(spec);spec.loader.exec_module(raster)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'manifests').mkdir();raster.ROOT=root
            image=Image.new('RGB',(16,16),(120,80,30));image.save(root/'source.png')
            subprocess.run(['cjxl',str(root/'source.png'),str(root/'master.jxl'),'-d','0','-e','1'],check=True,capture_output=True)
            (root/'manifests/raster-masters.json').write_text(json.dumps({'assets':[{
                'path':'master.jxl','reversible_jpeg':False,
                'decoded_rgb_sha256':hashlib.sha256(image.tobytes()).hexdigest()}]}))
            decoded=raster.decoded_asset(root/'master.jxl',root/'cache')
            with Image.open(decoded) as result:
                self.assertEqual(result.tobytes(),image.tobytes())
                for key in ('gamma','chromaticity','srgb'):
                    self.assertNotIn(key,result.info)

    def test_lossless_conversion_updates_local_reader_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);web=root/'events/example/2027/web';web.mkdir(parents=True)
            image=Image.new('RGB',(200,100),'navy');image.save(web/'figure.png')
            (web/'index.html').write_text('<img src="figure.png"><p>Creator · CC BY 4.0</p><a href=\"https://example.org/figure.png\">Source</a>')
            (web/'responsive.html').write_text('<img src="./figure.png?v=2#crop" srcset="figure.png 1x, ./figure.png?v=2 2x"><style>.picture{background:url(./figure.png#mask)}</style>')
            paths=[p.relative_to(root) for p in web.iterdir()]
            exporter.optimize_web_images(root,paths)
            self.assertFalse((web/'figure.png').exists())
            self.assertEqual(Image.open(web/'figure.webp').tobytes(),image.tobytes())
            self.assertEqual((web/'index.html').read_text(),'<img src="figure.webp"><p>Creator · CC BY 4.0</p><a href=\"https://example.org/figure.png\">Source</a>')
            self.assertIn((web/'figure.webp').relative_to(root),paths)
            responsive=(web/'responsive.html').read_text()
            self.assertIn('src="./figure.webp?v=2#crop"',responsive)
            self.assertIn('srcset="figure.webp 1x, ./figure.webp?v=2 2x"',responsive)
            self.assertIn('url(./figure.webp#mask)',responsive)


    def test_web_photo_policy_preserves_unselected_and_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);web=root/'web';web.mkdir()
            image=Image.frombytes('RGB',(300,300),random.Random(17).randbytes(300*300*3))
            image.save(web/'photo.webp',lossless=True)
            image.save(web/'diagram.webp',lossless=True)
            alpha=image.convert('RGBA');alpha.putalpha(128);alpha.save(web/'transparent.webp',lossless=True)
            digest=hashlib.sha256(image.tobytes()).hexdigest()
            paths=[p.relative_to(root) for p in web.iterdir()]
            # First no assets are selected, so no lossy encoding is allowed.
            exporter.optimize_web_images(root,paths)
            self.assertEqual(Image.open(web/'diagram.webp').convert('RGB').tobytes(),image.tobytes())
            exporter.optimize_web_images(root,paths,[digest])
            self.assertNotEqual(hashlib.sha256(Image.open(web/'photo.webp').convert('RGB').tobytes()).hexdigest(),digest)
            self.assertEqual(Image.open(web/'transparent.webp').tobytes(),alpha.tobytes())

    def test_shared_pdf_image_uses_largest_placement(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'guide.pdf';doc=fitz.open()
            stream=BytesIO();Image.new('RGB',(600,600),'navy').save(stream,format='PNG')
            first=doc.new_page();xref=first.insert_image(fitz.Rect(20,20,92,92),stream=stream.getvalue())
            second=doc.new_page();second.insert_image(fitz.Rect(20,20,308,308),xref=xref)
            doc.save(path);doc.close();before=path.read_bytes()
            self.assertEqual(exporter.optimize_pdf(path),0)
            self.assertEqual(path.read_bytes(),before)

    def test_pdf_photo_encoding_is_opt_in_and_avoids_jpeg_reencoding(self):
        with tempfile.TemporaryDirectory() as directory:
            image=Image.frombytes('RGB',(300,300),bytes((i*31+i//677)%256 for i in range(300*300*3)))
            digest=hashlib.sha256(image.tobytes()).hexdigest()
            path=Path(directory)/'photo.pdf';doc=fitz.open();page=doc.new_page()
            stream=BytesIO();image.save(stream,format='PNG')
            page.insert_image(fitz.Rect(20,20,164,164),stream=stream.getvalue())
            doc.save(path);doc.close()
            self.assertEqual(exporter.optimize_pdf(path),0)
            self.assertEqual(exporter.optimize_pdf(path,[digest]),1)
            result=fitz.open(path);xref=result[0].get_images()[0][0]
            extracted=result.extract_image(xref)
            self.assertEqual(extracted['ext'],'jpeg')
            decoded=Image.open(BytesIO(extracted['image'])).convert('RGB')
            digest=hashlib.sha256(decoded.tobytes()).hexdigest();result.close()
            before=path.read_bytes()
            self.assertEqual(exporter.optimize_pdf(path,[digest]),0)
            self.assertEqual(path.read_bytes(),before)

    def test_pdf_resize_preserves_text_link_and_page(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'guide.pdf';doc=fitz.open();page=doc.new_page()
            # Structured noise compresses poorly enough to exercise the smaller-output guard.
            image=Image.frombytes('RGB',(600,600),bytes((i*31+i//677)%256 for i in range(600*600*3)))
            stream=BytesIO();image.save(stream,format='PNG')
            page.insert_image(fitz.Rect(20,20,92,92),stream=stream.getvalue())
            page.insert_text((20,150),'Searchable science')
            page.insert_link({'kind':fitz.LINK_URI,'from':fitz.Rect(20,140,150,155),'uri':'https://example.org/source'})
            doc.save(path);doc.close()
            self.assertEqual(exporter.optimize_pdf(path,[hashlib.sha256(image.tobytes()).hexdigest()]),1)
            result=fitz.open(path)
            self.assertIn('Searchable science',result[0].get_text())
            self.assertEqual(result[0].get_links()[0]['uri'],'https://example.org/source')
            self.assertEqual(result[0].get_images()[0][2:4],(300,300))
            self.assertEqual(result[0].rect,fitz.Rect(0,0,595,842))
            result.close()

if __name__=='__main__':unittest.main()
