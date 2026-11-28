import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
import image_library
import projects

def png(rgb):
    def chunk(name,data):
        return struct.pack(">I",len(data))+name+data+struct.pack(">I",zlib.crc32(name+data)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",1,1,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(b"\x00"+bytes(rgb)))+chunk(b"IEND",b"")

class ImageLibraryTests(unittest.TestCase):
    def test_archive_deduplicate_activate_delete_and_saved_revision(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);job={"folder":folder,"metadata":{"duration":2},"clips":[]}
            (folder/"source.media").write_bytes(b"source")
            logo=folder/"logo.png";first=png((255,0,0));second=png((0,0,255))
            logo.write_bytes(first);one=image_library.archive(job)
            self.assertEqual(image_library.archive(job),one)
            projects.save(job,{"name":"Library"})
            prior=projects.read(folder)
            logo.write_bytes(second);two=image_library.archive(job)
            self.assertEqual(len(two),2)
            ident=hashlib.sha256(first).hexdigest()
            image_library.activate(job,ident);self.assertEqual(logo.read_bytes(),first)
            image_library.delete(job,ident);self.assertEqual(logo.read_bytes(),first)
            self.assertEqual(projects.read(folder),prior)
            self.assertEqual(len(image_library.inventory(job)),1)
            with self.assertRaises(ValueError):image_library.activate(job,ident)
    def test_caps_and_paths(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);job={"folder":folder};logo=folder/"logo.png"
            logo.write_bytes(png((1,2,3)))
            with patch.object(image_library,"MAX_TOTAL_BYTES",1):
                with self.assertRaises(ValueError):image_library.archive(job)
            with patch.object(image_library,"MAX_IMAGES",1):
                image_library.archive(job)
                logo.write_bytes(png((4,5,6)))
                with self.assertRaises(ValueError):image_library.archive(job)
            for ident in ("../logo",None,"a"*64):
                with self.assertRaises(ValueError):image_library.delete(job,ident)
            self.assertEqual(len(image_library.inventory(job)),1)
