import os
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from cli_tools import quick_pic


class QuickPicTest(unittest.TestCase):
    def test_candidates_are_latest_five_supported_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "output"
            input_dir.mkdir()
            output_root.mkdir()
            config_path = self._write_config(root, input_dir, output_root)

            for index in range(7):
                path = input_dir / f"photo-{index}.jpg"
                path.write_bytes(b"not decoded during discovery")
                os.utime(path, ns=(index + 1, index + 1))
            (input_dir / "ignore.txt").write_text("x", encoding="utf-8")

            config = quick_pic.load_config(config_path)
            candidates = quick_pic.list_candidates(config)

            self.assertEqual(
                [candidate.path.name for candidate in candidates],
                ["photo-6.jpg", "photo-5.jpg", "photo-4.jpg", "photo-3.jpg", "photo-2.jpg"],
            )
            self.assertNotIn(str(input_dir), str(candidates[0].to_dict()))

    def test_output_directories_include_root_and_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "output"
            input_dir.mkdir()
            (output_root / "animals" / "cats").mkdir(parents=True)
            (output_root / "people").mkdir()
            config = quick_pic.load_config(self._write_config(root, input_dir, output_root))

            directories = quick_pic.list_output_directories(config)

            self.assertEqual(
                [directory.label for directory in directories],
                [
                    "Test images",
                    "Test images/animals",
                    "Test images/animals/cats",
                    "Test images/people",
                ],
            )
            self.assertTrue(all(str(output_root) not in str(item.to_dict()) for item in directories))

    def test_output_discovery_rejects_symlinked_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "output"
            outside = root / "outside"
            input_dir.mkdir()
            output_root.mkdir()
            outside.mkdir()
            (output_root / "escape").symlink_to(outside, target_is_directory=True)
            config = quick_pic.load_config(self._write_config(root, input_dir, output_root))

            labels = [item.label for item in quick_pic.list_output_directories(config)]

            self.assertNotIn("escape", labels)

    def test_output_labels_start_at_dropbox_with_short_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "Dropbox" / "Embedded" / "home_companian" / "images"
            input_dir.mkdir()
            (output_root / "drawings").mkdir(parents=True)
            config = quick_pic.load_config(self._write_config(root, input_dir, output_root))

            labels = [item.label for item in quick_pic.list_output_directories(config)]

            self.assertEqual(
                labels,
                [
                    "D/Embedded/home_companian/images",
                    "D/Embedded/home_companian/images/drawings",
                ],
            )

    def test_candidate_must_remain_in_latest_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "output"
            input_dir.mkdir()
            output_root.mkdir()
            config = quick_pic.load_config(self._write_config(root, input_dir, output_root))
            image = input_dir / "photo.jpg"
            image.write_bytes(b"x")
            candidate = quick_pic.list_candidates(config)[0]
            image.unlink()

            with self.assertRaisesRegex(quick_pic.QuickPicError, "no longer"):
                quick_pic.get_candidate(config, candidate.id)

    def test_output_name_adds_png_and_rejects_paths(self):
        self.assertEqual(quick_pic._output_filename("练习一"), "练习一.png")
        self.assertEqual(quick_pic._output_filename("练习  一"), "练习_一.png")
        self.assertEqual(quick_pic._output_filename("My File   "), "my_file.png")
        for invalid in ("drawing.png", "../drawing", r"..\drawing"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(quick_pic.QuickPicError):
                    quick_pic._output_filename(invalid)

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is required")
    def test_imagemagick_creates_transparent_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "drawing.pgm"
            self._write_pgm(image, blank=False)
            stat = image.stat()
            candidate = quick_pic.Candidate("test", image, stat.st_mtime_ns, stat.st_size)
            config = quick_pic.QuickPicConfig(root, root, crop_padding=2, extensions=(".pgm",))

            result = quick_pic.process_image(config, candidate, "transparent", 82, 25)

            self.assertTrue(result.startswith(b"\x89PNG\r\n\x1a\n"))

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is required")
    def test_blank_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "blank.pgm"
            self._write_pgm(image, blank=True)
            stat = image.stat()
            candidate = quick_pic.Candidate("test", image, stat.st_mtime_ns, stat.st_size)
            config = quick_pic.QuickPicConfig(root, root, crop_padding=2, extensions=(".pgm",))

            with self.assertRaisesRegex(quick_pic.QuickPicError, "No drawing"):
                quick_pic.process_image(config, candidate, "transparent", 82, 25)

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is required")
    def test_processing_preserves_drawing_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "drawing.ppm"
            pixels = [(255, 255, 255)] * 100
            pixels[55] = (230, 20, 40)
            payload = "P3\n10 10\n255\n" + "\n".join(
                f"{red} {green} {blue}" for red, green, blue in pixels
            )
            image.write_text(payload, encoding="ascii")
            stat = image.stat()
            candidate = quick_pic.Candidate("test", image, stat.st_mtime_ns, stat.st_size)
            config = quick_pic.QuickPicConfig(root, root, crop_padding=2, extensions=(".ppm",))

            result = quick_pic.process_image(config, candidate, "transparent", 82, 100)
            completed = __import__("subprocess").run(
                ["magick", "png:-", "-alpha", "off", "-format", "%[pixel:p{2,2}]", "info:"],
                input=result,
                capture_output=True,
                check=True,
            )

            pixel = completed.stdout.decode("ascii").lower()
            self.assertIn("srgb(230,20,40)", pixel)

    @unittest.skipUnless(shutil.which("magick"), "ImageMagick is required")
    def test_save_and_resolve_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_root = root / "output"
            input_dir.mkdir()
            output_root.mkdir()
            image = input_dir / "drawing.jpg"
            self._write_pgm(image, blank=False)
            config_path = self._write_config(root, input_dir, output_root)
            config = quick_pic.load_config(config_path)
            candidate = quick_pic.list_candidates(config)[0]
            output_dir = quick_pic.list_output_directories(config)[0]

            result = quick_pic.save_request(
                {
                    "candidate_id": candidate.id,
                    "background": "white",
                    "threshold": 82,
                    "scale_percent": 25,
                    "output_name": "Alice",
                    "output_dir_id": output_dir.id,
                },
                config_path,
            )
            saved, allowed_root = quick_pic.resolve_result(
                output_dir.id, result["name"], config_path
            )

            self.assertEqual(allowed_root, output_root)
            self.assertEqual(result["name"], "alice.png")
            self.assertEqual(saved.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertNotIn(str(output_root), str(result))

    def test_dedicated_page_uses_private_assets(self):
        page = quick_pic.render_tool_page("zh")

        self.assertIn("素写速食", page)
        self.assertIn("/static/quick_pic.js", page)
        self.assertIn("/static/quick_pic.css", page)
        self.assertIn("data-quick-pic-candidates", page)
        self.assertIn("data-quick-pic-output-name", page)
        self.assertIn("data-quick-pic-scale", page)
        self.assertNotIn("<figcaption>", page)
        self.assertNotIn("data-quick-pic-source", page)
        self.assertNotIn("/home/", page)

    @staticmethod
    def _write_config(
        root: Path, input_dir: Path, output_root: Path, recent_count: int = 5
    ) -> Path:
        path = root / "quick_pic.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "type": "command_tool",
                    "quick_pic": {
                        "input_dir": str(input_dir),
                        "output_root": str(output_root),
                        "output_root_label": "Test images",
                        "recent_count": recent_count,
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _write_pgm(path: Path, blank: bool) -> None:
        pixels = [255] * 400
        if not blank:
            for y in range(6, 14):
                for x in range(8, 12):
                    pixels[y * 20 + x] = 0
        rows = [" ".join(str(value) for value in pixels[index : index + 20]) for index in range(0, 400, 20)]
        path.write_text("P2\n20 20\n255\n" + "\n".join(rows) + "\n", encoding="ascii")


if __name__ == "__main__":
    unittest.main()
